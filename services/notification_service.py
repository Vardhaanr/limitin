"""
Opal Desktop — Notification Service

Sends Windows toast notifications for usage warnings, limit enforcement, and
focus-mode events.

Notification back-ends (tried in order):
1. ``windows_toasts`` — native Windows 10/11 toast API.
2. ``plyer``          — cross-platform fallback.
3. Tkinter messagebox — last-resort fallback (non-blocking popup).

All notification methods are wrapped in broad exception handlers so that a
notification failure can **never** crash the application.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from services.logger import get_logger

logger = get_logger(__name__)

# ── Back-end detection ────────────────────────────────────────────────────

_USE_WINDOWS_TOASTS: bool = False
_USE_PLYER: bool = False

try:
    from windows_toasts import Toast, WindowsToaster  # type: ignore[import-untyped]

    _USE_WINDOWS_TOASTS = True
    logger.debug("Notification back-end: windows_toasts")
except ImportError:
    try:
        from plyer import notification as _plyer_notification  # type: ignore[import-untyped]

        _USE_PLYER = True
        logger.debug("Notification back-end: plyer")
    except ImportError:
        logger.debug("Notification back-end: tkinter fallback")

# Notification thresholds in seconds → human-readable label
_THRESHOLDS: list[tuple[int, str]] = [
    (30 * 60, "30 minutes"),
    (15 * 60, "15 minutes"),
    (10 * 60, "10 minutes"),
    (5 * 60,  "5 minutes"),
    (1 * 60,  "1 minute"),
]


class NotificationService:
    """Manages and dispatches desktop notifications for Opal events.

    Tracks which notifications have already been sent for the current day
    to avoid spamming the user with duplicate alerts.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        """Initialise the notification service."""
        # key → timestamp of last send; prevents duplicates
        self._sent: dict[str, float] = {}
        # Track per-app threshold notifications sent today
        # key = "{app_id}_{threshold_seconds}"
        self._threshold_sent: set[str] = set()

        self._lock: threading.Lock = threading.Lock()

        # Minimum seconds between duplicate notifications with the same key
        self._dedup_interval: float = 60.0

        if _USE_WINDOWS_TOASTS:
            try:
                self._toaster: Optional[WindowsToaster] = WindowsToaster("Opal Desktop")
            except Exception:
                self._toaster = None
                logger.debug("Failed to create WindowsToaster", exc_info=True)
        else:
            self._toaster = None

        logger.info("NotificationService initialised")

    # ------------------------------------------------------------------
    # Public notification methods
    # ------------------------------------------------------------------

    def notify_time_remaining(self, app_name: str, minutes: int) -> None:
        """Notify the user how many minutes remain for *app_name*.

        Args:
            app_name: Display name of the application.
            minutes:  Approximate minutes remaining.
        """
        key: str = f"time_remaining_{app_name}_{minutes}"
        if self._is_duplicate(key):
            return
        title: str = f"⏱️  {app_name} — Time Warning"
        body: str = f"You have about {minutes} minute{'s' if minutes != 1 else ''} remaining today."
        self._send_notification(title, body)
        self._mark_sent(key)

    def notify_limit_reached(self, app_name: str) -> None:
        """Notify the user that the daily limit for *app_name* has been reached.

        Args:
            app_name: Display name of the application.
        """
        key: str = f"limit_reached_{app_name}"
        if self._is_duplicate(key):
            return
        title: str = f"🛑  {app_name} — Limit Reached"
        body: str = (
            f"Your daily time limit for {app_name} has been reached. "
            "The app will be closed shortly."
        )
        self._send_notification(title, body)
        self._mark_sent(key)

    def notify_app_blocked(self, app_name: str) -> None:
        """Notify the user that *app_name* has been blocked.

        Args:
            app_name: Display name of the application.
        """
        key: str = f"app_blocked_{app_name}"
        if self._is_duplicate(key):
            return
        title: str = f"🚫  {app_name} — Blocked"
        body: str = (
            f"{app_name} has been blocked for the rest of today. "
            "Your daily limit has been exceeded."
        )
        self._send_notification(title, body)
        self._mark_sent(key)

    def notify_daily_reset(self) -> None:
        """Notify the user that daily usage counters have been reset."""
        title: str = "🔄  Daily Reset"
        body: str = "All app usage counters have been reset for a new day. Enjoy!"
        self._send_notification(title, body)

    def notify_focus_started(self, duration_minutes: int) -> None:
        """Notify that a focus session has begun.

        Args:
            duration_minutes: Planned duration of the focus session.
        """
        title: str = "🎯  Focus Mode Started"
        body: str = f"Stay focused for {duration_minutes} minutes. You've got this!"
        self._send_notification(title, body)

    def notify_focus_completed(self) -> None:
        """Notify that the focus session has completed."""
        title: str = "✅  Focus Session Complete"
        body: str = "Great work! Your focus session is finished. Take a well-deserved break."
        self._send_notification(title, body)

    # ------------------------------------------------------------------
    # Threshold checking
    # ------------------------------------------------------------------

    def check_thresholds(
        self, app_name: str, remaining_seconds: int, app_id: int
    ) -> None:
        """Fire a notification if *remaining_seconds* crosses a threshold.

        Thresholds: 30 min, 15 min, 10 min, 5 min, 1 min.
        Each threshold fires at most once per app per day.

        Args:
            app_name:          Display name of the application.
            remaining_seconds: Seconds remaining before the daily limit.
            app_id:            Database ID of the app.
        """
        for threshold_secs, label in _THRESHOLDS:
            if remaining_seconds > threshold_secs:
                continue

            threshold_key: str = f"{app_id}_{threshold_secs}"
            with self._lock:
                if threshold_key in self._threshold_sent:
                    continue
                self._threshold_sent.add(threshold_key)

            minutes: int = max(1, threshold_secs // 60)
            self.notify_time_remaining(app_name, minutes)
            # Only fire the most specific (smallest) threshold that applies
            break

    # ------------------------------------------------------------------
    # Daily reset
    # ------------------------------------------------------------------

    def reset_daily(self) -> None:
        """Clear all notification tracking for a new day."""
        with self._lock:
            self._sent.clear()
            self._threshold_sent.clear()
        logger.info("Notification tracking reset for new day")

    # ------------------------------------------------------------------
    # Internal: send notification via available back-end
    # ------------------------------------------------------------------

    def _send_notification(self, title: str, message: str) -> None:
        """Dispatch a notification through the best available back-end.

        Failures are logged but never raised.

        Args:
            title:   Notification title.
            message: Notification body text.
        """
        logger.debug("Notification: %s — %s", title, message)

        # --- windows_toasts ---
        if _USE_WINDOWS_TOASTS and self._toaster is not None:
            try:
                toast = Toast()
                toast.text_fields = [title, message]
                self._toaster.show_toast(toast)
                return
            except Exception:
                logger.debug("windows_toasts failed", exc_info=True)

        # --- plyer ---
        if _USE_PLYER:
            try:
                _plyer_notification.notify(
                    title=title,
                    message=message,
                    app_name="Opal Desktop",
                    timeout=8,
                )
                return
            except Exception:
                logger.debug("plyer notification failed", exc_info=True)

        # --- tkinter fallback (non-blocking) ---
        self._tkinter_fallback(title, message)

    @staticmethod
    def _tkinter_fallback(title: str, message: str) -> None:
        """Show a simple Tkinter popup on a throw-away thread.

        The popup auto-closes after 5 seconds to avoid blocking.
        """
        def _show() -> None:
            try:
                import tkinter as tk

                root = tk.Tk()
                root.withdraw()  # hide main window
                root.attributes("-topmost", True)
                root.title(title)

                popup = tk.Toplevel(root)
                popup.title(title)
                popup.attributes("-topmost", True)
                popup.geometry("360x120+100+100")
                popup.resizable(False, False)

                tk.Label(
                    popup, text=title, font=("Segoe UI", 11, "bold"),
                    wraplength=340, anchor="w", justify="left",
                ).pack(padx=10, pady=(10, 2), fill="x")

                tk.Label(
                    popup, text=message, font=("Segoe UI", 10),
                    wraplength=340, anchor="w", justify="left",
                ).pack(padx=10, pady=(2, 10), fill="x")

                # Auto-close after 5 seconds
                popup.after(5000, root.destroy)
                root.mainloop()
            except Exception:
                logger.debug("Tkinter fallback notification failed", exc_info=True)

        thread = threading.Thread(target=_show, daemon=True, name="OpalNotify")
        thread.start()

    # ------------------------------------------------------------------
    # Deduplication helpers
    # ------------------------------------------------------------------

    def _is_duplicate(self, key: str) -> bool:
        """Check if a notification with *key* was sent recently."""
        with self._lock:
            last_sent: Optional[float] = self._sent.get(key)
            if last_sent is None:
                return False
            return (time.time() - last_sent) < self._dedup_interval

    def _mark_sent(self, key: str) -> None:
        """Record that a notification with *key* was just sent."""
        with self._lock:
            self._sent[key] = time.time()
