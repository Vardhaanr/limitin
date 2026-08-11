"""
Opal Desktop — Main Application Window

The root CTk window that hosts the sidebar, page frames, background services,
and system tray.  Created once by ``main.py`` after the splash screen finishes.
"""

from __future__ import annotations

import sys
import threading
from typing import Optional

import customtkinter as ctk

from themes.dark_theme import (
    BG_DARKEST, BG_DARK, BG_MID, ACCENT, ACCENT_LIGHT, TEXT_SECONDARY,
    FONT_FAMILY, SIDEBAR_WIDTH, BORDER_DIVIDER,
)
from utils.logger import get_logger
from utils.storage import ConfigManager
from database.database import DatabaseManager

# ── Pages (imported lazily inside _build_pages to avoid circular imports) ─────
from ui.sidebar import Sidebar
from ui.dashboard import DashboardPage
from ui.limits import LimitsPage
from ui.statistics import StatisticsPage
from ui.history import HistoryPage
from ui.settings import SettingsPage
from ui.focus_mode import FocusModePage
from ui.about import AboutPage

# ── Services ─────────────────────────────────────────────────────────────────
from services.app_tracker import AppTracker
from services.notification_service import NotificationService
from services.tray_service import TrayService

logger = get_logger(__name__)


class OpalApp(ctk.CTk):
    """Main application window for Opal Desktop.

    Responsibilities:
      - Hosts the sidebar navigation and page frames.
      - Owns the ``DatabaseManager`` and ``AppTracker`` singletons.
      - Manages the system-tray icon.
      - Coordinates graceful shutdown.
    """

    # ── Class-level page registry ────────────────────────────────────────────
    PAGE_NAMES = [
        "dashboard", "limits", "statistics", "history",
        "focus", "settings", "about",
    ]

    def __init__(self, config: ConfigManager, db: DatabaseManager) -> None:
        super().__init__()

        self.config = config
        self.db = db

        # ── Window chrome ────────────────────────────────────────────────────
        self.title("Opal Desktop")
        self.configure(fg_color=BG_DARKEST)

        w = self.config.get("window.width", 1200)
        h = self.config.get("window.height", 750)
        min_w = self.config.get("window.min_width", 900)
        min_h = self.config.get("window.min_height", 600)

        # Centre on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min_w, min_h)

        # Try to set the window icon
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        # ── Services ─────────────────────────────────────────────────────────
        self.tracker = AppTracker(db=self.db)
        self.notification_service = NotificationService()
        self.tray_service = TrayService()

        # Wire blocker notifications
        self.tracker.blocker.set_on_block_callback(self._on_app_blocked)
        self.tracker.blocker.set_on_grace_callback(self._on_grace_period)

        # ── UI ───────────────────────────────────────────────────────────────
        self._current_page: str = "dashboard"
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._grace_overlay: Optional[ctk.CTkToplevel] = None

        self._build_layout()
        self._build_pages()
        self._show_page("dashboard")

        # ── Start background services ────────────────────────────────────────
        if self.config.get("behavior.tracking_enabled", True):
            self.tracker.start()
            logger.info("Tracking engine started")

        self._start_tray()

        # ── Window protocol ──────────────────────────────────────────────────
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Start periodic UI refresh ────────────────────────────────────────
        self._schedule_refresh()

        # ── Force window to front ─────────────────────────────────────────────
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(500, lambda: self.attributes("-topmost", False))

        logger.info("Opal Desktop ready")

    # ──────────────────────────────────────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        """Create the two-column layout: sidebar | content."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)   # sidebar fixed
        self.grid_columnconfigure(1, weight=1)   # content expands

        # Sidebar
        self.sidebar = Sidebar(
            self,
            on_navigate=self._show_page,
        )
        self.sidebar.grid(row=0, column=0, sticky="ns")

        # Content container
        self.content_frame = ctk.CTkFrame(self, fg_color=BG_MID, corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

    def _build_pages(self) -> None:
        """Instantiate all page frames (hidden initially)."""
        page_classes = {
            "dashboard": DashboardPage,
            "limits": LimitsPage,
            "statistics": StatisticsPage,
            "history": HistoryPage,
            "focus": FocusModePage,
            "settings": SettingsPage,
            "about": AboutPage,
        }

        for name, cls in page_classes.items():
            try:
                page = cls(
                    self.content_frame,
                    db=self.db,
                    tracker=self.tracker,
                )
                page.grid(row=0, column=0, sticky="nsew")
                page.grid_remove()  # Hide initially
                self._pages[name] = page
            except Exception:
                logger.exception("Failed to create page '%s'", name)

    # ──────────────────────────────────────────────────────────────────────────
    # Navigation
    # ──────────────────────────────────────────────────────────────────────────

    def _show_page(self, page_name: str) -> None:
        """Switch to the given page, hiding the current one."""
        if page_name == self._current_page and page_name in self._pages:
            return

        # Hide current
        if self._current_page in self._pages:
            self._pages[self._current_page].grid_remove()

        # Show requested
        if page_name in self._pages:
            self._pages[page_name].grid()
            self._current_page = page_name
            self.sidebar.set_active_page(page_name)

            # Refresh the page data
            try:
                self._pages[page_name].refresh()
            except Exception:
                logger.exception("Error refreshing page '%s'", page_name)
        else:
            logger.warning("Page '%s' not found", page_name)

    # ──────────────────────────────────────────────────────────────────────────
    # Periodic UI refresh (1 second)
    # ──────────────────────────────────────────────────────────────────────────

    def _schedule_refresh(self) -> None:
        """Schedule a UI refresh every second for the active page."""
        try:
            if self._current_page in self._pages:
                page = self._pages[self._current_page]
                if hasattr(page, "refresh"):
                    page.refresh()
        except Exception:
            logger.debug("Refresh error (non-critical)", exc_info=True)
        finally:
            self.after(1000, self._schedule_refresh)

    # ──────────────────────────────────────────────────────────────────────────
    # Service callbacks
    # ──────────────────────────────────────────────────────────────────────────

    def _on_app_blocked(self, app_id: int, app_name: str) -> None:
        """Called by Blocker when an app is terminated."""
        logger.info("App blocked: %s (id=%d)", app_name, app_id)
        self.notification_service.notify_app_blocked(app_name)

    def _on_grace_period(self, app_id: int, seconds_remaining: int) -> None:
        """Called by Blocker when a grace period starts."""
        logger.info("Grace period for app_id=%d: %ds", app_id, seconds_remaining)

        # Get the app info
        app = self.db.get_application(app_id)
        if not app:
            return

        # Show the floating overlay (on the main thread)
        self.after(0, lambda: self._show_grace_overlay(app, seconds_remaining))

    def _show_grace_overlay(self, app, seconds_remaining: int) -> None:
        """Display the grace period countdown overlay."""
        from ui.dialogs import GracePeriodOverlay

        # Close existing overlay if any
        if self._grace_overlay is not None:
            try:
                self._grace_overlay.destroy()
            except Exception:
                pass

        def on_close_app():
            self.tracker.blocker.terminate_process(app.exe_path)
            if self._grace_overlay:
                try:
                    self._grace_overlay.destroy()
                except Exception:
                    pass
                self._grace_overlay = None

        def on_dismiss():
            if self._grace_overlay:
                try:
                    self._grace_overlay.destroy()
                except Exception:
                    pass
                self._grace_overlay = None

        self._grace_overlay = GracePeriodOverlay(
            self, app.name, seconds_remaining,
            on_close_app=on_close_app,
            on_dismiss=on_dismiss,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # System tray
    # ──────────────────────────────────────────────────────────────────────────

    def _start_tray(self) -> None:
        """Launch the system-tray icon on a daemon thread."""
        try:
            self.tray_service.start(
                on_show=lambda: self.after(0, self._show_from_tray),
                on_pause=lambda: self.after(0, self._pause_tracking),
                on_resume=lambda: self.after(0, self._resume_tracking),
                on_quit=lambda: self.after(0, self._quit_app),
            )
        except Exception:
            logger.exception("Failed to start tray service")

    def _show_from_tray(self) -> None:
        """Restore the window from the system tray."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _pause_tracking(self) -> None:
        """Pause the tracking engine."""
        self.tracker.pause()
        self.sidebar.set_tracking_status(is_active=True, is_paused=True)
        self.tray_service.set_tracking_state(is_paused=True)
        logger.info("Tracking paused")

    def _resume_tracking(self) -> None:
        """Resume the tracking engine."""
        self.tracker.resume()
        self.sidebar.set_tracking_status(is_active=True, is_paused=False)
        self.tray_service.set_tracking_state(is_paused=False)
        logger.info("Tracking resumed")

    # ──────────────────────────────────────────────────────────────────────────
    # Shutdown
    # ──────────────────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        """Handle the window close button click."""
        if self.config.get("behavior.minimize_to_tray", True):
            self.withdraw()  # Hide to tray
            logger.info("Minimized to tray")
        else:
            self._quit_app()

    def _quit_app(self) -> None:
        """Full application shutdown — stop all services and exit."""
        logger.info("Shutting down Opal Desktop...")

        # Stop tracking
        try:
            self.tracker.stop()
        except Exception:
            logger.exception("Error stopping tracker")

        # Stop tray
        try:
            self.tray_service.stop()
        except Exception:
            logger.exception("Error stopping tray service")

        # Close database
        try:
            self.db.close()
        except Exception:
            logger.exception("Error closing database")

        # Save config
        try:
            self.config.save()
        except Exception:
            logger.exception("Error saving config")

        logger.info("Goodbye!")

        self.quit()
        self.destroy()
