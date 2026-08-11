"""
Opal Desktop — History Page

Usage history timeline with day-by-day navigation, daily summaries,
per-app usage breakdown, and blocked events log.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import customtkinter as ctk

from themes.dark_theme import (
    BG_MID, BG_CARD, BG_CARD_HOVER, BG_ELEVATED,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT, ACCENT_MUTED,
    CYAN, GREEN, GREEN_MUTED, AMBER, AMBER_MUTED, RED, RED_LIGHT, RED_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_DISABLED,
    BORDER, BORDER_DIVIDER,
    font, font_bold,
    FONT_TITLE, FONT_HEADING, FONT_SUBHEADING, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_SMALL_BOLD, FONT_TINY, FONT_STAT_VALUE,
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL, PAD_3XL,
    CARD_CORNER_RADIUS, BUTTON_CORNER_RADIUS,
    STYLE_CARD, STYLE_BUTTON_PRIMARY, STYLE_BUTTON_SECONDARY, STYLE_BUTTON_GHOST,
    STYLE_SCROLLABLE_FRAME, STYLE_INPUT, STYLE_PROGRESS_BAR,
    ICONS, get_usage_color,
)
from utils.helpers import format_duration, format_percentage, clamp
from utils.time_utils import today_str, format_date_display
from services.logger import get_logger

if TYPE_CHECKING:
    from database.schema import Database

logger = get_logger("ui.history")


class HistoryAppRow(ctk.CTkFrame):
    """A single app usage row in the history view."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        app_name: str = "",
        usage_seconds: int = 0,
        limit_seconds: int = 3600,
        **kwargs,
    ) -> None:
        super().__init__(master, **STYLE_CARD, height=60, **kwargs)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)

        pct = usage_seconds / max(limit_seconds, 1)

        # App name
        ctk.CTkLabel(
            self, text=app_name, font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(PAD_LG, PAD_SM), pady=(PAD_MD, 0))

        # Progress bar
        bar = ctk.CTkProgressBar(
            self, progress_color=get_usage_color(pct),
            fg_color=BG_ELEVATED, corner_radius=3, height=6,
        )
        bar.set(clamp(pct, 0, 1))
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=PAD_LG, pady=(PAD_XS, PAD_MD))

        # Usage / Limit text
        usage_text = f"{format_duration(usage_seconds, short=True)} / {format_duration(limit_seconds, short=True)}"
        ctk.CTkLabel(
            self, text=usage_text, font=FONT_SMALL,
            text_color=TEXT_SECONDARY, anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=(0, PAD_LG), pady=(PAD_MD, 0))

        # Percentage badge
        ctk.CTkLabel(
            self, text=format_percentage(pct), font=FONT_SMALL_BOLD,
            text_color=get_usage_color(pct), anchor="e", width=60,
        ).grid(row=0, column=2, sticky="e", padx=(0, PAD_LG), pady=(PAD_MD, 0))


class BlockedEventRow(ctk.CTkFrame):
    """A single blocked event log entry."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        app_name: str = "",
        timestamp: str = "",
        reason: str = "",
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color=RED_MUTED, corner_radius=8, height=44, **kwargs)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=ICONS["block"], font=font(12),
            text_color=RED_LIGHT, width=28,
        ).grid(row=0, column=0, padx=(PAD_MD, PAD_XS), pady=PAD_SM)

        ctk.CTkLabel(
            self, text=app_name, font=FONT_SMALL_BOLD,
            text_color=RED_LIGHT, anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=0, pady=PAD_SM)

        reason_display = reason.replace("_", " ").title() if reason else "Blocked"
        ctk.CTkLabel(
            self, text=reason_display, font=FONT_TINY,
            text_color=TEXT_TERTIARY, anchor="e",
        ).grid(row=0, column=2, sticky="e", padx=(0, PAD_SM), pady=PAD_SM)

        # Format time
        time_str = ""
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%I:%M %p").lstrip("0")
        except (ValueError, TypeError):
            time_str = timestamp

        ctk.CTkLabel(
            self, text=time_str, font=FONT_TINY,
            text_color=TEXT_TERTIARY, anchor="e", width=70,
        ).grid(row=0, column=3, sticky="e", padx=(0, PAD_MD), pady=PAD_SM)


class HistoryPage(ctk.CTkFrame):
    """Usage history timeline with date navigation."""

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

        self._selected_date: date = date.today()
        self._app_rows: list[HistoryAppRow] = []
        self._event_rows: list[BlockedEventRow] = []

        self._build_ui()
        logger.info("History page initialized")

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct the page layout."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Header ───────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=PAD_XL, pady=(PAD_XL, PAD_MD))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=f"{ICONS['history']}  History", font=FONT_TITLE,
            text_color=TEXT_PRIMARY, anchor="w",
        ).grid(row=0, column=0, sticky="w")

        # Date navigation
        nav_frame = ctk.CTkFrame(header, fg_color="transparent")
        nav_frame.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            nav_frame, text=ICONS["arrow_left"], **STYLE_BUTTON_GHOST,
            width=36, command=self._go_prev_day,
        ).grid(row=0, column=0)

        self._date_label = ctk.CTkLabel(
            nav_frame, text="", font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY, width=180, anchor="center",
        )
        self._date_label.grid(row=0, column=1, padx=PAD_XS)
        self._date_label.bind("<Button-1>", self._on_date_clicked)

        ctk.CTkButton(
            nav_frame, text=ICONS["arrow_right"], **STYLE_BUTTON_GHOST,
            width=36, command=self._go_next_day,
        ).grid(row=0, column=2)

        ctk.CTkButton(
            nav_frame, text="Today", **STYLE_BUTTON_SECONDARY, width=70,
            command=self._go_today,
        ).grid(row=0, column=3, padx=(PAD_SM, 0))

        # ── Scrollable body ──────────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, **STYLE_SCROLLABLE_FRAME)
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=PAD_XL, pady=(0, PAD_XL))
        self._scroll.grid_columnconfigure(0, weight=1)

        # Summary card
        self._summary_card = ctk.CTkFrame(self._scroll, **STYLE_CARD)
        self._summary_card.grid(row=0, column=0, sticky="ew", pady=(0, PAD_MD))
        self._summary_card.grid_columnconfigure((0, 1, 2), weight=1)

        self._sum_usage = self._make_summary_item(self._summary_card, "Total Usage", "—", 0)
        self._sum_apps = self._make_summary_item(self._summary_card, "Apps Used", "0", 1)
        self._sum_blocks = self._make_summary_item(self._summary_card, "Blocks", "0", 2)

        # App usage section
        ctk.CTkLabel(
            self._scroll, text="App Usage", font=FONT_HEADING,
            text_color=TEXT_PRIMARY, anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(PAD_SM, PAD_SM))

        self._apps_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._apps_frame.grid(row=2, column=0, sticky="ew", pady=(0, PAD_MD))
        self._apps_frame.grid_columnconfigure(0, weight=1)

        self._apps_empty = ctk.CTkLabel(
            self._apps_frame, text="No usage recorded for this day.",
            font=FONT_BODY, text_color=TEXT_TERTIARY,
        )

        # Blocked events section
        ctk.CTkLabel(
            self._scroll, text="Blocked Events", font=FONT_HEADING,
            text_color=TEXT_PRIMARY, anchor="w",
        ).grid(row=3, column=0, sticky="w", pady=(PAD_SM, PAD_SM))

        self._events_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._events_frame.grid(row=4, column=0, sticky="ew", pady=(0, PAD_XL))
        self._events_frame.grid_columnconfigure(0, weight=1)

        self._events_empty = ctk.CTkLabel(
            self._events_frame, text="No blocked events for this day.",
            font=FONT_BODY, text_color=TEXT_TERTIARY,
        )

    def _make_summary_item(
        self, parent: ctk.CTkFrame, label: str, value: str, col: int,
    ) -> ctk.CTkLabel:
        """Create a summary stat within the summary card and return the value label."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=col, padx=PAD_LG, pady=PAD_LG)

        val_lbl = ctk.CTkLabel(frame, text=value, font=font_bold(22), text_color=TEXT_PRIMARY)
        val_lbl.pack()

        ctk.CTkLabel(frame, text=label, font=FONT_SMALL, text_color=TEXT_SECONDARY).pack()
        return val_lbl

    # ── Date Navigation ───────────────────────────────────────────────────

    def _go_prev_day(self) -> None:
        """Navigate to the previous day."""
        self._selected_date -= timedelta(days=1)
        self.refresh()

    def _go_next_day(self) -> None:
        """Navigate to the next day (capped at today)."""
        new_date = self._selected_date + timedelta(days=1)
        if new_date <= date.today():
            self._selected_date = new_date
        self.refresh()

    def _go_today(self) -> None:
        """Jump to today."""
        self._selected_date = date.today()
        self.refresh()

    def _on_date_clicked(self, event: object = None) -> None:
        """Open a simple date entry dialog when the date label is clicked."""
        dialog = ctk.CTkInputDialog(
            text="Enter date (YYYY-MM-DD):",
            title="Go to Date",
        )
        result = dialog.get_input()
        if result:
            try:
                new_date = date.fromisoformat(result.strip())
                if new_date <= date.today():
                    self._selected_date = new_date
                    self.refresh()
            except ValueError:
                logger.warning(f"Invalid date entered: {result}")

    # ── Data Refresh ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload data for the selected date."""
        date_str = self._selected_date.isoformat()
        display = format_date_display(date_str)
        is_today = self._selected_date == date.today()
        self._date_label.configure(text=f"{display}{'  (Today)' if is_today else ''}")

        self._update_summary(date_str)
        self._update_app_usage(date_str)
        self._update_blocked_events(date_str)

    def _update_summary(self, date_str: str) -> None:
        """Update the daily summary card."""
        if self.db is None:
            self._sum_usage.configure(text="—")
            self._sum_apps.configure(text="0")
            self._sum_blocks.configure(text="0")
            return

        try:
            # Total usage
            row = self.db.fetch_one(
                "SELECT COALESCE(SUM(usage_seconds), 0) as total FROM usage_history WHERE date = ?",
                (date_str,),
            )
            total = row["total"] if row else 0
            self._sum_usage.configure(text=format_duration(total))

            # Apps used
            row = self.db.fetch_one(
                "SELECT COUNT(DISTINCT app_id) as cnt FROM usage_history WHERE date = ? AND usage_seconds > 0",
                (date_str,),
            )
            self._sum_apps.configure(text=str(row["cnt"] if row else 0))

            # Block count
            row = self.db.fetch_one(
                "SELECT COUNT(*) as cnt FROM blocked_events WHERE timestamp LIKE ?",
                (date_str + "%",),
            )
            self._sum_blocks.configure(text=str(row["cnt"] if row else 0))

        except Exception as exc:
            logger.error(f"Error updating history summary: {exc}", exc_info=True)

    def _update_app_usage(self, date_str: str) -> None:
        """Rebuild app usage rows for the selected day."""
        for row_w in self._app_rows:
            row_w.destroy()
        self._app_rows.clear()

        if self.db is None:
            self._show_apps_empty()
            return

        try:
            rows = self.db.fetch_all(
                """SELECT a.name, COALESCE(SUM(uh.usage_seconds), 0) as used_secs,
                          a.daily_limit_seconds
                   FROM applications a
                   LEFT JOIN usage_history uh ON a.id = uh.app_id AND uh.date = ?
                   WHERE a.is_active = 1
                   GROUP BY a.id
                   HAVING used_secs > 0
                   ORDER BY used_secs DESC""",
                (date_str,),
            )

            if not rows:
                self._show_apps_empty()
                return

            self._apps_empty.grid_forget()

            for i, r in enumerate(rows):
                row_w = HistoryAppRow(
                    self._apps_frame,
                    app_name=r["name"],
                    usage_seconds=r["used_secs"],
                    limit_seconds=r["daily_limit_seconds"],
                )
                row_w.grid(row=i, column=0, sticky="ew", pady=(0, PAD_SM))
                self._app_rows.append(row_w)

        except Exception as exc:
            logger.error(f"Error loading history app usage: {exc}", exc_info=True)
            self._show_apps_empty()

    def _show_apps_empty(self) -> None:
        """Show the empty state for app usage."""
        self._apps_empty.grid(row=0, column=0, pady=PAD_LG)

    def _update_blocked_events(self, date_str: str) -> None:
        """Rebuild blocked event rows for the selected day."""
        for row_w in self._event_rows:
            row_w.destroy()
        self._event_rows.clear()

        if self.db is None:
            self._show_events_empty()
            return

        try:
            rows = self.db.fetch_all(
                """SELECT be.app_id, a.name, be.timestamp, be.reason
                   FROM blocked_events be
                   JOIN applications a ON be.app_id = a.id
                   WHERE be.timestamp LIKE ?
                   ORDER BY be.timestamp DESC""",
                (date_str + "%",),
            )

            if not rows:
                self._show_events_empty()
                return

            self._events_empty.grid_forget()

            for i, r in enumerate(rows):
                row_w = BlockedEventRow(
                    self._events_frame,
                    app_name=r["name"],
                    timestamp=r["timestamp"] or "",
                    reason=r["reason"],
                )
                row_w.grid(row=i, column=0, sticky="ew", pady=(0, PAD_SM))
                self._event_rows.append(row_w)

        except Exception as exc:
            logger.error(f"Error loading blocked events: {exc}", exc_info=True)
            self._show_events_empty()

    def _show_events_empty(self) -> None:
        """Show the empty state for blocked events."""
        self._events_empty.grid(row=0, column=0, pady=PAD_LG)

    def destroy(self) -> None:
        """Clean up."""
        super().destroy()
