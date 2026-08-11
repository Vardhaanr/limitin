"""
Opal Desktop — System Tray Service

Runs a ``pystray`` system-tray icon on a dedicated daemon thread.
The tray provides quick access to show the main window, pause/resume
tracking, and quit the application.

The icon is a procedurally generated 64×64 PNG with a stylised "O"
drawn in the accent colour, so no external icon file is needed.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from services.logger import get_logger

logger = get_logger(__name__)

# Late-imported inside methods to allow graceful failure if pystray/PIL
# are not installed.
_PYSTRAY_AVAILABLE: bool = False
_PIL_AVAILABLE: bool = False

try:
    import pystray  # type: ignore[import-untyped]

    _PYSTRAY_AVAILABLE = True
except ImportError:
    logger.warning("pystray not installed — system tray will be unavailable")

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-untyped]

    _PIL_AVAILABLE = True
except ImportError:
    logger.warning("Pillow not installed — system tray icon cannot be created")


class TrayService:
    """System-tray icon providing Show / Pause / Resume / Quit actions."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        """Initialise the tray service (does not start it)."""
        self._icon: Optional[pystray.Icon] = None  # type: ignore[name-defined]
        self._thread: Optional[threading.Thread] = None
        self._tracking_paused: bool = False

        # Callbacks (set via ``start()``)
        self._on_show: Optional[Callable[[], None]] = None
        self._on_pause: Optional[Callable[[], None]] = None
        self._on_resume: Optional[Callable[[], None]] = None
        self._on_quit: Optional[Callable[[], None]] = None

        self._lock: threading.Lock = threading.Lock()
        logger.info("TrayService initialised")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        on_show: Callable[[], None],
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        """Create and display the system-tray icon.

        The icon is run on a daemon thread via ``pystray.Icon.run()``.

        Args:
            on_show:   Callback to bring the main window to the foreground.
            on_pause:  Callback to pause tracking.
            on_resume: Callback to resume tracking.
            on_quit:   Callback to quit the entire application.
        """
        if not _PYSTRAY_AVAILABLE or not _PIL_AVAILABLE:
            logger.warning("Cannot start tray — pystray or Pillow not available")
            return

        self._on_show = on_show
        self._on_pause = on_pause
        self._on_resume = on_resume
        self._on_quit = on_quit

        image: Image.Image = self._create_icon_image()
        menu = self._build_menu()

        self._icon = pystray.Icon(
            name="OpalDesktop",
            icon=image,
            title="Opal Desktop — Tracking",
            menu=menu,
        )

        self._thread = threading.Thread(
            target=self._run_icon,
            name="OpalTray",
            daemon=True,
        )
        self._thread.start()
        logger.info("System tray icon started")

    def stop(self) -> None:
        """Remove the tray icon and shut down the tray thread."""
        with self._lock:
            icon = self._icon
            self._icon = None

        if icon is not None:
            try:
                icon.stop()
                logger.info("System tray icon stopped")
            except Exception:
                logger.debug("Error stopping tray icon", exc_info=True)

    # ------------------------------------------------------------------
    # Dynamic updates
    # ------------------------------------------------------------------

    def update_tooltip(self, text: str) -> None:
        """Update the tray icon's hover tooltip.

        Args:
            text: New tooltip string (max ~128 chars on Windows).
        """
        with self._lock:
            if self._icon is not None:
                try:
                    self._icon.title = text[:127]
                except Exception:
                    logger.debug("Failed to update tray tooltip", exc_info=True)

    def set_tracking_state(self, is_paused: bool) -> None:
        """Reflect the current tracking state in the tray menu.

        Args:
            is_paused: True if tracking is currently paused.
        """
        with self._lock:
            self._tracking_paused = is_paused
            if self._icon is not None:
                try:
                    self._icon.menu = self._build_menu()
                    if is_paused:
                        self._icon.title = "Opal Desktop — Paused"
                    else:
                        self._icon.title = "Opal Desktop — Tracking"
                except Exception:
                    logger.debug("Failed to update tray menu", exc_info=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_icon(self) -> None:
        """Entry point for the tray thread."""
        try:
            if self._icon is not None:
                self._icon.run()
        except Exception:
            logger.exception("Tray icon run() raised an exception")

    def _build_menu(self) -> pystray.Menu:  # type: ignore[name-defined]
        """Build the context menu for the tray icon."""
        items: list[pystray.MenuItem] = []  # type: ignore[name-defined]

        # Show window
        items.append(
            pystray.MenuItem("Show Opal", self._handle_show, default=True)
        )

        items.append(pystray.Menu.SEPARATOR)

        # Pause / Resume
        with self._lock:
            paused = self._tracking_paused

        if paused:
            items.append(
                pystray.MenuItem("Resume Tracking", self._handle_resume)
            )
        else:
            items.append(
                pystray.MenuItem("Pause Tracking", self._handle_pause)
            )

        items.append(pystray.Menu.SEPARATOR)

        # Quit
        items.append(pystray.MenuItem("Quit", self._handle_quit))

        return pystray.Menu(*items)

    # ── Menu action handlers ──────────────────────────────────────────

    def _handle_show(self, icon: object, item: object) -> None:
        """Handle 'Show Opal' menu click."""
        if self._on_show is not None:
            try:
                self._on_show()
            except Exception:
                logger.exception("Error in on_show callback")

    def _handle_pause(self, icon: object, item: object) -> None:
        """Handle 'Pause Tracking' menu click."""
        with self._lock:
            self._tracking_paused = True
        if self._on_pause is not None:
            try:
                self._on_pause()
            except Exception:
                logger.exception("Error in on_pause callback")
        self.set_tracking_state(True)

    def _handle_resume(self, icon: object, item: object) -> None:
        """Handle 'Resume Tracking' menu click."""
        with self._lock:
            self._tracking_paused = False
        if self._on_resume is not None:
            try:
                self._on_resume()
            except Exception:
                logger.exception("Error in on_resume callback")
        self.set_tracking_state(False)

    def _handle_quit(self, icon: object, item: object) -> None:
        """Handle 'Quit' menu click."""
        self.stop()
        if self._on_quit is not None:
            try:
                self._on_quit()
            except Exception:
                logger.exception("Error in on_quit callback")

    # ── Icon generation ───────────────────────────────────────────────

    @staticmethod
    def _create_icon_image() -> Image.Image:  # type: ignore[name-defined]
        """Generate a 64×64 icon image with a stylised 'O' for Opal.

        Uses the accent colour (#6366f1 — indigo) on a dark background
        to match the application's dark theme.

        Returns:
            A 64×64 RGBA ``PIL.Image``.
        """
        size: int = 64
        bg_color: str = "#1e1e2e"
        accent: str = "#6366f1"
        accent_light: str = "#818cf8"

        image: Image.Image = Image.new("RGBA", (size, size), bg_color)
        draw: ImageDraw.ImageDraw = ImageDraw.Draw(image)

        # Outer ring (accent)
        padding: int = 6
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            outline=accent,
            width=5,
        )

        # Inner accent dot
        center: int = size // 2
        dot_radius: int = 6
        draw.ellipse(
            [
                center - dot_radius,
                center - dot_radius,
                center + dot_radius,
                center + dot_radius,
            ],
            fill=accent_light,
        )

        # Small highlight arc (top-right) to give depth
        draw.arc(
            [padding + 2, padding + 2, size - padding - 2, size - padding - 2],
            start=-60,
            end=30,
            fill=accent_light,
            width=2,
        )

        return image
