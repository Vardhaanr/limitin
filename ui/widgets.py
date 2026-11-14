"""
Limitin Desktop — Reusable Widget Components

Production-ready widget library used across all pages. Each widget is a
self-contained class that follows the dark theme and handles its own layout,
events, and state updates.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import customtkinter as ctk

from themes.dark_theme import (
    BG_CARD,
    BG_CARD_HOVER,
    BG_DARKEST,
    BG_ELEVATED,
    BG_INPUT,
    BG_MID,
    ACCENT,
    ACCENT_HOVER,
    ACCENT_LIGHT,
    ACCENT_SURFACE,
    BORDER,
    BORDER_DIVIDER,
    BORDER_FOCUS,
    BORDER_HOVER,
    GREEN,
    GREEN_LIGHT,
    RED,
    RED_LIGHT,
    AMBER,
    TEXT_DISABLED,
    TEXT_INVERSE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    FONT_FAMILY,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
    FONT_SMALL_BOLD,
    FONT_STAT_LABEL,
    FONT_STAT_VALUE,
    FONT_SUBHEADING,
    FONT_TINY,
    CARD_CORNER_RADIUS,
    BUTTON_CORNER_RADIUS,
    PAD_XS,
    PAD_SM,
    PAD_MD,
    PAD_LG,
    PAD_XL,
    PAD_2XL,
    STYLE_CARD,
    STYLE_BUTTON_GHOST,
    STYLE_BUTTON_PRIMARY,
    STYLE_BUTTON_SECONDARY,
    STYLE_INPUT,
    STYLE_SIDEBAR_BUTTON,
    STYLE_SIDEBAR_BUTTON_ACTIVE,
    ICONS,
    font,
    font_bold,
    get_usage_color,
    get_status_badge_colors,
)
from database.models import Application

logger = logging.getLogger("limitin.ui.widgets")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _format_seconds(seconds: int) -> str:
    """Format seconds into a human-readable 'Xh Ym' string.

    Args:
        seconds: Total seconds to format.

    Returns:
        Formatted time string, e.g. '2h 15m', '45m', '0m'.
    """
    if seconds < 0:
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


# ── StatCard ──────────────────────────────────────────────────────────────────


class StatCard(ctk.CTkFrame):
    """Dashboard stat card with icon, label, value, and optional trend.

    Displays a key metric in a rounded card with a large value, supporting
    icon, descriptive label, and optional trend indicator (arrow + text).

    Args:
        master: Parent widget.
        icon: Emoji or unicode character displayed top-left.
        label: Descriptive label shown below the value.
        value: The primary metric text (default '0').
        trend: Optional trend string, e.g. '+12%'.
        trend_positive: Whether the trend is positive (green) or negative (red).
        **kwargs: Additional CTkFrame keyword arguments.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        icon: str,
        label: str,
        value: str = "0",
        trend: Optional[str] = None,
        trend_positive: bool = True,
        **kwargs,
    ) -> None:
        merged_kwargs = {**STYLE_CARD, **kwargs}
        super().__init__(master, **merged_kwargs)

        self._icon_text = icon
        self._label_text = label
        self._trend_text = trend
        self._trend_positive = trend_positive

        # Configure grid: single column, rows stretch as needed
        self.grid_columnconfigure(0, weight=1)

        # ── Row 0: Icon ──────────────────────────────────────────────────
        self._icon_label = ctk.CTkLabel(
            self,
            text=icon,
            font=font_bold(22),
            text_color=ACCENT_LIGHT,
            anchor="w",
            fg_color="transparent",
        )
        self._icon_label.grid(
            row=0, column=0, sticky="w", padx=PAD_LG, pady=(PAD_LG, PAD_XS)
        )

        # ── Row 1: Value (large bold) ────────────────────────────────────
        self._value_label = ctk.CTkLabel(
            self,
            text=value,
            font=FONT_STAT_VALUE,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        )
        self._value_label.grid(
            row=1, column=0, sticky="w", padx=PAD_LG, pady=(PAD_XS, 0)
        )

        # ── Row 2: Label (small secondary) ──────────────────────────────
        self._label_label = ctk.CTkLabel(
            self,
            text=label,
            font=FONT_STAT_LABEL,
            text_color=TEXT_SECONDARY,
            anchor="w",
            fg_color="transparent",
        )
        self._label_label.grid(
            row=2, column=0, sticky="w", padx=PAD_LG, pady=(PAD_XS, PAD_SM)
        )

        # ── Row 3: Trend (bottom, right-aligned) ────────────────────────
        self._trend_label = ctk.CTkLabel(
            self,
            text="",
            font=FONT_TINY,
            text_color=GREEN_LIGHT if trend_positive else RED_LIGHT,
            anchor="e",
            fg_color="transparent",
        )
        self._trend_label.grid(
            row=3, column=0, sticky="e", padx=PAD_LG, pady=(0, PAD_LG)
        )
        if trend is not None:
            self.set_trend(trend, trend_positive)

        logger.debug("StatCard created: icon=%s, label=%s", icon, label)

    def set_value(self, value: str) -> None:
        """Update the primary metric value.

        Args:
            value: New value string to display.
        """
        try:
            self._value_label.configure(text=value)
        except Exception:
            logger.exception("Failed to set StatCard value to '%s'", value)

    def set_trend(self, trend: str, positive: bool = True) -> None:
        """Update the trend indicator text and color.

        Args:
            trend: Trend string, e.g. '+12%' or '-3%'.
            positive: True for green (good), False for red (bad).
        """
        try:
            arrow = "↑" if positive else "↓"
            color = GREEN_LIGHT if positive else RED_LIGHT
            self._trend_label.configure(text=f"{arrow} {trend}", text_color=color)
            self._trend_positive = positive
            self._trend_text = trend
        except Exception:
            logger.exception("Failed to set StatCard trend to '%s'", trend)


# ── ProgressCard ──────────────────────────────────────────────────────────────


class ProgressCard(ctk.CTkFrame):
    """App usage card with icon, name, progress bar, and time info.

    Shows a monitored application's current usage relative to its daily limit,
    with a color-coded progress bar and status badge.

    Args:
        master: Parent widget.
        app_name: Display name of the application.
        icon_image: Optional CTkImage for the app icon.
        usage_seconds: Current usage in seconds.
        limit_seconds: Daily limit in seconds.
        status: Current status string ('active', 'blocked', 'paused', 'idle', 'warning').
        on_click: Optional callback when the card is clicked.
        **kwargs: Additional CTkFrame keyword arguments.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        app_name: str,
        icon_image: Optional[ctk.CTkImage] = None,
        usage_seconds: int = 0,
        limit_seconds: int = 3600,
        status: str = "idle",
        on_click: Optional[callable] = None,
        **kwargs,
    ) -> None:
        merged_kwargs = {**STYLE_CARD, **kwargs}
        super().__init__(master, **merged_kwargs)

        self._app_name = app_name
        self._usage_seconds = usage_seconds
        self._limit_seconds = max(limit_seconds, 1)  # prevent division by zero
        self._status = status
        self._on_click = on_click

        self.grid_columnconfigure(1, weight=1)

        # ── Icon (column 0) ──────────────────────────────────────────────
        if icon_image is not None:
            self._icon_label = ctk.CTkLabel(
                self, image=icon_image, text="", fg_color="transparent"
            )
        else:
            self._icon_label = ctk.CTkLabel(
                self,
                text="⊞",
                font=font_bold(20),
                text_color=TEXT_SECONDARY,
                width=36,
                height=36,
                fg_color="transparent",
            )
        self._icon_label.grid(
            row=0, column=0, rowspan=3, padx=(PAD_LG, PAD_SM), pady=PAD_LG, sticky="n"
        )

        # ── Top row: App name + status badge (column 1) ─────────────────
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.grid(row=0, column=1, sticky="ew", padx=(0, PAD_LG), pady=(PAD_LG, 0))
        top_row.grid_columnconfigure(0, weight=1)

        self._name_label = ctk.CTkLabel(
            top_row,
            text=app_name,
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        )
        self._name_label.grid(row=0, column=0, sticky="w")

        self._status_badge = StatusBadge(top_row, status=status)
        self._status_badge.grid(row=0, column=1, sticky="e", padx=(PAD_SM, 0))

        # ── Middle row: Usage / limit text ───────────────────────────────
        usage_text = f"{_format_seconds(usage_seconds)} / {_format_seconds(limit_seconds)}"
        self._usage_label = ctk.CTkLabel(
            self,
            text=usage_text,
            font=FONT_SMALL,
            text_color=TEXT_SECONDARY,
            anchor="w",
            fg_color="transparent",
        )
        self._usage_label.grid(
            row=1, column=1, sticky="ew", padx=(0, PAD_LG), pady=(PAD_XS, PAD_SM)
        )

        # ── Bottom row: Progress bar ────────────────────────────────────
        percentage = min(usage_seconds / self._limit_seconds, 1.0)
        bar_color = get_usage_color(usage_seconds / self._limit_seconds)
        self._progress_bar = AnimatedProgressBar(
            self, height=6, color=bar_color, bg_color=BG_ELEVATED
        )
        self._progress_bar.grid(
            row=2, column=1, sticky="ew", padx=(0, PAD_LG), pady=(0, PAD_LG)
        )
        self._progress_bar.set_progress(percentage, animate=False)

        # ── Click binding ───────────────────────────────────────────────
        if on_click is not None:
            for widget in (self, self._icon_label, self._name_label, self._usage_label):
                widget.bind("<Button-1>", lambda _e: on_click())
                widget.configure(cursor="hand2")

        logger.debug("ProgressCard created: app=%s", app_name)

    def update_usage(
        self, usage_seconds: int, limit_seconds: int, status: str
    ) -> None:
        """Refresh all displayed data with new values.

        Args:
            usage_seconds: Current usage in seconds.
            limit_seconds: Daily limit in seconds.
            status: New status string.
        """
        try:
            self._usage_seconds = usage_seconds
            self._limit_seconds = max(limit_seconds, 1)
            self._status = status

            # Update text
            usage_text = f"{_format_seconds(usage_seconds)} / {_format_seconds(limit_seconds)}"
            self._usage_label.configure(text=usage_text)

            # Update badge
            self._status_badge.set_status(status)

            # Update progress
            raw_pct = usage_seconds / self._limit_seconds
            clamped_pct = min(raw_pct, 1.0)
            bar_color = get_usage_color(raw_pct)
            self._progress_bar.set_color(bar_color)
            self._progress_bar.set_progress(clamped_pct, animate=True)
        except Exception:
            logger.exception(
                "Failed to update ProgressCard for '%s'", self._app_name
            )


# ── AppListItem ───────────────────────────────────────────────────────────────


class AppListItem(ctk.CTkFrame):
    """Row in the app list with icon, name, limit, usage, and action buttons.

    Provides a compact horizontal layout for a monitored application with
    hover effects and inline edit/delete buttons.

    Args:
        master: Parent widget.
        app: Application dataclass instance.
        usage_seconds: Today's usage in seconds.
        on_edit: Optional callback(app) when edit button is clicked.
        on_delete: Optional callback(app) when delete button is clicked.
        **kwargs: Additional CTkFrame keyword arguments.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        app: Application,
        usage_seconds: int = 0,
        on_edit: Optional[callable] = None,
        on_delete: Optional[callable] = None,
        **kwargs,
    ) -> None:
        merged_kwargs = {
            "fg_color": BG_CARD,
            "corner_radius": CARD_CORNER_RADIUS,
            "border_width": 1,
            "border_color": BORDER,
            **kwargs,
        }
        super().__init__(master, **merged_kwargs)

        self._app = app
        self._usage_seconds = usage_seconds
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._default_fg = merged_kwargs["fg_color"]

        self.grid_columnconfigure(1, weight=1)

        # ── Column 0: Icon ───────────────────────────────────────────────
        icon_text = "⊞"
        self._icon_label = ctk.CTkLabel(
            self,
            text=icon_text,
            font=font_bold(18),
            text_color=ACCENT_LIGHT,
            width=36,
            height=36,
            fg_color="transparent",
        )
        self._icon_label.grid(
            row=0, column=0, padx=(PAD_MD, PAD_SM), pady=PAD_SM, sticky="w"
        )

        # ── Column 1: Name + exe path ───────────────────────────────────
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", pady=PAD_SM)
        info_frame.grid_columnconfigure(0, weight=1)

        self._name_label = ctk.CTkLabel(
            info_frame,
            text=app.name,
            font=FONT_BODY_BOLD,
            text_color=TEXT_PRIMARY,
            anchor="w",
            fg_color="transparent",
        )
        self._name_label.grid(row=0, column=0, sticky="w")

        self._path_label = ctk.CTkLabel(
            info_frame,
            text=app.exe_name,
            font=FONT_TINY,
            text_color=TEXT_TERTIARY,
            anchor="w",
            fg_color="transparent",
        )
        self._path_label.grid(row=1, column=0, sticky="w")

        # ── Column 2: Daily limit ───────────────────────────────────────
        limit_text = _format_seconds(app.daily_limit_seconds)
        self._limit_label = ctk.CTkLabel(
            self,
            text=f"Limit: {limit_text}",
            font=FONT_SMALL,
            text_color=TEXT_SECONDARY,
            width=90,
            anchor="center",
            fg_color="transparent",
        )
        self._limit_label.grid(row=0, column=2, padx=PAD_SM, pady=PAD_SM)

        # ── Column 3: Today's usage ─────────────────────────────────────
        usage_pct = (
            usage_seconds / app.daily_limit_seconds
            if app.daily_limit_seconds > 0
            else 0.0
        )
        usage_color = get_usage_color(usage_pct)
        self._usage_label = ctk.CTkLabel(
            self,
            text=_format_seconds(usage_seconds),
            font=FONT_SMALL_BOLD,
            text_color=usage_color,
            width=70,
            anchor="center",
            fg_color="transparent",
        )
        self._usage_label.grid(row=0, column=3, padx=PAD_SM, pady=PAD_SM)

        # ── Column 4: Edit button ───────────────────────────────────────
        self._edit_btn = ctk.CTkButton(
            self,
            text=ICONS.get("edit", "✎"),
            width=32,
            height=32,
            command=lambda: self._handle_edit(),
            **STYLE_BUTTON_GHOST,
        )
        self._edit_btn.grid(row=0, column=4, padx=(PAD_XS, 0), pady=PAD_SM)

        # ── Column 5: Delete button ─────────────────────────────────────
        self._delete_btn = ctk.CTkButton(
            self,
            text=ICONS.get("delete", "✕"),
            width=32,
            height=32,
            text_color=RED_LIGHT,
            command=lambda: self._handle_delete(),
            **{k: v for k, v in STYLE_BUTTON_GHOST.items() if k != "text_color"},
        )
        self._delete_btn.grid(
            row=0, column=5, padx=(0, PAD_MD), pady=PAD_SM
        )

        # ── Hover effects ───────────────────────────────────────────────
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        # Also bind children so hover doesn't flicker
        for child in (
            self._icon_label,
            info_frame,
            self._name_label,
            self._path_label,
            self._limit_label,
            self._usage_label,
        ):
            child.bind("<Enter>", self._on_enter)
            child.bind("<Leave>", self._on_leave)

        logger.debug("AppListItem created: app=%s (id=%s)", app.name, app.id)

    # ── Event handlers ───────────────────────────────────────────────────

    def _on_enter(self, _event: object) -> None:
        """Highlight the row on mouse enter."""
        try:
            self.configure(fg_color=BG_CARD_HOVER, border_color=BORDER_HOVER)
        except Exception:
            pass

    def _on_leave(self, _event: object) -> None:
        """Restore the row on mouse leave."""
        try:
            self.configure(fg_color=self._default_fg, border_color=BORDER)
        except Exception:
            pass

    def _handle_edit(self) -> None:
        """Invoke the edit callback with the application."""
        if self._on_edit is not None:
            try:
                self._on_edit(self._app)
            except Exception:
                logger.exception("Error in on_edit callback for '%s'", self._app.name)

    def _handle_delete(self) -> None:
        """Invoke the delete callback with the application."""
        if self._on_delete is not None:
            try:
                self._on_delete(self._app)
            except Exception:
                logger.exception(
                    "Error in on_delete callback for '%s'", self._app.name
                )

    def update_data(self, usage_seconds: int) -> None:
        """Refresh usage display with new data.

        Args:
            usage_seconds: Updated usage in seconds.
        """
        try:
            self._usage_seconds = usage_seconds
            usage_pct = (
                usage_seconds / self._app.daily_limit_seconds
                if self._app.daily_limit_seconds > 0
                else 0.0
            )
            usage_color = get_usage_color(usage_pct)
            self._usage_label.configure(
                text=_format_seconds(usage_seconds), text_color=usage_color
            )
        except Exception:
            logger.exception(
                "Failed to update AppListItem for '%s'", self._app.name
            )


# ── SidebarButton ─────────────────────────────────────────────────────────────


class SidebarButton(ctk.CTkFrame):
    """Navigation button for the sidebar with text-only label and active state.

    Built as a CTkFrame with a CTkLabel to avoid CTkButton's text duplication
    bug when reconfiguring font/anchor repeatedly.

    Args:
        master: Parent widget.
        icon: Unused (kept for API compatibility).
        text: Button label text.
        command: Callback when clicked.
        **kwargs: Additional CTkFrame keyword arguments.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        icon: str,
        text: str,
        command: Optional[callable] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color="transparent",
            corner_radius=BUTTON_CORNER_RADIUS,
            height=40,
            cursor="hand2",
            **kwargs,
        )
        self.pack_propagate(False)

        self._command = command
        self._label_text = text
        self._is_active = False

        self._label = ctk.CTkLabel(
            self,
            text=f"  {text}",
            font=font(13),
            text_color=TEXT_SECONDARY,
            anchor="w",
            fg_color="transparent",
            cursor="hand2",
        )
        self._label.pack(fill="both", expand=True, padx=PAD_XS, pady=2)

        # Bind click on both frame and label
        self.bind("<Button-1>", self._on_click)
        self._label.bind("<Button-1>", self._on_click)

        # Hover effects
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._label.bind("<Enter>", self._on_enter)
        self._label.bind("<Leave>", self._on_leave)

    def _on_click(self, _event: object = None) -> None:
        """Handle click."""
        if self._command:
            self._command()

    def _on_enter(self, _event: object = None) -> None:
        """Hover in."""
        if not self._is_active:
            self.configure(fg_color=BG_CARD)

    def _on_leave(self, _event: object = None) -> None:
        """Hover out."""
        if not self._is_active:
            self.configure(fg_color="transparent")

    def set_active(self, active: bool) -> None:
        """Toggle between active and inactive visual state.

        Args:
            active: True to show active styling, False for inactive.
        """
        try:
            self._is_active = active
            if active:
                self.configure(fg_color=ACCENT_SURFACE)
                self._label.configure(
                    text_color=ACCENT_LIGHT,
                    font=font_bold(13),
                )
            else:
                self.configure(fg_color="transparent")
                self._label.configure(
                    text_color=TEXT_SECONDARY,
                    font=font(13),
                )
        except Exception:
            logger.exception("Failed to set SidebarButton active state")


# ── SearchBar ─────────────────────────────────────────────────────────────────


class SearchBar(ctk.CTkFrame):
    """Search input with magnifying-glass icon.

    Compact search bar that fires an on_change callback when the user types.

    Args:
        master: Parent widget.
        placeholder: Placeholder text for the input.
        on_change: Optional callback(query: str) fired on every keystroke.
        **kwargs: Additional CTkFrame keyword arguments.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        placeholder: str = "Search...",
        on_change: Optional[callable] = None,
        **kwargs,
    ) -> None:
        frame_kwargs = {
            "fg_color": BG_INPUT,
            "corner_radius": BUTTON_CORNER_RADIUS,
            "border_width": 1,
            "border_color": BORDER,
            **kwargs,
        }
        super().__init__(master, **frame_kwargs)
        self._on_change = on_change

        self.grid_columnconfigure(1, weight=1)

        # ── Icon ─────────────────────────────────────────────────────────
        icon_label = ctk.CTkLabel(
            self,
            text=ICONS.get("search", "⌕"),
            font=font(14),
            text_color=TEXT_TERTIARY,
            width=30,
            fg_color="transparent",
        )
        icon_label.grid(row=0, column=0, padx=(PAD_SM, 0), pady=PAD_XS)

        # ── Entry ────────────────────────────────────────────────────────
        self._entry = ctk.CTkEntry(
            self,
            placeholder_text=placeholder,
            fg_color="transparent",
            border_width=0,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_TERTIARY,
            font=FONT_BODY,
            height=32,
        )
        self._entry.grid(
            row=0, column=1, sticky="ew", padx=(0, PAD_SM), pady=PAD_XS
        )

        # Bind key release to trigger on_change
        self._entry.bind("<KeyRelease>", self._handle_key)

        # Focus effects on the outer frame
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)

    def _handle_key(self, _event: object) -> None:
        """Fire the on_change callback with the current query."""
        if self._on_change is not None:
            try:
                self._on_change(self.get_query())
            except Exception:
                logger.exception("Error in SearchBar on_change callback")

    def _on_focus_in(self, _event: object) -> None:
        """Highlight border when focused."""
        try:
            self.configure(border_color=BORDER_FOCUS)
        except Exception:
            pass

    def _on_focus_out(self, _event: object) -> None:
        """Restore border when unfocused."""
        try:
            self.configure(border_color=BORDER)
        except Exception:
            pass

    def get_query(self) -> str:
        """Return the current text in the search field.

        Returns:
            The search query string.
        """
        try:
            return self._entry.get().strip()
        except Exception:
            logger.exception("Failed to get SearchBar query")
            return ""

    def clear(self) -> None:
        """Clear the search field."""
        try:
            self._entry.delete(0, "end")
            if self._on_change is not None:
                self._on_change("")
        except Exception:
            logger.exception("Failed to clear SearchBar")


# ── AnimatedProgressBar ───────────────────────────────────────────────────────


class AnimatedProgressBar(ctk.CTkFrame):
    """Progress bar with smooth animation using a canvas.

    Draws a rounded rectangle that fills from left to right. Supports
    smooth interpolation when the value changes.

    Args:
        master: Parent widget.
        height: Bar height in pixels.
        color: Fill color of the progress portion.
        bg_color: Background color of the bar track.
        **kwargs: Additional CTkFrame keyword arguments.
    """

    _ANIMATION_DURATION_MS: int = 300
    _ANIMATION_STEP_MS: int = 16  # ~60fps

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        height: int = 6,
        color: str = ACCENT,
        bg_color: str = BG_ELEVATED,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", height=height, **kwargs)

        self._bar_height = height
        self._color = color
        self._bg_color = bg_color
        self._current_value: float = 0.0
        self._target_value: float = 0.0
        self._animation_id: str | None = None

        self._canvas = ctk.CTkCanvas(
            self,
            height=height,
            highlightthickness=0,
            bg=self._get_tk_bg(),
        )
        self._canvas.pack(fill="x", expand=True)
        self._canvas.bind("<Configure>", self._on_resize)

    def _get_tk_bg(self) -> str:
        """Get the background color for the canvas.

        Returns:
            A hex color string compatible with tkinter canvas.
        """
        # Use the parent frame's bg_color for seamless blending
        try:
            parent_fg = self.master.cget("fg_color")
            if isinstance(parent_fg, (list, tuple)):
                return parent_fg[-1]
            if parent_fg and parent_fg != "transparent":
                return parent_fg
        except Exception:
            pass
        return BG_CARD

    def _on_resize(self, _event: object) -> None:
        """Redraw when the canvas is resized."""
        self._draw()

    def _draw(self) -> None:
        """Render the progress bar on the canvas."""
        try:
            self._canvas.delete("all")
            w = self._canvas.winfo_width()
            h = self._bar_height
            radius = h // 2

            if w <= 0:
                return

            # Background track
            self._draw_rounded_rect(0, 0, w, h, radius, self._bg_color)

            # Filled portion
            fill_width = int(w * self._current_value)
            if fill_width > 0:
                fill_width = max(fill_width, radius * 2)  # minimum visible size
                self._draw_rounded_rect(0, 0, fill_width, h, radius, self._color)
        except Exception:
            logger.exception("Failed to draw AnimatedProgressBar")

    def _draw_rounded_rect(
        self, x1: int, y1: int, x2: int, y2: int, radius: int, color: str
    ) -> None:
        """Draw a rounded rectangle on the canvas.

        Args:
            x1, y1: Top-left corner.
            x2, y2: Bottom-right corner.
            radius: Corner radius in pixels.
            color: Fill color.
        """
        r = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
        self._canvas.create_arc(
            x1, y1, x1 + 2 * r, y1 + 2 * r,
            start=90, extent=90, fill=color, outline=color,
        )
        self._canvas.create_arc(
            x2 - 2 * r, y1, x2, y1 + 2 * r,
            start=0, extent=90, fill=color, outline=color,
        )
        self._canvas.create_arc(
            x1, y2 - 2 * r, x1 + 2 * r, y2,
            start=180, extent=90, fill=color, outline=color,
        )
        self._canvas.create_arc(
            x2 - 2 * r, y2 - 2 * r, x2, y2,
            start=270, extent=90, fill=color, outline=color,
        )
        # Fill the center rectangles
        self._canvas.create_rectangle(
            x1 + r, y1, x2 - r, y2, fill=color, outline=color
        )
        self._canvas.create_rectangle(
            x1, y1 + r, x1 + r, y2 - r, fill=color, outline=color
        )
        self._canvas.create_rectangle(
            x2 - r, y1 + r, x2, y2 - r, fill=color, outline=color
        )

    def set_progress(self, value: float, animate: bool = True) -> None:
        """Set progress from 0.0 to 1.0 with optional smooth animation.

        Args:
            value: Target progress value, clamped to [0.0, 1.0].
            animate: Whether to smoothly interpolate (True) or jump instantly.
        """
        value = max(0.0, min(1.0, value))
        self._target_value = value

        if not animate or abs(self._current_value - value) < 0.005:
            self._current_value = value
            self._draw()
            return

        self._animate_to(value)

    def _animate_to(self, target: float) -> None:
        """Smoothly animate progress bar fill to the target value.

        Uses self.after() to interpolate over ~300ms at ~60fps.

        Args:
            target: The target progress value.
        """
        # Cancel any pending animation
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except Exception:
                pass
            self._animation_id = None

        total_steps = max(1, self._ANIMATION_DURATION_MS // self._ANIMATION_STEP_MS)
        step_delta = (target - self._current_value) / total_steps
        steps_remaining = total_steps

        def _step() -> None:
            nonlocal steps_remaining
            try:
                if steps_remaining <= 1 or not self.winfo_exists():
                    self._current_value = self._target_value
                    self._draw()
                    self._animation_id = None
                    return

                self._current_value += step_delta
                steps_remaining -= 1
                self._draw()
                self._animation_id = self.after(self._ANIMATION_STEP_MS, _step)
            except Exception:
                # Widget may have been destroyed during animation
                self._animation_id = None

        _step()

    def set_color(self, color: str) -> None:
        """Change the progress fill color.

        Args:
            color: New hex color string.
        """
        self._color = color
        self._draw()


# ── StatusBadge ───────────────────────────────────────────────────────────────


class StatusBadge(ctk.CTkLabel):
    """Small colored badge showing status text.

    Renders a compact, rounded label with colors based on the status.

    Args:
        master: Parent widget.
        status: Initial status ('active', 'blocked', 'paused', 'idle', 'warning').
        **kwargs: Additional CTkLabel keyword arguments.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        status: str = "idle",
        **kwargs,
    ) -> None:
        bg_color, text_color = get_status_badge_colors(status)
        default_kwargs = {
            "text": status.capitalize(),
            "font": FONT_TINY,
            "text_color": text_color,
            "fg_color": bg_color,
            "corner_radius": 6,
            "height": 22,
            "width": 60,
        }
        default_kwargs.update(kwargs)
        super().__init__(master, **default_kwargs)
        self._status = status

    def set_status(self, status: str) -> None:
        """Update status text and colors.

        Args:
            status: One of 'active', 'blocked', 'paused', 'idle', 'warning'.
        """
        try:
            self._status = status
            bg_color, text_color = get_status_badge_colors(status)
            self.configure(
                text=status.capitalize(),
                text_color=text_color,
                fg_color=bg_color,
            )
        except Exception:
            logger.exception("Failed to set StatusBadge status to '%s'", status)


# ── TimePicker ────────────────────────────────────────────────────────────────


class TimePicker(ctk.CTkFrame):
    """Hours and minutes input with spinbox-style +/- controls.

    Provides a compact time picker with increment/decrement buttons for
    hours and minutes, suitable for setting daily limits.

    Args:
        master: Parent widget.
        initial_hours: Starting hours value (0–23).
        initial_minutes: Starting minutes value (0–59).
        on_change: Optional callback() fired when the value changes.
        **kwargs: Additional CTkFrame keyword arguments.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        initial_hours: int = 1,
        initial_minutes: int = 0,
        on_change: Optional[callable] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._hours = max(0, min(23, initial_hours))
        self._minutes = max(0, min(59, initial_minutes))
        self._on_change = on_change

        # ── Hours spinner ────────────────────────────────────────────────
        self._hours_up = ctk.CTkButton(
            self, text="▲", width=28, height=22, font=font(10),
            fg_color=BG_ELEVATED, hover_color=BG_CARD_HOVER,
            text_color=TEXT_SECONDARY, corner_radius=4,
            command=lambda: self._adjust("hours", 1),
        )
        self._hours_up.grid(row=0, column=0, padx=1, pady=(0, 1))

        self._hours_label = ctk.CTkLabel(
            self,
            text=str(self._hours).zfill(2),
            font=font_bold(18),
            text_color=TEXT_PRIMARY,
            width=36,
            height=30,
            fg_color=BG_INPUT,
            corner_radius=4,
        )
        self._hours_label.grid(row=1, column=0, padx=1)

        self._hours_down = ctk.CTkButton(
            self, text="▼", width=28, height=22, font=font(10),
            fg_color=BG_ELEVATED, hover_color=BG_CARD_HOVER,
            text_color=TEXT_SECONDARY, corner_radius=4,
            command=lambda: self._adjust("hours", -1),
        )
        self._hours_down.grid(row=2, column=0, padx=1, pady=(1, 0))

        # ── 'h' label ───────────────────────────────────────────────────
        ctk.CTkLabel(
            self, text="h", font=FONT_BODY, text_color=TEXT_SECONDARY,
            fg_color="transparent",
        ).grid(row=1, column=1, padx=(PAD_XS, PAD_SM))

        # ── Minutes spinner ──────────────────────────────────────────────
        self._minutes_up = ctk.CTkButton(
            self, text="▲", width=28, height=22, font=font(10),
            fg_color=BG_ELEVATED, hover_color=BG_CARD_HOVER,
            text_color=TEXT_SECONDARY, corner_radius=4,
            command=lambda: self._adjust("minutes", 5),
        )
        self._minutes_up.grid(row=0, column=2, padx=1, pady=(0, 1))

        self._minutes_label = ctk.CTkLabel(
            self,
            text=str(self._minutes).zfill(2),
            font=font_bold(18),
            text_color=TEXT_PRIMARY,
            width=36,
            height=30,
            fg_color=BG_INPUT,
            corner_radius=4,
        )
        self._minutes_label.grid(row=1, column=2, padx=1)

        self._minutes_down = ctk.CTkButton(
            self, text="▼", width=28, height=22, font=font(10),
            fg_color=BG_ELEVATED, hover_color=BG_CARD_HOVER,
            text_color=TEXT_SECONDARY, corner_radius=4,
            command=lambda: self._adjust("minutes", -5),
        )
        self._minutes_down.grid(row=2, column=2, padx=1, pady=(1, 0))

        # ── 'm' label ───────────────────────────────────────────────────
        ctk.CTkLabel(
            self, text="m", font=FONT_BODY, text_color=TEXT_SECONDARY,
            fg_color="transparent",
        ).grid(row=1, column=3, padx=(PAD_XS, 0))

    def _adjust(self, field: str, delta: int) -> None:
        """Increment or decrement hours or minutes and notify.

        Args:
            field: 'hours' or 'minutes'.
            delta: Amount to add (positive or negative).
        """
        try:
            if field == "hours":
                self._hours = max(0, min(23, self._hours + delta))
                self._hours_label.configure(text=str(self._hours).zfill(2))
            else:
                self._minutes = max(0, min(59, self._minutes + delta))
                self._minutes_label.configure(text=str(self._minutes).zfill(2))

            if self._on_change is not None:
                self._on_change()
        except Exception:
            logger.exception("Failed to adjust TimePicker %s by %d", field, delta)

    def get_total_seconds(self) -> int:
        """Return the current time value in total seconds.

        Returns:
            Total seconds for the configured hours and minutes.
        """
        return self._hours * 3600 + self._minutes * 60

    def set_time(self, hours: int, minutes: int) -> None:
        """Set the displayed time.

        Args:
            hours: Hours value (0–23).
            minutes: Minutes value (0–59).
        """
        try:
            self._hours = max(0, min(23, hours))
            self._minutes = max(0, min(59, minutes))
            self._hours_label.configure(text=str(self._hours).zfill(2))
            self._minutes_label.configure(text=str(self._minutes).zfill(2))
        except Exception:
            logger.exception("Failed to set TimePicker to %d:%d", hours, minutes)


# ── Tooltip ───────────────────────────────────────────────────────────────────


class Tooltip:
    """Hover tooltip for any widget.

    Shows a small, borderless popup after a configurable delay when the user
    hovers over the associated widget.

    Args:
        widget: The widget to attach the tooltip to.
        text: Tooltip text content.
        delay: Milliseconds to wait before showing the tooltip.
    """

    def __init__(
        self,
        widget: ctk.CTkBaseClass,
        text: str,
        delay: int = 500,
    ) -> None:
        self._widget = widget
        self._text = text
        self._delay = delay
        self._tooltip_window: ctk.CTkToplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event: object) -> None:
        """Schedule tooltip display after the configured delay."""
        self._cancel_pending()
        self._after_id = self._widget.after(self._delay, self.show)

    def _on_leave(self, _event: object) -> None:
        """Cancel pending tooltip and hide any visible one."""
        self._cancel_pending()
        self.hide()

    def _cancel_pending(self) -> None:
        """Cancel any pending after() callback."""
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def show(self) -> None:
        """Display the tooltip near the widget."""
        self.hide()
        try:
            if not self._widget.winfo_exists():
                return

            x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4

            self._tooltip_window = tw = ctk.CTkToplevel(self._widget)
            tw.wm_overrideredirect(True)
            tw.wm_attributes("-topmost", True)
            tw.configure(fg_color=BG_ELEVATED)

            # On Windows, remove any potential window shadow/flash
            try:
                tw.wm_attributes("-toolwindow", True)
            except Exception:
                pass

            label = ctk.CTkLabel(
                tw,
                text=self._text,
                font=FONT_SMALL,
                text_color=TEXT_PRIMARY,
                fg_color=BG_ELEVATED,
                corner_radius=6,
                padx=PAD_SM,
                pady=PAD_XS,
            )
            label.pack()

            # Update geometry so we can read the label's size
            tw.update_idletasks()
            tw_width = tw.winfo_width()
            tw_height = tw.winfo_height()

            # Center the tooltip horizontally on the widget
            tooltip_x = x - tw_width // 2
            tooltip_y = y

            tw.wm_geometry(f"+{tooltip_x}+{tooltip_y}")
        except Exception:
            # Widget may have been destroyed before tooltip was shown
            self._tooltip_window = None

    def hide(self) -> None:
        """Remove the tooltip from screen."""
        if self._tooltip_window is not None:
            try:
                self._tooltip_window.destroy()
            except Exception:
                pass
            self._tooltip_window = None

    def update_text(self, text: str) -> None:
        """Change the tooltip text.

        Args:
            text: New tooltip text.
        """
        self._text = text


# ── EmptyState ────────────────────────────────────────────────────────────────


class EmptyState(ctk.CTkFrame):
    """Placeholder shown when a list or page has no content.

    Displays a large icon, title, subtitle, and an optional action button
    centered in the available space.

    Args:
        master: Parent widget.
        icon: Large emoji or unicode character.
        title: Heading text.
        subtitle: Descriptive text below the title.
        action_text: Optional button label.
        action_command: Optional callback for the action button.
        **kwargs: Additional CTkFrame keyword arguments.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        icon: str,
        title: str,
        subtitle: str,
        action_text: Optional[str] = None,
        action_command: Optional[callable] = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        # Center everything vertically and horizontally
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # ── Icon ─────────────────────────────────────────────────────────
        icon_label = ctk.CTkLabel(
            self,
            text=icon,
            font=font(48),
            text_color=TEXT_TERTIARY,
            fg_color="transparent",
        )
        icon_label.grid(row=0, column=0, pady=(PAD_3XL, PAD_MD), sticky="s")

        # ── Title ────────────────────────────────────────────────────────
        title_label = ctk.CTkLabel(
            self,
            text=title,
            font=FONT_SUBHEADING,
            text_color=TEXT_PRIMARY,
            fg_color="transparent",
        )
        title_label.grid(row=1, column=0, pady=(0, PAD_XS))

        # ── Subtitle ────────────────────────────────────────────────────
        subtitle_label = ctk.CTkLabel(
            self,
            text=subtitle,
            font=FONT_SMALL,
            text_color=TEXT_SECONDARY,
            fg_color="transparent",
            wraplength=300,
        )
        subtitle_label.grid(row=2, column=0, pady=(0, PAD_LG))

        # ── Optional Action Button ──────────────────────────────────────
        if action_text is not None and action_command is not None:
            action_btn = ctk.CTkButton(
                self,
                text=action_text,
                command=action_command,
                **STYLE_BUTTON_PRIMARY,
            )
            action_btn.grid(row=3, column=0, pady=(0, PAD_SM))

        logger.debug("EmptyState created: title='%s'", title)
