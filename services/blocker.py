"""
Limitin Desktop — Blocker Service

Enforces application time limits by terminating processes when their daily
usage quota is exhausted.  Supports a configurable grace period during which
the user is warned before the app is forcefully closed.

Thread-safe: all mutable state is guarded by a lock so the tracking loop
and UI can interact concurrently.
"""

from __future__ import annotations

import os
import time
import threading
from datetime import datetime
from typing import Callable, Optional

import psutil

from database.models import Application, BlockedEvent
from database.schema import Database
from services.logger import get_logger

logger = get_logger(__name__)


class Blocker:
    """Enforces per-app daily usage limits by blocking/terminating apps."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, db: Database) -> None:
        """Initialise the blocker.

        Args:
            db: Database instance for logging blocked events.
        """
        self._db: Database = db

        # Set of app_ids that are blocked for the rest of the day
        self._blocked_apps: set[int] = set()

        # app_id -> timestamp when the grace period ends
        self._grace_periods: dict[int, float] = {}

        # Callback: (app_id: int, app_name: str) -> None
        self._on_block_callback: Optional[Callable[[int, str], None]] = None

        # Callback: (app_id: int, seconds_remaining: int) -> None
        self._on_grace_callback: Optional[Callable[[int, int], None]] = None

        self._lock: threading.RLock = threading.RLock()

        logger.info("Blocker initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_and_block(
        self, app_id: int, usage_seconds: int, app: Application
    ) -> str:
        """Evaluate whether *app* should be blocked based on its usage.

        Decision matrix:
        - If already blocked ➜ ``'already_blocked'``
        - If usage < limit    ➜ ``'none'``
        - If ``block_mode == 'immediate'`` ➜ terminate immediately, ``'blocked'``
        - If ``block_mode == 'warn_then_block'``:
            - First call over limit ➜ start grace period, ``'grace_started'``
            - During grace          ➜ ``'grace_warning'``
            - Grace expired         ➜ terminate, ``'blocked'``

        Args:
            app_id:        The application's database ID.
            usage_seconds: Current day's accumulated usage in seconds.
            app:           The Application model instance.

        Returns:
            One of ``'none'``, ``'grace_started'``, ``'grace_warning'``,
            ``'blocked'``, or ``'already_blocked'``.
        """
        with self._lock:
            # ── Already blocked ───────────────────────────────────────
            if app_id in self._blocked_apps:
                # Re-terminate in case the user re-opened the app
                self._terminate_and_log(app, "limit_exceeded")
                return "already_blocked"

            # ── Under the limit ───────────────────────────────────────
            if app.daily_limit_seconds <= 0:
                # Zero or negative means unlimited
                return "none"

            if usage_seconds < app.daily_limit_seconds:
                return "none"

            # ── Over the limit ────────────────────────────────────────
            if app.block_mode == "immediate":
                self._blocked_apps.add(app_id)
                self._terminate_and_log(app, "limit_exceeded")
                self._fire_block_callback(app_id, app.name)
                return "blocked"

            # --- warn_then_block (default) ---
            now: float = time.time()

            if app_id not in self._grace_periods:
                # Start grace period
                grace_end: float = now + app.grace_period_seconds
                self._grace_periods[app_id] = grace_end
                remaining: int = app.grace_period_seconds
                logger.info(
                    "Grace period started for '%s' (app_id=%d) — %d s remaining",
                    app.name, app_id, remaining,
                )
                self._fire_grace_callback(app_id, remaining)
                return "grace_started"

            grace_end = self._grace_periods[app_id]

            if now < grace_end:
                remaining = max(0, int(grace_end - now))
                self._fire_grace_callback(app_id, remaining)
                return "grace_warning"

            # Grace period expired → block
            del self._grace_periods[app_id]
            self._blocked_apps.add(app_id)
            self._terminate_and_log(app, "limit_exceeded")
            self._fire_block_callback(app_id, app.name)
            return "blocked"

    def is_blocked(self, app_id: int) -> bool:
        """Return whether *app_id* is currently blocked.

        Args:
            app_id: The application's database ID.

        Returns:
            True if the app has been blocked for the remainder of the day.
        """
        with self._lock:
            return app_id in self._blocked_apps

    def terminate_process(self, exe_path: str) -> bool:
        """Terminate all running processes whose executable matches *exe_path*.

        Uses ``psutil`` to iterate running processes and sends ``terminate()``
        (SIGTERM-equivalent on Windows) to each matching process.

        Args:
            exe_path: Full normalised path to the executable.

        Returns:
            True if at least one process was terminated.
        """
        if not exe_path:
            return False

        normalised: str = os.path.normpath(exe_path).lower()
        terminated: int = 0

        for proc in psutil.process_iter(attrs=["pid", "exe"]):
            try:
                proc_exe: Optional[str] = proc.info.get("exe")  # type: ignore[union-attr]
                if proc_exe is None:
                    continue
                if os.path.normpath(proc_exe).lower() == normalised:
                    proc.terminate()
                    terminated += 1
                    logger.info(
                        "Terminated PID %d (%s)",
                        proc.info["pid"],  # type: ignore[index]
                        exe_path,
                    )
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                logger.warning(
                    "Access denied terminating PID %d for %s",
                    proc.info.get("pid", 0),  # type: ignore[union-attr]
                    exe_path,
                )
            except Exception:
                logger.debug("Error terminating process", exc_info=True)

        return terminated > 0

    def get_blocked_apps(self) -> set[int]:
        """Return a *copy* of the set of currently blocked app IDs."""
        with self._lock:
            return set(self._blocked_apps)

    def reset_daily(self) -> None:
        """Clear all blocks and grace periods for a new day."""
        with self._lock:
            count: int = len(self._blocked_apps)
            self._blocked_apps.clear()
            self._grace_periods.clear()
        logger.info("Daily blocker reset — cleared %d blocked app(s)", count)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def set_on_block_callback(
        self, callback: Callable[[int, str], None]
    ) -> None:
        """Set the callback invoked when an app is blocked.

        Args:
            callback: ``(app_id, app_name) -> None``
        """
        self._on_block_callback = callback

    def set_on_grace_callback(
        self, callback: Callable[[int, int], None]
    ) -> None:
        """Set the callback invoked during/at the start of a grace period.

        Args:
            callback: ``(app_id, seconds_remaining) -> None``
        """
        self._on_grace_callback = callback

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fire_block_callback(self, app_id: int, app_name: str) -> None:
        """Safely invoke the block callback."""
        if self._on_block_callback is not None:
            try:
                self._on_block_callback(app_id, app_name)
            except Exception:
                logger.exception("Error in on_block callback")

    def _fire_grace_callback(self, app_id: int, remaining: int) -> None:
        """Safely invoke the grace-period callback."""
        if self._on_grace_callback is not None:
            try:
                self._on_grace_callback(app_id, remaining)
            except Exception:
                logger.exception("Error in on_grace callback")

    def _terminate_and_log(self, app: Application, reason: str) -> None:
        """Terminate the application and log the blocked event to the DB."""
        did_terminate: bool = self.terminate_process(app.exe_path)
        action: str = "terminated" if did_terminate else "warned"

        try:
            now_iso: str = datetime.now().isoformat()
            self._db.execute(
                "INSERT INTO usage_sessions (app_id, start_time, duration_seconds, session_date) "
                "SELECT ?, ?, 0, ? WHERE NOT EXISTS ("
                "  SELECT 1 FROM usage_sessions WHERE app_id = ? AND session_date = ?"
                ")",
                (
                    app.id,
                    now_iso,
                    datetime.now().date().isoformat(),
                    app.id,
                    datetime.now().date().isoformat(),
                ),
            )
        except Exception:
            logger.debug("Could not ensure usage row exists for blocked event", exc_info=True)

        logger.info(
            "Blocked app '%s' (id=%s) — reason=%s action=%s",
            app.name,
            app.id,
            reason,
            action,
        )
