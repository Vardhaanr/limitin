"""
Opal Desktop — Sidebar Navigation Panel

The left-hand sidebar providing navigation between all application pages,
branding, and a real-time tracking status indicator.
"""

from __future__ import annotations

import logging
from typing import Optional

import customtkinter as ctk

from themes.dark_theme import (
    BG_DARK,
    BG_CARD,
    BG_ELEVATED,
    ACCENT,
    ACCENT_LIGHT,
    ACCENT_SURFACE,
    GREEN,
    GREEN_LIGHT,
    GREEN_MUTED,
    AMBER,
    AMBER_LIGHT,
    AMBER_MUTED,
    RED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    TEXT_DISABLED,
    BORDER,
    BORDER_DIVIDER,
    SIDEBAR_WIDTH,
    BUTTON_CORNER_RADIUS,
    FONT_BODY,
    FONT_SMALL,
    FONT_TINY,
    ICONS,
    STYLE_SIDEBAR,
    STYLE_SIDEBAR_BUTTON,
    STYLE_SIDEBAR_BUTTON_ACTIVE,
    PAD_XS,
    PAD_SM,
    PAD_MD,
    PAD_LG,
    PAD_XL,
    PAD_2XL,
    font,
    font_bold,
)
from ui.widgets import SidebarButton

logger = logging.getLogger("opal.ui.sidebar")

# ── Navigation Definition ────────────────────────────────────────────────────

_NAV_ITEMS: list[dict[str, str]] = [
    {"name": "dashboard", "label": "Dashboard", "icon": ""},
    {"name": "limits",    "label": "Apps & Limits", "icon": ""},
    {"name": "statistics","label": "Statistics", "icon": ""},
    {"name": "history",   "label": "History",    "icon": ""},
    {"name": "focus",     "label": "Focus Mode", "icon": ""},
]

_BOTTOM_ITEMS: list[dict[str, str]] = [
    {"name": "settings", "label": "Settings", "icon": ""},
    {"name": "about",    "label": "About",    "icon": ""},
]

# Version shown at the bottom of the sidebar
_APP_VERSION = "v0.1.0"


class Sidebar(ctk.CTkFrame):
    """Left navigation sidebar for Opal Desktop.

    Renders a fixed-width panel with branding at the top, navigation buttons
    in the middle, a separator, secondary nav items, and a tracking status
    indicator at the bottom.

    Args:
        master: Parent widget (typically the main application window).
        on_navigate: Callback(page_name: str) invoked when a nav button is
                     clicked. page_name is one of: 'dashboard', 'limits',
                     'statistics', 'history', 'focus', 'settings', 'about'.
        **kwargs: Additional CTkFrame keyword arguments.
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_navigate: callable,
        **kwargs,
    ) -> None:
        sidebar_kwargs = {
            **STYLE_SIDEBAR,
            "width": SIDEBAR_WIDTH,
            **kwargs,
        }
        super().__init__(master, **sidebar_kwargs)

        self._on_navigate = on_navigate
        self._buttons: dict[str, SidebarButton] = {}
        self._active_page: str = "dashboard"

        # Prevent the sidebar from shrinking below its configured width
        self.grid_propagate(False)
        self.pack_propagate(False)

        self._build_ui()

        logger.info("Sidebar initialized with %d navigation items",
                     len(_NAV_ITEMS) + len(_BOTTOM_ITEMS))

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construct all sidebar child widgets."""
        # ── Logo / Branding ──────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(fill="x", padx=PAD_LG, pady=(PAD_2XL, PAD_XS))

        logo_label = ctk.CTkLabel(
            logo_frame,
            text="Opal",
            font=font_bold(22),
            text_color=ACCENT_LIGHT,
            anchor="w",
            fg_color="transparent",
        )
        logo_label.pack(anchor="w")

        tagline_label = ctk.CTkLabel(
            logo_frame,
            text="Digital Wellness",
            font=font(10),
            text_color=TEXT_TERTIARY,
            anchor="w",
            fg_color="transparent",
        )
        tagline_label.pack(anchor="w", pady=(0, PAD_XS))

        # ── Primary Navigation ───────────────────────────────────────────
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=PAD_SM, pady=(PAD_MD, 0))

        for item in _NAV_ITEMS:
            btn = SidebarButton(
                nav_frame,
                icon=item["icon"],
                text=item["label"],
                command=self._make_nav_command(item["name"]),
            )
            btn.pack(fill="x", pady=2)
            self._buttons[item["name"]] = btn

        # ── Separator ────────────────────────────────────────────────────
        separator = ctk.CTkFrame(
            self,
            height=1,
            fg_color=BORDER_DIVIDER,
            corner_radius=0,
        )
        separator.pack(fill="x", padx=PAD_XL, pady=PAD_MD)

        # ── Secondary Navigation ─────────────────────────────────────────
        secondary_frame = ctk.CTkFrame(self, fg_color="transparent")
        secondary_frame.pack(fill="x", padx=PAD_SM)

        for item in _BOTTOM_ITEMS:
            btn = SidebarButton(
                secondary_frame,
                icon=item["icon"],
                text=item["label"],
                command=self._make_nav_command(item["name"]),
            )
            btn.pack(fill="x", pady=2)
            self._buttons[item["name"]] = btn

        # ── Spacer (pushes status to the bottom) ────────────────────────
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # ── Tracking Status Indicator ────────────────────────────────────
        self._status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._status_frame.pack(fill="x", padx=PAD_LG, pady=(0, PAD_SM))

        self._status_dot = ctk.CTkLabel(
            self._status_frame,
            text="●",
            font=font(10),
            text_color=GREEN,
            width=16,
            fg_color="transparent",
        )
        self._status_dot.pack(side="left")

        self._status_label = ctk.CTkLabel(
            self._status_frame,
            text="Tracking active",
            font=FONT_TINY,
            text_color=TEXT_TERTIARY,
            anchor="w",
            fg_color="transparent",
        )
        self._status_label.pack(side="left", padx=(PAD_XS, 0))

        # ── Version Number ───────────────────────────────────────────────
        version_label = ctk.CTkLabel(
            self,
            text=_APP_VERSION,
            font=FONT_TINY,
            text_color=TEXT_DISABLED,
            anchor="center",
            fg_color="transparent",
        )
        version_label.pack(pady=(0, PAD_MD))

        # ── Set initial active state ─────────────────────────────────────
        self.set_active_page(self._active_page)

    # ── Navigation Helpers ───────────────────────────────────────────────

    def _make_nav_command(self, page_name: str) -> callable:
        """Create a lambda-safe callback for a navigation button.

        Args:
            page_name: The page identifier string.

        Returns:
            A zero-argument callable that navigates to the given page.
        """
        def _navigate() -> None:
            try:
                self.set_active_page(page_name)
                self._on_navigate(page_name)
            except Exception:
                logger.exception("Navigation error for page '%s'", page_name)

        return _navigate

    # ── Public Methods ───────────────────────────────────────────────────

    def set_active_page(self, page_name: str) -> None:
        """Highlight the active page button and deactivate others.

        Args:
            page_name: One of 'dashboard', 'limits', 'statistics', 'history',
                       'focus', 'settings', 'about'.
        """
        try:
            self._active_page = page_name
            for name, btn in self._buttons.items():
                btn.set_active(name == page_name)
            logger.debug("Active page set to '%s'", page_name)
        except Exception:
            logger.exception("Failed to set active page to '%s'", page_name)

    def set_tracking_status(self, is_active: bool, is_paused: bool) -> None:
        """Update the tracking status indicator at the bottom of the sidebar.

        Args:
            is_active: True if the tracker service is running.
            is_paused: True if tracking is temporarily paused.
        """
        try:
            if is_paused:
                self._status_dot.configure(text_color=AMBER)
                self._status_label.configure(text="Tracking paused")
            elif is_active:
                self._status_dot.configure(text_color=GREEN)
                self._status_label.configure(text="Tracking active")
            else:
                self._status_dot.configure(text_color=RED)
                self._status_label.configure(text="Tracking stopped")
            logger.debug(
                "Tracking status updated: active=%s, paused=%s",
                is_active,
                is_paused,
            )
        except Exception:
            logger.exception("Failed to update tracking status")
