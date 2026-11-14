"""
Limitin Desktop — Statistics Page

Displays analytical charts and tables: summary cards, bar/pie charts,
hour-of-day heatmap, and a ranked top apps table. Time range is selectable.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import customtkinter as ctk

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
import numpy as np  # noqa: E402

from themes.dark_theme import (
    BG_MID, BG_CARD, BG_CARD_HOVER, BG_ELEVATED,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT, ACCENT_MUTED,
    CYAN, CYAN_LIGHT, GREEN, GREEN_LIGHT, AMBER, AMBER_LIGHT, RED, RED_LIGHT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BORDER, BORDER_DIVIDER,
    font, font_bold,
    FONT_TITLE, FONT_HEADING, FONT_SUBHEADING, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_SMALL_BOLD, FONT_TINY, FONT_STAT_VALUE, FONT_STAT_LABEL,
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL, PAD_3XL,
    CARD_CORNER_RADIUS,
    STYLE_CARD, STYLE_SCROLLABLE_FRAME,
    ICONS, get_usage_color,
)
from utils.helpers import format_duration, format_percentage
from utils.time_utils import today_str, days_ago, get_week_range, get_month_range, get_year_range
from services.logger import get_logger

if TYPE_CHECKING:
    from database.schema import Database

logger = get_logger("ui.statistics")

# Colors for the pie / bar chart palette
_CHART_COLORS = [ACCENT, CYAN, GREEN, AMBER, RED, ACCENT_LIGHT, CYAN_LIGHT, GREEN_LIGHT, AMBER_LIGHT, RED_LIGHT]


class MiniStatCard(ctk.CTkFrame):
    """A small stat card with label + large value."""

    def __init__(self, master: ctk.CTkFrame, label: str, value: str = "—", **kwargs) -> None:
        super().__init__(master, **STYLE_CARD, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self._value = ctk.CTkLabel(self, text=value, font=font_bold(20), text_color=TEXT_PRIMARY, anchor="w")
        self._value.grid(row=0, column=0, sticky="w", padx=PAD_LG, pady=(PAD_LG, PAD_XS))

        self._label = ctk.CTkLabel(self, text=label, font=FONT_SMALL, text_color=TEXT_SECONDARY, anchor="w")
        self._label.grid(row=1, column=0, sticky="w", padx=PAD_LG, pady=(0, PAD_LG))

    def set_value(self, value: str) -> None:
        """Update the displayed value."""
        try:
            self._value.configure(text=value)
        except Exception:
            pass


class StatisticsPage(ctk.CTkFrame):
    """Statistics and analytics page with charts, heatmap, and top-apps table."""

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

        self._range: str = "Week"
        self._fig_bar: Figure | None = None
        self._fig_pie: Figure | None = None
        self._fig_heat: Figure | None = None
        self._canvas_bar: FigureCanvasTkAgg | None = None
        self._canvas_pie: FigureCanvasTkAgg | None = None
        self._canvas_heat: FigureCanvasTkAgg | None = None
        self._top_rows: list[ctk.CTkFrame] = []

        self._build_ui()
        logger.info("Statistics page initialized")

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct the full page layout."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self, **STYLE_SCROLLABLE_FRAME)
        self._scroll.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        row_idx = 0

        # ── Header ───────────────────────────────────────────────────────
        header = ctk.CTkFrame(self._scroll, fg_color="transparent")
        header.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(PAD_XL, PAD_MD))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text=f"{ICONS['stats']}  Statistics", font=FONT_TITLE,
                      text_color=TEXT_PRIMARY, anchor="w").grid(row=0, column=0, sticky="w")

        self._range_seg = ctk.CTkSegmentedButton(
            header, values=["Day", "Week", "Month", "Year"],
            font=FONT_SMALL, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=BG_ELEVATED,
            unselected_hover_color=BG_CARD_HOVER,
            text_color=TEXT_PRIMARY,
            command=self._on_range_changed,
        )
        self._range_seg.set("Week")
        self._range_seg.grid(row=0, column=1, sticky="e")
        row_idx += 1

        # ── Summary stat cards ───────────────────────────────────────────
        stats_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        stats_frame.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_MD))
        for c in range(5):
            stats_frame.grid_columnconfigure(c, weight=1)

        self._card_total = MiniStatCard(stats_frame, "Total Usage")
        self._card_total.grid(row=0, column=0, sticky="ew", padx=(0, PAD_SM), pady=PAD_XS)

        self._card_avg = MiniStatCard(stats_frame, "Daily Average")
        self._card_avg.grid(row=0, column=1, sticky="ew", padx=PAD_SM, pady=PAD_XS)

        self._card_most = MiniStatCard(stats_frame, "Most Used")
        self._card_most.grid(row=0, column=2, sticky="ew", padx=PAD_SM, pady=PAD_XS)

        self._card_saved = MiniStatCard(stats_frame, "Time Saved")
        self._card_saved.grid(row=0, column=3, sticky="ew", padx=PAD_SM, pady=PAD_XS)

        self._card_blocks = MiniStatCard(stats_frame, "Total Blocks")
        self._card_blocks.grid(row=0, column=4, sticky="ew", padx=(PAD_SM, 0), pady=PAD_XS)
        row_idx += 1

        # ── Charts row (bar + pie) ───────────────────────────────────────
        charts_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        charts_frame.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_MD))
        charts_frame.grid_columnconfigure(0, weight=3)
        charts_frame.grid_columnconfigure(1, weight=2)

        # Bar chart card
        bar_card = ctk.CTkFrame(charts_frame, **STYLE_CARD)
        bar_card.grid(row=0, column=0, sticky="nsew", padx=(0, PAD_SM))
        bar_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(bar_card, text="Usage by App", font=FONT_SUBHEADING,
                      text_color=TEXT_PRIMARY, anchor="w").grid(
            row=0, column=0, sticky="w", padx=PAD_LG, pady=(PAD_LG, PAD_SM))

        self._fig_bar = Figure(figsize=(5, 3), dpi=100)
        self._fig_bar.patch.set_facecolor(BG_CARD)
        self._ax_bar = self._fig_bar.add_subplot(111)
        self._style_axis(self._ax_bar)
        self._canvas_bar = FigureCanvasTkAgg(self._fig_bar, master=bar_card)
        w = self._canvas_bar.get_tk_widget()
        w.configure(bg=BG_CARD, highlightthickness=0)
        w.grid(row=1, column=0, sticky="ew", padx=PAD_SM, pady=(0, PAD_LG))

        # Pie chart card
        pie_card = ctk.CTkFrame(charts_frame, **STYLE_CARD)
        pie_card.grid(row=0, column=1, sticky="nsew", padx=(PAD_SM, 0))
        pie_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(pie_card, text="Usage Distribution", font=FONT_SUBHEADING,
                      text_color=TEXT_PRIMARY, anchor="w").grid(
            row=0, column=0, sticky="w", padx=PAD_LG, pady=(PAD_LG, PAD_SM))

        self._fig_pie = Figure(figsize=(3.5, 3), dpi=100)
        self._fig_pie.patch.set_facecolor(BG_CARD)
        self._ax_pie = self._fig_pie.add_subplot(111)
        self._canvas_pie = FigureCanvasTkAgg(self._fig_pie, master=pie_card)
        w2 = self._canvas_pie.get_tk_widget()
        w2.configure(bg=BG_CARD, highlightthickness=0)
        w2.grid(row=1, column=0, sticky="ew", padx=PAD_SM, pady=(0, PAD_LG))
        row_idx += 1

        # ── Heatmap ──────────────────────────────────────────────────────
        heat_card = ctk.CTkFrame(self._scroll, **STYLE_CARD)
        heat_card.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_MD))
        heat_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(heat_card, text="Activity Heatmap (Hour × Day of Week)", font=FONT_SUBHEADING,
                      text_color=TEXT_PRIMARY, anchor="w").grid(
            row=0, column=0, sticky="w", padx=PAD_LG, pady=(PAD_LG, PAD_SM))

        self._fig_heat = Figure(figsize=(8, 2.5), dpi=100)
        self._fig_heat.patch.set_facecolor(BG_CARD)
        self._ax_heat = self._fig_heat.add_subplot(111)
        self._canvas_heat = FigureCanvasTkAgg(self._fig_heat, master=heat_card)
        w3 = self._canvas_heat.get_tk_widget()
        w3.configure(bg=BG_CARD, highlightthickness=0)
        w3.grid(row=1, column=0, sticky="ew", padx=PAD_SM, pady=(0, PAD_LG))
        row_idx += 1

        # ── Top Apps Table ───────────────────────────────────────────────
        table_card = ctk.CTkFrame(self._scroll, **STYLE_CARD)
        table_card.grid(row=row_idx, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_XL))
        table_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(table_card, text="Top Applications", font=FONT_SUBHEADING,
                      text_color=TEXT_PRIMARY, anchor="w").grid(
            row=0, column=0, sticky="w", padx=PAD_LG, pady=(PAD_LG, PAD_SM))

        # Table header
        th = ctk.CTkFrame(table_card, fg_color=BG_ELEVATED, corner_radius=6, height=32)
        th.grid(row=1, column=0, sticky="ew", padx=PAD_LG, pady=(0, PAD_XS))
        th.grid_columnconfigure(1, weight=1)
        th.grid_propagate(False)

        for col, (text, w) in enumerate([("#", 40), ("Application", 0), ("Total Time", 120), ("% of Total", 100)]):
            ctk.CTkLabel(th, text=text, font=FONT_SMALL_BOLD, text_color=TEXT_TERTIARY,
                          anchor="w" if col <= 1 else "e",
                          width=w if w else 0).grid(row=0, column=col, sticky="ew", padx=PAD_SM, pady=PAD_XS)

        self._table_body = ctk.CTkFrame(table_card, fg_color="transparent")
        self._table_body.grid(row=2, column=0, sticky="ew", padx=PAD_LG, pady=(0, PAD_LG))
        self._table_body.grid_columnconfigure(1, weight=1)

    # ── Axis Styling ──────────────────────────────────────────────────────

    def _style_axis(self, ax: plt.Axes) -> None:  # type: ignore[name-defined]
        """Apply dark theme to a matplotlib axis."""
        ax.set_facecolor(BG_CARD)
        ax.tick_params(colors=TEXT_TERTIARY, labelsize=9)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("bottom", "left"):
            ax.spines[spine].set_color(BORDER_DIVIDER)

    # ── Data Loading ──────────────────────────────────────────────────────

    def _get_date_range(self) -> tuple[str, str]:
        """Return (start_date, end_date) ISO strings based on selected range."""
        end = today_str()
        if self._range == "Day":
            return end, end
        if self._range == "Week":
            return days_ago(6), end
        if self._range == "Month":
            return days_ago(29), end
        # Year
        return days_ago(364), end

    def _fetch_app_usage(self) -> list[dict]:
        """Return a list of {name, total_secs} dicts for the selected range."""
        if self.db is None:
            return []
        start, end = self._get_date_range()
        try:
            rows = self.db.fetch_all(
                """SELECT a.name, COALESCE(SUM(uh.usage_seconds), 0) as total_secs
                   FROM applications a
                   LEFT JOIN usage_history uh
                     ON a.id = uh.app_id AND uh.date BETWEEN ? AND ?
                   WHERE a.is_active = 1
                   GROUP BY a.id
                   HAVING total_secs > 0
                   ORDER BY total_secs DESC""",
                (start, end),
            )
            return [{"name": r["name"], "total_secs": r["total_secs"]} for r in rows]
        except Exception as exc:
            logger.error(f"Error fetching app usage: {exc}", exc_info=True)
            return []

    # ── Refresh ───────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload all data and update charts."""
        data = self._fetch_app_usage()
        self._update_summary_cards(data)
        self._update_bar_chart(data)
        self._update_pie_chart(data)
        self._update_heatmap()
        self._update_top_table(data)

    def _on_range_changed(self, mode: str) -> None:
        """Handle time range selector change."""
        self._range = mode
        logger.debug(f"Statistics range changed to {mode}")
        self.refresh()

    # ── Summary Cards ─────────────────────────────────────────────────────

    def _update_summary_cards(self, data: list[dict]) -> None:
        """Update the 5 summary stat cards."""
        total_secs = sum(d["total_secs"] for d in data)
        self._card_total.set_value(format_duration(total_secs))

        # Daily average
        start, end = self._get_date_range()
        try:
            d_start = date.fromisoformat(start)
            d_end = date.fromisoformat(end)
            num_days = max(1, (d_end - d_start).days + 1)
        except ValueError:
            num_days = 1
        avg = total_secs // num_days if num_days else 0
        self._card_avg.set_value(format_duration(avg))

        # Most used app
        most = data[0]["name"] if data else "—"
        self._card_most.set_value(most)

        # Time saved — estimate as (limit_total - usage_total) clamped >= 0
        saved = 0
        if self.db is not None:
            try:
                row = self.db.fetch_one(
                    "SELECT COALESCE(SUM(daily_limit_seconds), 0) as total_limit FROM applications WHERE is_active = 1"
                )
                if row:
                    limit_total_secs = row["total_limit"] * num_days
                    saved = max(0, limit_total_secs - total_secs)
            except Exception:
                pass
        self._card_saved.set_value(format_duration(saved))

        # Total blocks
        blocks = 0
        if self.db is not None:
            try:
                s, e = self._get_date_range()
                row = self.db.fetch_one(
                    "SELECT COUNT(*) as cnt FROM blocked_events WHERE timestamp >= ? AND timestamp <= ?",
                    (s, e + "T23:59:59"),
                )
                blocks = row["cnt"] if row else 0
            except Exception:
                pass
        self._card_blocks.set_value(str(blocks))

    # ── Bar Chart ─────────────────────────────────────────────────────────

    def _update_bar_chart(self, data: list[dict]) -> None:
        """Draw the usage-per-app bar chart."""
        if self._fig_bar is None or self._canvas_bar is None:
            return

        self._ax_bar.clear()
        self._style_axis(self._ax_bar)

        top = data[:8] if data else []
        names = [d["name"] for d in top] or ["No data"]
        mins = [d["total_secs"] / 60 for d in top] or [0]
        colors = [_CHART_COLORS[i % len(_CHART_COLORS)] for i in range(len(names))]

        y = range(len(names))
        self._ax_bar.barh(list(y), mins, color=colors, height=0.6, edgecolor="none")
        self._ax_bar.set_yticks(list(y))
        self._ax_bar.set_yticklabels(names, fontsize=9, color=TEXT_SECONDARY)
        self._ax_bar.set_xlabel("Minutes", fontsize=9, color=TEXT_TERTIARY)
        self._ax_bar.invert_yaxis()
        self._fig_bar.tight_layout(pad=1.5)

        try:
            self._canvas_bar.draw_idle()
        except Exception:
            pass

    # ── Pie Chart ─────────────────────────────────────────────────────────

    def _update_pie_chart(self, data: list[dict]) -> None:
        """Draw the usage distribution pie chart."""
        if self._fig_pie is None or self._canvas_pie is None:
            return

        self._ax_pie.clear()

        top = data[:6] if data else []
        if not top:
            self._ax_pie.text(
                0.5, 0.5, "No data", ha="center", va="center",
                fontsize=12, color=TEXT_TERTIARY, transform=self._ax_pie.transAxes,
            )
            self._fig_pie.tight_layout(pad=1)
            try:
                self._canvas_pie.draw_idle()
            except Exception:
                pass
            return

        labels = [d["name"] for d in top]
        sizes = [d["total_secs"] for d in top]
        colors = [_CHART_COLORS[i % len(_CHART_COLORS)] for i in range(len(labels))]

        wedges, texts, autotexts = self._ax_pie.pie(
            sizes, labels=labels, colors=colors, autopct="%1.0f%%",
            startangle=140, pctdistance=0.8,
            textprops={"fontsize": 8, "color": TEXT_SECONDARY},
        )
        for at in autotexts:
            at.set_color(TEXT_PRIMARY)
            at.set_fontsize(7)

        self._fig_pie.tight_layout(pad=1)
        try:
            self._canvas_pie.draw_idle()
        except Exception:
            pass

    # ── Heatmap ───────────────────────────────────────────────────────────

    def _update_heatmap(self) -> None:
        """Draw the hour × day-of-week activity heatmap."""
        if self._fig_heat is None or self._canvas_heat is None:
            return

        self._ax_heat.clear()

        # Build a 7×24 matrix (days_of_week × hours)
        grid = np.zeros((7, 24), dtype=float)

        if self.db is not None:
            try:
                start, end = self._get_date_range()
                rows = self.db.fetch_all(
                    """SELECT start_time, duration_seconds
                       FROM usage_sessions
                       WHERE session_date BETWEEN ? AND ?
                         AND start_time IS NOT NULL""",
                    (start, end),
                )
                from datetime import datetime as _dt
                for r in rows:
                    try:
                        dt = _dt.fromisoformat(r["start_time"])
                        dow = dt.weekday()  # 0=Mon
                        hour = dt.hour
                        grid[dow][hour] += r["duration_seconds"] / 60.0
                    except (ValueError, TypeError):
                        continue
            except Exception as exc:
                logger.error(f"Heatmap data error: {exc}", exc_info=True)

        # Use a purple colormap
        from matplotlib.colors import LinearSegmentedColormap
        cmap = LinearSegmentedColormap.from_list("limitin", [BG_CARD, ACCENT_MUTED, ACCENT, ACCENT_LIGHT])

        im = self._ax_heat.imshow(grid, aspect="auto", cmap=cmap, interpolation="nearest")
        self._ax_heat.set_yticks(range(7))
        self._ax_heat.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                                       fontsize=8, color=TEXT_SECONDARY)
        self._ax_heat.set_xticks(range(0, 24, 3))
        self._ax_heat.set_xticklabels([f"{h}:00" for h in range(0, 24, 3)],
                                       fontsize=8, color=TEXT_SECONDARY)
        self._ax_heat.tick_params(length=0)

        for spine in self._ax_heat.spines.values():
            spine.set_visible(False)

        self._fig_heat.tight_layout(pad=1.5)
        try:
            self._canvas_heat.draw_idle()
        except Exception:
            pass

    # ── Top Apps Table ────────────────────────────────────────────────────

    def _update_top_table(self, data: list[dict]) -> None:
        """Rebuild the top applications table rows."""
        for row_widget in self._top_rows:
            row_widget.destroy()
        self._top_rows.clear()

        total_secs = max(1, sum(d["total_secs"] for d in data))

        for i, d in enumerate(data[:10]):
            row_frame = ctk.CTkFrame(self._table_body, fg_color="transparent", height=32)
            row_frame.grid(row=i, column=0, columnspan=4, sticky="ew", pady=1)
            row_frame.grid_columnconfigure(1, weight=1)
            row_frame.grid_propagate(False)

            # Rank
            ctk.CTkLabel(row_frame, text=str(i + 1), font=FONT_SMALL, text_color=TEXT_TERTIARY,
                          width=40, anchor="w").grid(row=0, column=0, padx=PAD_SM)
            # Name
            ctk.CTkLabel(row_frame, text=d["name"], font=FONT_BODY, text_color=TEXT_PRIMARY,
                          anchor="w").grid(row=0, column=1, sticky="ew", padx=PAD_SM)
            # Total time
            ctk.CTkLabel(row_frame, text=format_duration(d["total_secs"], short=True),
                          font=FONT_SMALL, text_color=TEXT_SECONDARY,
                          width=120, anchor="e").grid(row=0, column=2, padx=PAD_SM)
            # Percentage
            pct = d["total_secs"] / total_secs
            ctk.CTkLabel(row_frame, text=format_percentage(pct),
                          font=FONT_SMALL_BOLD, text_color=get_usage_color(pct),
                          width=100, anchor="e").grid(row=0, column=3, padx=PAD_SM)

            self._top_rows.append(row_frame)

        if not data:
            empty = ctk.CTkLabel(
                self._table_body, text="No usage data for this period.",
                font=FONT_BODY, text_color=TEXT_TERTIARY,
            )
            empty.grid(row=0, column=0, columnspan=4, pady=PAD_LG)
            self._top_rows.append(empty)

    # ── Cleanup ───────────────────────────────────────────────────────────

    def destroy(self) -> None:
        """Clean up matplotlib figures."""
        for fig in (self._fig_bar, self._fig_pie, self._fig_heat):
            if fig is not None:
                plt.close(fig)
        self._fig_bar = None
        self._fig_pie = None
        self._fig_heat = None
        super().destroy()
