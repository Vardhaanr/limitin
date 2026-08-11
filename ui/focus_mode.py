"""
Opal Desktop — Focus Mode Page

Allows users to start timed focus sessions that block selected apps.
Features a visual countdown timer, app selector, duration presets,
and session history.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from themes.dark_theme import (
    BG_MID, BG_CARD, BG_CARD_HOVER, BG_ELEVATED, BG_INPUT,
    ACCENT, ACCENT_HOVER, ACCENT_LIGHT, ACCENT_MUTED, ACCENT_SURFACE,
    CYAN, CYAN_LIGHT, GREEN, GREEN_LIGHT, GREEN_MUTED,
    AMBER, AMBER_LIGHT, RED, RED_LIGHT, RED_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY,
    BORDER, BORDER_DIVIDER,
    font, font_bold,
    FONT_TITLE, FONT_HEADING, FONT_SUBHEADING, FONT_BODY, FONT_SMALL,
    PAD_SM, PAD_MD, PAD_LG, PAD_XL, PAD_2XL, PAD_3XL,
    STYLE_CARD, STYLE_BUTTON_PRIMARY, STYLE_BUTTON_SECONDARY,
    STYLE_BUTTON_DANGER, STYLE_SWITCH,
    CARD_CORNER_RADIUS,
)
from utils.helpers import format_duration
from utils.time_utils import now_iso, today_str
from utils.logger import get_logger

if TYPE_CHECKING:
    from database.database import DatabaseManager
    from services.app_tracker import AppTracker

logger = get_logger(__name__)

# Duration presets in seconds
_PRESETS: list[tuple[str, int]] = [
    ("25 min", 25 * 60),
    ("50 min", 50 * 60),
    ("90 min", 90 * 60),
    ("Custom", 0),
]


class FocusModePage(ctk.CTkFrame):
    """Focus mode page with session management and countdown timer."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        db: DatabaseManager | None = None,
        tracker: AppTracker | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color=BG_MID, corner_radius=0, **kwargs)
        self.db = db
        self.tracker = tracker

        # Focus session state
        self._is_active: bool = False
        self._session_start: Optional[float] = None
        self._target_seconds: int = 25 * 60
        self._elapsed_seconds: int = 0
        self._blocked_app_ids: list[int] = []
        self._focus_session_id: Optional[int] = None
        self._timer_job: Optional[str] = None

        # UI state
        self._selected_preset: str = "25 min"
        self._custom_hours: int = 0
        self._custom_minutes: int = 25
        self._app_check_vars: dict[int, ctk.BooleanVar] = {}

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the focus mode page layout."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=PAD_2XL, pady=(PAD_2XL, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Focus Mode",
            font=FONT_TITLE, text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        self._status_label = ctk.CTkLabel(
            header, text="Ready to focus",
            font=font(12), text_color=TEXT_TERTIARY,
        )
        self._status_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Main content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=PAD_2XL, pady=PAD_LG)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)

        # Left column: Timer + Controls
        self._left_col = ctk.CTkFrame(content, fg_color="transparent")
        self._left_col.grid(row=0, column=0, sticky="nsew", padx=(0, PAD_MD))
        self._left_col.grid_rowconfigure(1, weight=1)
        self._left_col.grid_columnconfigure(0, weight=1)

        self._build_timer_area(self._left_col)
        self._build_controls(self._left_col)

        # Right column: App selector + History
        right_col = ctk.CTkFrame(content, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(PAD_MD, 0))
        right_col.grid_rowconfigure(1, weight=1)
        right_col.grid_columnconfigure(0, weight=1)

        self._build_app_selector(right_col)
        self._build_history(right_col)

    def _build_timer_area(self, parent: ctk.CTkFrame) -> None:
        """Build the circular countdown timer area."""
        timer_card = ctk.CTkFrame(parent, **STYLE_CARD)
        timer_card.grid(row=0, column=0, sticky="ew", pady=(0, PAD_MD))
        timer_card.grid_columnconfigure(0, weight=1)

        # Canvas for circular timer
        canvas_size = 220
        self._timer_canvas = ctk.CTkCanvas(
            timer_card, width=canvas_size, height=canvas_size,
            bg=BG_CARD, highlightthickness=0,
        )
        self._timer_canvas.grid(row=0, column=0, pady=PAD_XL)

        # Draw initial timer
        self._draw_timer(1.0)

        # Time display below canvas
        self._time_label = ctk.CTkLabel(
            timer_card, text="25:00",
            font=font_bold(42), text_color=TEXT_PRIMARY,
        )
        self._time_label.grid(row=1, column=0, pady=(0, PAD_SM))

        self._subtitle_label = ctk.CTkLabel(
            timer_card, text="Select duration and start",
            font=font(12), text_color=TEXT_TERTIARY,
        )
        self._subtitle_label.grid(row=2, column=0, pady=(0, PAD_XL))

    def _build_controls(self, parent: ctk.CTkFrame) -> None:
        """Build duration presets and start/stop button."""
        controls_card = ctk.CTkFrame(parent, **STYLE_CARD)
        controls_card.grid(row=1, column=0, sticky="ew")
        controls_card.grid_columnconfigure(0, weight=1)

        # Duration presets
        ctk.CTkLabel(
            controls_card, text="Duration",
            font=font_bold(14), text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=PAD_XL, pady=(PAD_LG, PAD_SM))

        presets_frame = ctk.CTkFrame(controls_card, fg_color="transparent")
        presets_frame.grid(row=1, column=0, sticky="ew", padx=PAD_XL)

        self._preset_buttons: list[ctk.CTkButton] = []
        for i, (label, _seconds) in enumerate(_PRESETS):
            is_selected = label == self._selected_preset
            btn = ctk.CTkButton(
                presets_frame, text=label,
                width=80, height=36,
                fg_color=ACCENT_SURFACE if is_selected else BG_ELEVATED,
                hover_color=ACCENT_MUTED,
                text_color=ACCENT_LIGHT if is_selected else TEXT_SECONDARY,
                corner_radius=8,
                font=font_bold(12) if is_selected else font(12),
                command=lambda l=label, s=_seconds: self._on_preset_select(l, s),
            )
            btn.grid(row=0, column=i, padx=3, pady=PAD_SM)
            self._preset_buttons.append(btn)

        # Custom duration (hidden by default)
        self._custom_frame = ctk.CTkFrame(controls_card, fg_color="transparent")
        self._custom_frame.grid(row=2, column=0, sticky="ew", padx=PAD_XL)

        ctk.CTkLabel(
            self._custom_frame, text="Hours:",
            font=font(12), text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, padx=(0, PAD_SM))

        self._hours_var = ctk.StringVar(value="0")
        ctk.CTkEntry(
            self._custom_frame, textvariable=self._hours_var,
            width=50, height=32, font=font(12),
            fg_color=BG_INPUT, border_color=BORDER,
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=1, padx=(0, PAD_LG))

        ctk.CTkLabel(
            self._custom_frame, text="Minutes:",
            font=font(12), text_color=TEXT_SECONDARY,
        ).grid(row=0, column=2, padx=(0, PAD_SM))

        self._minutes_var = ctk.StringVar(value="25")
        ctk.CTkEntry(
            self._custom_frame, textvariable=self._minutes_var,
            width=50, height=32, font=font(12),
            fg_color=BG_INPUT, border_color=BORDER,
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=3)

        self._custom_frame.grid_remove()  # Hidden initially

        # Start / Stop button
        self._action_btn = ctk.CTkButton(
            controls_card, text="▶  Start Focus Session",
            **STYLE_BUTTON_PRIMARY, width=260,
            command=self._toggle_session,
        )
        self._action_btn.grid(row=3, column=0, pady=(PAD_LG, PAD_XL))

    def _build_app_selector(self, parent: ctk.CTkFrame) -> None:
        """Build the app selection panel."""
        selector_card = ctk.CTkFrame(parent, **STYLE_CARD)
        selector_card.grid(row=0, column=0, sticky="new", pady=(0, PAD_MD))
        selector_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            selector_card, text="Apps to Block",
            font=font_bold(14), text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=PAD_XL, pady=(PAD_LG, PAD_SM))

        ctk.CTkLabel(
            selector_card, text="Select which apps to block during focus",
            font=font(11), text_color=TEXT_TERTIARY,
        ).grid(row=1, column=0, sticky="w", padx=PAD_XL, pady=(0, PAD_SM))

        # App list (scrollable)
        self._app_list_frame = ctk.CTkScrollableFrame(
            selector_card, fg_color="transparent", height=200,
            scrollbar_fg_color=BG_CARD, scrollbar_button_color=BG_ELEVATED,
        )
        self._app_list_frame.grid(row=2, column=0, sticky="ew", padx=PAD_LG, pady=(0, PAD_LG))
        self._app_list_frame.grid_columnconfigure(0, weight=1)

        self._load_apps()

    def _build_history(self, parent: ctk.CTkFrame) -> None:
        """Build the session history panel."""
        history_card = ctk.CTkFrame(parent, **STYLE_CARD)
        history_card.grid(row=1, column=0, sticky="nsew")
        history_card.grid_columnconfigure(0, weight=1)
        history_card.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            history_card, text="Recent Sessions",
            font=font_bold(14), text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=PAD_XL, pady=(PAD_LG, PAD_SM))

        # Stats row
        stats_frame = ctk.CTkFrame(history_card, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", padx=PAD_XL, pady=(0, PAD_SM))

        self._total_focus_label = ctk.CTkLabel(
            stats_frame, text="Total: 0h 0m",
            font=font(11), text_color=ACCENT_LIGHT,
        )
        self._total_focus_label.pack(side="left")

        self._sessions_count_label = ctk.CTkLabel(
            stats_frame, text="  •  0 sessions",
            font=font(11), text_color=TEXT_TERTIARY,
        )
        self._sessions_count_label.pack(side="left")

        # Session list
        self._history_frame = ctk.CTkScrollableFrame(
            history_card, fg_color="transparent",
            scrollbar_fg_color=BG_CARD, scrollbar_button_color=BG_ELEVATED,
        )
        self._history_frame.grid(row=2, column=0, sticky="nsew", padx=PAD_LG, pady=(0, PAD_LG))
        self._history_frame.grid_columnconfigure(0, weight=1)

    # ── Timer drawing ────────────────────────────────────────────────

    def _draw_timer(self, progress: float) -> None:
        """Draw the circular timer arc.

        Args:
            progress: 0.0 (empty) to 1.0 (full circle).
        """
        canvas = self._timer_canvas
        canvas.delete("all")

        size = 220
        cx, cy = size // 2, size // 2
        radius = 90
        thickness = 8

        # Background circle
        canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius,
            outline=BG_ELEVATED, width=thickness,
        )

        # Progress arc
        if progress > 0:
            start_angle = 90  # Start from top
            extent = progress * 360
            color = ACCENT if progress > 0.2 else RED

            canvas.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=start_angle, extent=extent,
                outline=color, width=thickness, style="arc",
            )

        # Center icon
        if self._is_active:
            canvas.create_text(
                cx, cy, text="◉", fill=ACCENT_LIGHT,
                font=(font_bold(24)),
            )
        else:
            canvas.create_text(
                cx, cy, text="◎", fill=TEXT_TERTIARY,
                font=(font_bold(28)),
            )

    # ── App loading ──────────────────────────────────────────────────

    def _load_apps(self) -> None:
        """Load monitored apps into the selector."""
        # Clear existing
        for widget in self._app_list_frame.winfo_children():
            widget.destroy()
        self._app_check_vars.clear()

        if not self.db:
            ctk.CTkLabel(
                self._app_list_frame, text="No apps monitored yet",
                font=font(12), text_color=TEXT_TERTIARY,
            ).grid(row=0, column=0, pady=PAD_LG)
            return

        try:
            apps = self.db.get_all_applications()
            if not apps:
                ctk.CTkLabel(
                    self._app_list_frame, text="No apps monitored yet",
                    font=font(12), text_color=TEXT_TERTIARY,
                ).grid(row=0, column=0, pady=PAD_LG)
                return

            for i, app in enumerate(apps):
                var = ctk.BooleanVar(value=True)  # All selected by default
                self._app_check_vars[app.id] = var

                row_frame = ctk.CTkFrame(self._app_list_frame, fg_color="transparent")
                row_frame.grid(row=i, column=0, sticky="ew", pady=2)
                row_frame.grid_columnconfigure(1, weight=1)

                ctk.CTkCheckBox(
                    row_frame, text=app.name,
                    variable=var, font=font(12),
                    fg_color=BG_ELEVATED, hover_color=ACCENT_MUTED,
                    checkmark_color=ACCENT, text_color=TEXT_PRIMARY,
                    border_color=BORDER,
                ).grid(row=0, column=0, sticky="w")

        except Exception:
            logger.exception("Failed to load apps for focus mode")

    # ── Session control ──────────────────────────────────────────────

    def _toggle_session(self) -> None:
        """Start or stop a focus session."""
        if self._is_active:
            self._stop_session(completed=False)
        else:
            self._start_session()

    def _start_session(self) -> None:
        """Start a new focus session."""
        # Determine duration
        if self._selected_preset == "Custom":
            try:
                hours = int(self._hours_var.get() or 0)
                minutes = int(self._minutes_var.get() or 0)
                self._target_seconds = hours * 3600 + minutes * 60
            except ValueError:
                self._target_seconds = 25 * 60
        else:
            for label, secs in _PRESETS:
                if label == self._selected_preset:
                    self._target_seconds = secs
                    break

        if self._target_seconds <= 0:
            self._target_seconds = 25 * 60

        # Get selected apps
        self._blocked_app_ids = [
            app_id for app_id, var in self._app_check_vars.items()
            if var.get()
        ]

        # Start the session
        self._is_active = True
        self._session_start = time.time()
        self._elapsed_seconds = 0

        # Save to database
        if self.db:
            try:
                from database.models import FocusSession
                session = FocusSession(
                    target_duration_seconds=self._target_seconds,
                    start_time=now_iso(),
                    apps_blocked=json.dumps(self._blocked_app_ids),
                )
                self._focus_session_id = self.db.start_focus_session(session)
            except Exception:
                logger.exception("Failed to save focus session to DB")

        # Update UI
        self._action_btn.configure(
            text="■  End Session",
            fg_color=RED, hover_color=RED_MUTED,
        )
        self._status_label.configure(
            text=f"Focus session active — {len(self._blocked_app_ids)} apps blocked",
            text_color=GREEN,
        )

        # Start countdown
        self._tick_timer()

        logger.info(
            "Focus session started: %d seconds, %d apps blocked",
            self._target_seconds, len(self._blocked_app_ids),
        )

    def _stop_session(self, completed: bool = False) -> None:
        """Stop the current focus session."""
        self._is_active = False

        # Cancel timer
        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None

        # Update database
        if self.db and self._focus_session_id:
            try:
                self.db.end_focus_session(
                    self._focus_session_id,
                    completed=completed,
                    duration=self._elapsed_seconds,
                )
            except Exception:
                logger.exception("Failed to update focus session in DB")

        # Reset UI
        self._action_btn.configure(
            text="▶  Start Focus Session",
            **STYLE_BUTTON_PRIMARY,
        )
        status_text = "Session completed! 🎉" if completed else "Session ended"
        status_color = GREEN if completed else AMBER
        self._status_label.configure(text=status_text, text_color=status_color)

        # Reset timer display
        mins = self._target_seconds // 60
        self._time_label.configure(text=f"{mins:02d}:00")
        self._draw_timer(1.0)

        # Refresh history
        self._load_history()

        logger.info(
            "Focus session %s after %d seconds",
            "completed" if completed else "ended",
            self._elapsed_seconds,
        )

    def _tick_timer(self) -> None:
        """Update the countdown timer every second."""
        if not self._is_active:
            return

        self._elapsed_seconds = int(time.time() - self._session_start)
        remaining = max(0, self._target_seconds - self._elapsed_seconds)

        # Update time display
        mins, secs = divmod(remaining, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            self._time_label.configure(text=f"{hours}:{mins:02d}:{secs:02d}")
        else:
            self._time_label.configure(text=f"{mins:02d}:{secs:02d}")

        # Update subtitle
        self._subtitle_label.configure(
            text=f"{format_duration(remaining)} remaining",
            text_color=TEXT_SECONDARY,
        )

        # Update circular timer
        progress = remaining / self._target_seconds if self._target_seconds > 0 else 0
        self._draw_timer(progress)

        # Check if session is complete
        if remaining <= 0:
            self._stop_session(completed=True)
            return

        # Schedule next tick
        self._timer_job = self.after(1000, self._tick_timer)

    # ── Preset selection ─────────────────────────────────────────────

    def _on_preset_select(self, label: str, seconds: int) -> None:
        """Handle duration preset selection."""
        self._selected_preset = label

        # Update button styles
        for btn in self._preset_buttons:
            btn_text = btn.cget("text")
            if btn_text == label:
                btn.configure(
                    fg_color=ACCENT_SURFACE,
                    text_color=ACCENT_LIGHT,
                    font=font_bold(12),
                )
            else:
                btn.configure(
                    fg_color=BG_ELEVATED,
                    text_color=TEXT_SECONDARY,
                    font=font(12),
                )

        # Show/hide custom duration
        if label == "Custom":
            self._custom_frame.grid()
        else:
            self._custom_frame.grid_remove()
            # Update timer display
            if seconds > 0:
                self._target_seconds = seconds
                mins = seconds // 60
                self._time_label.configure(text=f"{mins:02d}:00")

    # ── History loading ──────────────────────────────────────────────

    def _load_history(self) -> None:
        """Load recent focus sessions into the history panel."""
        for widget in self._history_frame.winfo_children():
            widget.destroy()

        if not self.db:
            return

        try:
            from utils.time_utils import days_ago
            sessions = self.db.get_focus_sessions(days_ago(30), today_str())

            if not sessions:
                ctk.CTkLabel(
                    self._history_frame, text="No sessions yet",
                    font=font(12), text_color=TEXT_TERTIARY,
                ).grid(row=0, column=0, pady=PAD_LG)
                return

            total_seconds = 0
            completed_count = 0

            for i, session in enumerate(reversed(sessions[-10:])):  # Last 10
                total_seconds += session.duration_seconds
                if session.completed:
                    completed_count += 1

                row = ctk.CTkFrame(self._history_frame, fg_color="transparent")
                row.grid(row=i, column=0, sticky="ew", pady=2)
                row.grid_columnconfigure(1, weight=1)

                # Status icon
                icon = "✓" if session.completed else "✕"
                icon_color = GREEN if session.completed else RED_LIGHT
                ctk.CTkLabel(
                    row, text=icon, font=font_bold(12),
                    text_color=icon_color, width=20,
                ).grid(row=0, column=0, padx=(0, PAD_SM))

                # Duration
                ctk.CTkLabel(
                    row, text=format_duration(session.duration_seconds),
                    font=font(12), text_color=TEXT_PRIMARY,
                ).grid(row=0, column=1, sticky="w")

                # Date
                date_text = session.start_time[:10] if session.start_time else ""
                ctk.CTkLabel(
                    row, text=date_text,
                    font=font(11), text_color=TEXT_TERTIARY,
                ).grid(row=0, column=2, sticky="e")

            # Update stats
            self._total_focus_label.configure(
                text=f"Total: {format_duration(total_seconds)}"
            )
            self._sessions_count_label.configure(
                text=f"  •  {completed_count} completed"
            )

        except Exception:
            logger.exception("Failed to load focus session history")

    # ── Refresh ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Refresh app list and history."""
        if not self._is_active:
            self._load_apps()
        self._load_history()
