"""
Limitin Desktop — Dashboard Page

The main dashboard showing real-time usage statistics, charts, current activity,
and a sortable list of monitored applications with progress bars.
Auto-refreshes every second for live data.
"""

from __future__ import annotations

import math
from datetime import datetime, date, timedelta
from typing import TYPE_CHECKING

import customtkinter as ctk

# Matplotlib setup — must set backend before importing pyplot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from themes.dark_theme import (
    BG_DARKEST, BG_DARK, BG_MID, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BG_INPUT,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT, ACCENT_MUTED, ACCENT_SURFACE,
    CYAN, CYAN_LIGHT, GREEN, GREEN_LIGHT, GREEN_MUTED,
    AMBER, AMBER_LIGHT, AMBER_MUTED, RED, RED_LIGHT, RED_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_DISABLED,
    BORDER, BORDER_HOVER, BORDER_DIVIDER,
    FONT_FAMILY, font, font_bold,
    FONT_TITLE, FONT_HEADING, FONT_SUBHEADING, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_SMALL_BOLD, FONT_TINY, FONT_STAT_VALUE, FONT_STAT_LABEL,
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL, PAD_3XL,
    CARD_CORNER_RADIUS, BUTTON_CORNER_RADIUS,
    STYLE_CARD, STYLE_BUTTON_PRIMARY, STYLE_BUTTON_SECONDARY, STYLE_BUTTON_GHOST,
    STYLE_PROGRESS_BAR, STYLE_SCROLLABLE_FRAME,
    ICONS, get_usage_color, get_status_badge_colors,
)
from utils.helpers import format_duration, format_percentage, clamp
from utils.time_utils import today_str, now_iso, format_date_display, days_ago
from services.logger import get_logger

if TYPE_CHECKING:
    from database.schema import Database

logger = get_logger("ui.dashboard")


# ── Helper Widgets ────────────────────────────────────────────────────────────

class StatCard(ctk.CTkFrame):
    """A compact stat card showing an icon, value, and label."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        icon: str,
        label: str,
        value: str = "—",
        accent_color: str = ACCENT,
        **kwargs,
    ) -> None:
        super().__init__(master, **STYLE_CARD, **kwargs)
        self._accent = accent_color

        self.grid_columnconfigure(1, weight=1)

        # Icon circle
        self._icon_frame = ctk.CTkFrame(
            self, width=44, height=44,
            fg_color=accent_color, corner_radius=10,
        )
        self._icon_frame.grid(row=0, column=0, rowspan=2, padx=(PAD_LG, PAD_MD), pady=PAD_LG)
        self._icon_frame.grid_propagate(False)
        self._icon_label = ctk.CTkLabel(
            self._icon_frame, text=icon, font=font_bold(18),
            text_color="#ffffff",
        )
        self._icon_label.place(relx=0.5, rely=0.5, anchor="center")

        # Value
        self._value_label = ctk.CTkLabel(
            self, text=value, font=font_bold(22),
            text_color=TEXT_PRIMARY, anchor="w",
        )
        self._value_label.grid(row=0, column=1, sticky="sw", padx=(0, PAD_LG), pady=(PAD_LG, 0))

        # Label
        self._label_label = ctk.CTkLabel(
            self, text=label, font=FONT_SMALL,
            text_color=TEXT_SECONDARY, anchor="w",
        )
        self._label_label.grid(row=1, column=1, sticky="nw", padx=(0, PAD_LG), pady=(0, PAD_LG))

    def set_value(self, value: str) -> None:
        """Update the displayed value."""
        try:
            self._value_label.configure(text=value)
        except Exception:
            pass


class ProgressCard(ctk.CTkFrame):
    """A card showing an app's name, usage, limit, and progress bar."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        app_name: str = "",
        usage_seconds: int = 0,
        limit_seconds: int = 3600,
        is_active: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(master, **STYLE_CARD, height=68, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self.grid_propagate(False)

        # Status dot
        status_color = GREEN if is_active else TEXT_TERTIARY
        self._dot = ctk.CTkLabel(
            self, text="●", font=font(10), text_color=status_color, width=20,
        )
        self._dot.grid(row=0, column=0, rowspan=2, padx=(PAD_MD, PAD_XS), pady=PAD_MD)

        # App name
        self._name_label = ctk.CTkLabel(
            self, text=app_name, font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY, anchor="w",
        )
        self._name_label.grid(row=0, column=1, sticky="sw", padx=(0, PAD_SM), pady=(PAD_MD, 0))

        # Usage text
        pct = usage_seconds / max(limit_seconds, 1)
        usage_text = f"{format_duration(usage_seconds)} / {format_duration(limit_seconds)}"
        self._usage_label = ctk.CTkLabel(
            self, text=usage_text, font=FONT_SMALL,
            text_color=TEXT_SECONDARY, anchor="e",
        )
        self._usage_label.grid(row=0, column=2, sticky="se", padx=(0, PAD_LG), pady=(PAD_MD, 0))

        # Percentage
        self._pct_label = ctk.CTkLabel(
            self, text=format_percentage(pct), font=FONT_SMALL_BOLD,
            text_color=get_usage_color(pct), anchor="e",
        )
        self._pct_label.grid(row=1, column=2, sticky="ne", padx=(0, PAD_LG), pady=(2, PAD_MD))

        # Progress bar
        bar_color = get_usage_color(pct)
        self._progress = ctk.CTkProgressBar(
            self, progress_color=bar_color,
            fg_color=BG_ELEVATED, corner_radius=3, height=6,
        )
        self._progress.set(clamp(pct, 0, 1))
        self._progress.grid(row=1, column=1, sticky="new", padx=(0, PAD_SM), pady=(4, PAD_MD))

    def update_data(
        self,
        app_name: str,
        usage_seconds: int,
        limit_seconds: int,
        is_active: bool = False,
    ) -> None:
        """Update the card with new data."""
        try:
            pct = usage_seconds / max(limit_seconds, 1)
            bar_color = get_usage_color(pct)
            usage_text = f"{format_duration(usage_seconds)} / {format_duration(limit_seconds)}"

            self._name_label.configure(text=app_name)
            self._usage_label.configure(text=usage_text)
            self._pct_label.configure(
                text=format_percentage(pct),
                text_color=get_usage_color(pct),
            )
            self._progress.configure(progress_color=bar_color)
            self._progress.set(clamp(pct, 0, 1))
            self._dot.configure(text_color=GREEN if is_active else TEXT_TERTIARY)
        except Exception:
            pass


# ── Dashboard Page ────────────────────────────────────────────────────────────

class DashboardPage(ctk.CTkFrame):
    """Main dashboard with live stats, charts, current activity, and app list."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        db: "Database | None" = None,
        tracker: object | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color=BG_MID, corner_radius=0, **kwargs)
        self.db = db
        self.tracker = tracker

        self._chart_mode: str = "Day"
        self._fig: Figure | None = None
        self._canvas: FigureCanvasTkAgg | None = None
        self._progress_cards: list[ProgressCard] = []
        self._refresh_job: str | None = None
        self._destroyed = False

        self._build_ui()
        logger.info("Dashboard page initialized")

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct all dashboard widgets."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Scrollable container
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_fg_color=BG_MID,
            scrollbar_button_color=ACCENT_MUTED,
            scrollbar_button_hover_color=ACCENT,
        )
        self._scroll.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        row_idx = 0

        # ── 1. Header ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self._scroll, fg_color="transparent")
        header.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(PAD_XL, PAD_MD))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=f"{ICONS['dashboard']}  Dashboard", font=FONT_TITLE,
            text_color=TEXT_PRIMARY, anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._datetime_label = ctk.CTkLabel(
            header, text="", font=FONT_SMALL, text_color=TEXT_SECONDARY, anchor="e",
        )
        self._datetime_label.grid(row=0, column=1, sticky="e")
        row_idx += 1

        # ── 2. Stat cards ────────────────────────────────────────────────
        stats_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        stats_frame.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_MD))
        for c in range(4):
            stats_frame.grid_columnconfigure(c, weight=1)

        self._stat_usage = StatCard(stats_frame, ICONS["clock"], "Total Usage Today", accent_color=ACCENT)
        self._stat_usage.grid(row=0, column=0, sticky="ew", padx=(0, PAD_SM), pady=PAD_XS)

        self._stat_apps = StatCard(stats_frame, ICONS["apps"], "Apps Monitored", accent_color=CYAN)
        self._stat_apps.grid(row=0, column=1, sticky="ew", padx=PAD_SM, pady=PAD_XS)

        self._stat_blocked = StatCard(stats_frame, ICONS["block"], "Apps Blocked", accent_color=RED)
        self._stat_blocked.grid(row=0, column=2, sticky="ew", padx=PAD_SM, pady=PAD_XS)

        self._stat_streak = StatCard(stats_frame, ICONS["streak"], "Current Streak", accent_color=AMBER)
        self._stat_streak.grid(row=0, column=3, sticky="ew", padx=(PAD_SM, 0), pady=PAD_XS)
        row_idx += 1

        # ── 3. Main content: chart + activity ────────────────────────────
        main_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        main_frame.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_MD))
        main_frame.grid_columnconfigure(0, weight=3)
        main_frame.grid_columnconfigure(1, weight=1)

        # Left: Chart area
        chart_container = ctk.CTkFrame(main_frame, **STYLE_CARD)
        chart_container.grid(row=0, column=0, sticky="nsew", padx=(0, PAD_SM), pady=0)
        chart_container.grid_columnconfigure(0, weight=1)

        chart_header = ctk.CTkFrame(chart_container, fg_color="transparent")
        chart_header.grid(row=0, column=0, sticky="ew", padx=PAD_LG, pady=(PAD_LG, PAD_SM))
        chart_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            chart_header, text="Usage Overview", font=FONT_SUBHEADING,
            text_color=TEXT_PRIMARY, anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._chart_seg = ctk.CTkSegmentedButton(
            chart_header, values=["Day", "Week", "Month"],
            font=FONT_SMALL, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_ELEVATED,
            unselected_hover_color=BG_CARD_HOVER,
            text_color=TEXT_PRIMARY,
            command=self._on_chart_mode_changed,
        )
        self._chart_seg.set("Day")
        self._chart_seg.grid(row=0, column=1, sticky="e")

        # Matplotlib figure
        self._fig = Figure(figsize=(6, 3), dpi=100)
        self._fig.patch.set_facecolor(BG_CARD)
        self._ax = self._fig.add_subplot(111)
        self._style_axis(self._ax)

        self._canvas = FigureCanvasTkAgg(self._fig, master=chart_container)
        canvas_widget = self._canvas.get_tk_widget()
        canvas_widget.configure(bg=BG_CARD, highlightthickness=0)
        canvas_widget.grid(row=1, column=0, sticky="ew", padx=PAD_SM, pady=(0, PAD_LG))

        # Right: Activity sidebar
        activity_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        activity_frame.grid(row=0, column=1, sticky="nsew", padx=(PAD_SM, 0), pady=0)
        activity_frame.grid_columnconfigure(0, weight=1)

        # Current activity card
        current_card = ctk.CTkFrame(activity_frame, **STYLE_CARD)
        current_card.grid(row=0, column=0, sticky="ew", pady=(0, PAD_SM))
        current_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            current_card, text="Currently Active", font=FONT_SMALL_BOLD,
            text_color=TEXT_SECONDARY, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=PAD_LG, pady=(PAD_LG, PAD_XS))

        self._active_app_label = ctk.CTkLabel(
            current_card, text="No active app", font=FONT_SUBHEADING,
            text_color=TEXT_PRIMARY, anchor="w",
        )
        self._active_app_label.grid(row=1, column=0, sticky="w", padx=PAD_LG, pady=0)

        self._session_timer_label = ctk.CTkLabel(
            current_card, text="00:00", font=font_bold(28),
            text_color=ACCENT_LIGHT, anchor="w",
        )
        self._session_timer_label.grid(row=2, column=0, sticky="w", padx=PAD_LG, pady=(PAD_XS, PAD_LG))

        # Quick actions card
        actions_card = ctk.CTkFrame(activity_frame, **STYLE_CARD)
        actions_card.grid(row=1, column=0, sticky="ew", pady=(PAD_SM, 0))
        actions_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            actions_card, text="Quick Actions", font=FONT_SMALL_BOLD,
            text_color=TEXT_SECONDARY, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=PAD_LG, pady=(PAD_LG, PAD_SM))

        ctk.CTkButton(
            actions_card, text=f"{ICONS['add']}  Add App",
            **STYLE_BUTTON_PRIMARY, width=0,
            command=self._on_add_app,
        ).grid(row=1, column=0, sticky="ew", padx=PAD_LG, pady=(0, PAD_SM))

        ctk.CTkButton(
            actions_card, text=f"{ICONS['focus']}  Start Focus",
            **STYLE_BUTTON_SECONDARY, width=0,
            command=self._on_start_focus,
        ).grid(row=2, column=0, sticky="ew", padx=PAD_LG, pady=(0, PAD_SM))

        self._pause_btn = ctk.CTkButton(
            actions_card, text=f"{ICONS['pause']}  Pause Tracking",
            **STYLE_BUTTON_GHOST, width=0,
            command=self._on_toggle_tracking,
        )
        self._pause_btn.grid(row=3, column=0, sticky="ew", padx=PAD_LG, pady=(0, PAD_LG))

        row_idx += 1

        # ── 4. App usage list ────────────────────────────────────────────
        list_header = ctk.CTkFrame(self._scroll, fg_color="transparent")
        list_header.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(PAD_SM, PAD_SM))
        ctk.CTkLabel(
            list_header, text="App Usage", font=FONT_HEADING,
            text_color=TEXT_PRIMARY, anchor="w",
        ).grid(row=0, column=0, sticky="w")
        row_idx += 1

        self._app_list_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._app_list_frame.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_XL))
        self._app_list_frame.grid_columnconfigure(0, weight=1)

        self._empty_label = ctk.CTkLabel(
            self._app_list_frame,
            text="No apps being monitored.\nClick 'Add App' to get started.",
            font=FONT_BODY, text_color=TEXT_TERTIARY,
        )

    # ── Chart Helpers ─────────────────────────────────────────────────────

    def _style_axis(self, ax: plt.Axes) -> None:  # type: ignore[name-defined]
        """Apply dark theme styling to a matplotlib axis."""
        ax.set_facecolor(BG_CARD)
        ax.tick_params(colors=TEXT_TERTIARY, labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color(BORDER_DIVIDER)
        ax.spines["left"].set_color(BORDER_DIVIDER)
        ax.yaxis.label.set_color(TEXT_SECONDARY)
        ax.xaxis.label.set_color(TEXT_SECONDARY)

    def _on_chart_mode_changed(self, mode: str) -> None:
        """Handle chart time range segmented button change."""
        self._chart_mode = mode
        logger.debug(f"Chart mode changed to {mode}")
        self._update_chart()

    def _update_chart(self) -> None:
        """Redraw the usage bar chart with current data."""
        if self._fig is None or self._canvas is None:
            return

        self._ax.clear()
        self._style_axis(self._ax)

        app_names: list[str] = []
        app_minutes: list[float] = []

        try:
            if self.db is not None:
                today = today_str()

                if self._chart_mode == "Day":
                    start_date = today
                elif self._chart_mode == "Week":
                    start_date = days_ago(6)
                else:  # Month
                    start_date = days_ago(29)

                # Gather per-app usage
                rows = self.db.fetch_all(
                    """SELECT a.name, COALESCE(SUM(uh.usage_seconds), 0) as total_secs
                       FROM applications a
                       LEFT JOIN usage_history uh
                         ON a.id = uh.app_id AND uh.date BETWEEN ? AND ?
                       WHERE a.is_active = 1
                       GROUP BY a.id
                       ORDER BY total_secs DESC
                       LIMIT 8""",
                    (start_date, today),
                )
                for r in rows:
                    app_names.append(r["name"])
                    app_minutes.append(r["total_secs"] / 60.0)
        except Exception as exc:
            logger.error(f"Error fetching chart data: {exc}", exc_info=True)

        if not app_names:
            app_names = ["No data"]
            app_minutes = [0]

        # Draw horizontal bar chart
        colors = [ACCENT if m > 0 else BG_ELEVATED for m in app_minutes]
        y_pos = range(len(app_names))
        self._ax.barh(y_pos, app_minutes, color=colors, height=0.6, edgecolor="none")
        self._ax.set_yticks(list(y_pos))
        self._ax.set_yticklabels(app_names, fontsize=9, color=TEXT_SECONDARY)
        self._ax.set_xlabel("Minutes", fontsize=9, color=TEXT_TERTIARY)
        self._ax.invert_yaxis()
        self._fig.tight_layout(pad=1.5)

        try:
            self._canvas.draw_idle()
        except Exception:
            pass

    # ── Data Refresh ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload all data from the database and tracker."""
        if self._destroyed:
            return

        try:
            self._update_datetime()
            self._update_stats()
            self._update_chart()
            self._update_active_app()
            self._update_app_list()
        except Exception as exc:
            logger.error(f"Dashboard refresh error: {exc}", exc_info=True)

    def _update_datetime(self) -> None:
        """Update the header date/time label."""
        now = datetime.now()
        self._datetime_label.configure(
            text=now.strftime("%A, %B %d %Y  •  %I:%M %p")
        )

    def _update_stats(self) -> None:
        """Update the four stat cards."""
        if self.db is None:
            self._stat_usage.set_value("—")
            self._stat_apps.set_value("0")
            self._stat_blocked.set_value("0")
            self._stat_streak.set_value("0 days")
            return

        try:
            today = today_str()

            # Total usage today
            row = self.db.fetch_one(
                "SELECT COALESCE(SUM(usage_seconds), 0) as total "
                "FROM usage_history WHERE date = ?",
                (today,),
            )
            total_secs = row["total"] if row else 0
            self._stat_usage.set_value(format_duration(total_secs))

            # Apps monitored
            row = self.db.fetch_one("SELECT COUNT(*) as cnt FROM applications WHERE is_active = 1")
            self._stat_apps.set_value(str(row["cnt"] if row else 0))

            # Blocked count today
            row = self.db.fetch_one(
                "SELECT COUNT(*) as cnt FROM blocked_events WHERE timestamp LIKE ?",
                (today + "%",),
            )
            blocked_cnt = row["cnt"] if row else 0
            self._stat_blocked.set_value(str(blocked_cnt))

            # Streak: count consecutive days from yesterday backward that have usage
            streak = self._compute_streak()
            self._stat_streak.set_value(f"{streak} day{'s' if streak != 1 else ''}")

        except Exception as exc:
            logger.error(f"Error updating stats: {exc}", exc_info=True)

    def _compute_streak(self) -> int:
        """Count consecutive past days with recorded usage."""
        if self.db is None:
            return 0
        streak = 0
        try:
            for i in range(1, 366):
                d = days_ago(i)
                row = self.db.fetch_one(
                    "SELECT COALESCE(SUM(usage_seconds), 0) as total "
                    "FROM usage_history WHERE date = ?",
                    (d,),
                )
                if row and row["total"] > 0:
                    streak += 1
                else:
                    break
        except Exception:
            pass
        return streak

    def _update_active_app(self) -> None:
        """Update the 'Currently Active' card."""
        active_name = "No active app"
        session_time = "00:00"

        if self.tracker is not None:
            try:
                # The tracker should expose active_app_name and active_session_seconds
                name = getattr(self.tracker, "active_app_name", None)
                secs = getattr(self.tracker, "active_session_seconds", 0)
                if name:
                    active_name = name
                    mins, s = divmod(int(secs), 60)
                    hrs, mins = divmod(mins, 60)
                    session_time = f"{hrs:02d}:{mins:02d}:{s:02d}" if hrs else f"{mins:02d}:{s:02d}"
            except Exception:
                pass

        try:
            self._active_app_label.configure(text=active_name)
            self._session_timer_label.configure(text=session_time)
        except Exception:
            pass

    def _update_app_list(self) -> None:
        """Rebuild the app usage progress cards."""
        if self.db is None:
            self._show_empty_state()
            return

        try:
            today = today_str()

            rows = self.db.fetch_all(
                """SELECT a.id, a.name,
                          a.daily_limit_seconds as limit_secs,
                          COALESCE(SUM(uh.usage_seconds), 0) as used_secs
                   FROM applications a
                   LEFT JOIN usage_history uh
                     ON a.id = uh.app_id AND uh.date = ?
                   WHERE a.is_active = 1
                   GROUP BY a.id
                   ORDER BY used_secs DESC""",
                (today,),
            )

            if not rows:
                self._show_empty_state()
                return

            self._empty_label.grid_forget()

            # Reuse or create progress cards
            active_name = ""
            if self.tracker is not None:
                active_name = getattr(self.tracker, "active_app_name", "") or ""

            for i, r in enumerate(rows):
                name = r["name"]
                used = r["used_secs"]
                limit_sec = r["limit_secs"]
                is_active = name.lower() == active_name.lower() if active_name else False

                if i < len(self._progress_cards):
                    self._progress_cards[i].update_data(name, used, limit_sec, is_active)
                else:
                    card = ProgressCard(
                        self._app_list_frame,
                        app_name=name, usage_seconds=used,
                        limit_seconds=limit_sec, is_active=is_active,
                    )
                    card.grid(row=i, column=0, sticky="ew", pady=(0, PAD_SM))
                    self._progress_cards.append(card)

            # Remove extra cards
            while len(self._progress_cards) > len(rows):
                card = self._progress_cards.pop()
                card.destroy()

        except Exception as exc:
            logger.error(f"Error updating app list: {exc}", exc_info=True)

    def _show_empty_state(self) -> None:
        """Show the empty state label."""
        for card in self._progress_cards:
            card.destroy()
        self._progress_cards.clear()
        self._empty_label.grid(row=0, column=0, pady=PAD_2XL)

    # ── Actions ───────────────────────────────────────────────────────────

    def _on_add_app(self) -> None:
        """Placeholder for navigating to the Add App dialog."""
        logger.info("Add App action triggered from dashboard")

    def _on_start_focus(self) -> None:
        """Placeholder for navigating to focus mode."""
        logger.info("Start Focus action triggered from dashboard")

    def _on_toggle_tracking(self) -> None:
        """Toggle global tracking pause/resume."""
        if self.tracker is not None:
            paused = getattr(self.tracker, "paused", False)
            if paused:
                if hasattr(self.tracker, "resume"):
                    self.tracker.resume()  # type: ignore[attr-defined]
                self._pause_btn.configure(text=f"{ICONS['pause']}  Pause Tracking")
            else:
                if hasattr(self.tracker, "pause"):
                    self.tracker.pause()  # type: ignore[attr-defined]
                self._pause_btn.configure(text=f"{ICONS['play']}  Resume Tracking")
        logger.info("Tracking toggled from dashboard")

    # ── Auto-refresh ──────────────────────────────────────────────────────

    def _auto_refresh(self) -> None:
        """Periodic refresh every 1 second."""
        if self._destroyed:
            return
        try:
            self._update_datetime()
            self._update_active_app()
            # Full refresh (chart/stats) every 10 seconds to reduce load
            if not hasattr(self, "_tick_counter"):
                self._tick_counter = 0
            self._tick_counter += 1
            if self._tick_counter % 10 == 0:
                self._update_stats()
                self._update_chart()
                self._update_app_list()
        except Exception as exc:
            logger.error(f"Auto-refresh error: {exc}", exc_info=True)

        if not self._destroyed:
            self._refresh_job = self.after(1000, self._auto_refresh)

    def start_auto_refresh(self) -> None:
        """Begin the auto-refresh loop."""
        self._destroyed = False
        self.refresh()
        self._auto_refresh()

    def stop_auto_refresh(self) -> None:
        """Cancel the auto-refresh loop."""
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None

    def destroy(self) -> None:
        """Clean up before destruction."""
        self._destroyed = True
        self.stop_auto_refresh()
        if self._fig is not None:
            plt.close(self._fig)
            self._fig = None
        super().destroy()
