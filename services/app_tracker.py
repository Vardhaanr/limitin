"""
Opal Desktop — App Tracker (Orchestrator)

The central tracking service that ties together window detection, usage
counting, and limit enforcement.  Runs a 1-second polling loop on a
background daemon thread.

Lifecycle:
    tracker = AppTracker(db)
    tracker.start()          # spawns daemon thread
    ...
    tracker.stop()           # flushes data, joins thread

Thread-safety: all mutable state is guarded by a reentrant lock so that
the UI thread can safely call ``get_app_summaries()`` and similar readers.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime
from typing import Callable, Optional

from database.models import Application, AppUsageSummary
from database.schema import Database
from services.blocker import Blocker
from services.logger import get_logger
from services.usage_timer import UsageTimer
from services.window_detector import WindowDetector, WindowInfo

logger = get_logger(__name__)

# How often (in ticks / seconds) to flush in-memory counters to the DB.
_FLUSH_INTERVAL: int = 10


class AppTracker:
    """Main tracking orchestrator — polls the foreground window once per
    second, tallies usage, and enforces limits."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, db: Database) -> None:
        """Initialise the tracker and its sub-services.

        Args:
            db: The database instance shared across services.
        """
        self._db: Database = db
        self._detector: WindowDetector = WindowDetector()
        self._timer: UsageTimer = UsageTimer(db)
        self._blocker: Blocker = Blocker(db)

        # Thread control
        self._running: bool = False
        self._paused: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock: threading.RLock = threading.RLock()

        # Tracking state
        self._current_app_name: Optional[str] = None
        self._current_app_id: Optional[int] = None
        self._current_session_start: float = 0.0
        self._flush_counter: int = 0
        self._tracking_date: str = date.today().isoformat()

        # Cached app list (refreshed periodically)
        self._monitored_apps: list[Application] = []
        self._app_by_path: dict[str, Application] = {}
        self._app_by_exe_name: dict[str, Application] = {}
        self._apps_refresh_counter: int = 0
        _APPS_REFRESH_INTERVAL: int = 30  # seconds

        # Callbacks
        self._on_tick: Optional[Callable[[list[AppUsageSummary]], None]] = None
        self._on_active_change: Optional[Callable[[Optional[str]], None]] = None

        # Load initial data
        self._refresh_monitored_apps()
        self._timer.load_from_db()

        logger.info("AppTracker initialised with %d monitored app(s)", len(self._monitored_apps))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background tracking thread."""
        with self._lock:
            if self._running:
                logger.warning("AppTracker.start() called but already running")
                return
            self._running = True
            self._paused = False

        self._thread = threading.Thread(
            target=self._tracking_loop,
            name="OpalTracker",
            daemon=True,
        )
        self._thread.start()
        logger.info("Tracking thread started")

    def stop(self) -> None:
        """Stop the tracking thread and flush all data."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        # Wait for thread to finish (with timeout)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        # Final flush
        self._timer.force_flush()
        logger.info("Tracking thread stopped — data flushed")

    def pause(self) -> None:
        """Pause tracking (the thread keeps running but does nothing)."""
        with self._lock:
            self._paused = True
        logger.info("Tracking paused")

    def resume(self) -> None:
        """Resume tracking."""
        with self._lock:
            self._paused = False
        logger.info("Tracking resumed")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Whether the tracking thread is alive."""
        with self._lock:
            return self._running

    @property
    def is_paused(self) -> bool:
        """Whether tracking is paused."""
        with self._lock:
            return self._paused

    # ------------------------------------------------------------------
    # Readers (safe to call from any thread)
    # ------------------------------------------------------------------

    def get_current_app(self) -> Optional[str]:
        """Return the name of the currently active monitored app, or None."""
        with self._lock:
            return self._current_app_name

    def get_app_summaries(self) -> list[AppUsageSummary]:
        """Build usage summaries for every monitored app.

        Returns:
            List of ``AppUsageSummary`` instances with live data.
        """
        with self._lock:
            apps = list(self._monitored_apps)
            current_id = self._current_app_id
            session_secs = self.get_current_session_seconds()

        summaries: list[AppUsageSummary] = []
        for app in apps:
            if app.id is None:
                continue
            usage: int = self._timer.get_usage(app.id)
            is_active: bool = app.id == current_id
            summaries.append(
                AppUsageSummary(
                    app=app,
                    usage_today_seconds=usage,
                    is_blocked=self._blocker.is_blocked(app.id),
                    is_currently_active=is_active,
                    current_session_seconds=session_secs if is_active else 0,
                )
            )
        return summaries

    def get_current_session_seconds(self) -> int:
        """Duration in seconds of the current foreground session."""
        with self._lock:
            if self._current_app_id is None or self._current_session_start <= 0:
                return 0
            return max(0, int(time.time() - self._current_session_start))

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def set_on_tick_callback(
        self, callback: Callable[[list[AppUsageSummary]], None]
    ) -> None:
        """Register a callback invoked every tick with updated summaries."""
        self._on_tick = callback

    def set_on_active_change_callback(
        self, callback: Callable[[Optional[str]], None]
    ) -> None:
        """Register a callback invoked when the active monitored app changes."""
        self._on_active_change = callback

    # ------------------------------------------------------------------
    # Sub-service accessors
    # ------------------------------------------------------------------

    @property
    def blocker(self) -> Blocker:
        """Direct access to the Blocker (for setting callbacks from the UI)."""
        return self._blocker

    @property
    def timer(self) -> UsageTimer:
        """Direct access to the UsageTimer."""
        return self._timer

    # ------------------------------------------------------------------
    # Main tracking loop (runs on daemon thread)
    # ------------------------------------------------------------------

    def _tracking_loop(self) -> None:
        """Poll the foreground window once per second.

        Steps each tick:
        1. Check for midnight date change → reset counters.
        2. If paused, skip to sleep.
        3. Detect the foreground window.
        4. Match it against monitored apps (by exe_path).
        5. If monitored and not minimised, tick usage.
        6. Check limits via the Blocker.
        7. Periodically flush to DB.
        8. Fire on_tick callback.
        """
        logger.debug("Tracking loop entered")

        while True:
            loop_start: float = time.time()

            with self._lock:
                if not self._running:
                    break

            try:
                # 1) Midnight reset check
                self._check_midnight_reset()

                # 2) Paused?
                with self._lock:
                    if self._paused:
                        self._sleep_remainder(loop_start)
                        continue

                # 3) Detect foreground window
                win_info: Optional[WindowInfo] = self._detector.get_foreground_window()

                matched_app: Optional[Application] = None
                if win_info is not None and not win_info.is_minimized:
                    matched_app = self._match_app(win_info)

                # 4–5) Update tracking state
                self._update_active_app(matched_app)

                if matched_app is not None and matched_app.id is not None:
                    # Skip ticking if the app is already blocked
                    if self._blocker.is_blocked(matched_app.id):
                        # Re-terminate in case user reopened it
                        self._blocker.check_and_block(
                            matched_app.id,
                            self._timer.get_usage(matched_app.id),
                            matched_app,
                        )
                        with self._lock:
                            self._current_app_name = None
                            self._current_app_id = None
                            self._current_session_start = 0.0
                    else:
                        # Tick usage only if not blocked
                        usage: int = self._timer.tick(matched_app.id)

                        # 6) Check limits
                        action: str = self._blocker.check_and_block(
                            matched_app.id, usage, matched_app
                        )
                        if action in ("blocked", "already_blocked"):
                            # Clear active app since it was terminated
                            with self._lock:
                                self._current_app_name = None
                                self._current_app_id = None
                                self._current_session_start = 0.0

                # 7) Periodic flush
                self._flush_counter += 1
                if self._flush_counter >= _FLUSH_INTERVAL:
                    self._flush_counter = 0
                    self._timer.flush_to_db()

                # Periodic app list refresh
                self._apps_refresh_counter += 1
                if self._apps_refresh_counter >= 30:
                    self._apps_refresh_counter = 0
                    self._refresh_monitored_apps()

                # 8) Fire callback
                self._fire_tick_callback()

            except Exception:
                logger.exception("Error in tracking loop tick")

            self._sleep_remainder(loop_start)

        logger.debug("Tracking loop exited")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match_app(self, win_info: WindowInfo) -> Optional[Application]:
        """Try to match a ``WindowInfo`` to a monitored Application.

        Matches first by full exe path, then falls back to exe filename.
        """
        normalised: str = os.path.normpath(win_info.exe_path).lower()
        exe_name: str = os.path.basename(normalised)
        with self._lock:
            # Try full path match first
            app = self._app_by_path.get(normalised)
            if app is not None:
                return app
            # Fallback: match by exe filename
            return self._app_by_exe_name.get(exe_name)

    def _update_active_app(self, app: Optional[Application]) -> None:
        """Track which monitored app is currently in the foreground."""
        with self._lock:
            new_id: Optional[int] = app.id if app is not None else None
            if new_id == self._current_app_id:
                return  # No change

            old_name: Optional[str] = self._current_app_name
            self._current_app_id = new_id
            self._current_app_name = app.name if app is not None else None
            self._current_session_start = time.time() if app is not None else 0.0

        # Fire change callback (outside lock)
        if self._on_active_change is not None:
            try:
                self._on_active_change(
                    app.name if app is not None else None
                )
            except Exception:
                logger.exception("Error in on_active_change callback")

        if app is not None:
            logger.debug("Active app changed: %s -> %s", old_name, app.name)

    def _refresh_monitored_apps(self) -> None:
        """Reload the list of monitored applications from the database."""
        try:
            rows = self._db.fetch_all(
                "SELECT id, name, exe_path, icon_path, daily_limit_seconds, "
                "is_active, notify_enabled, grace_period_seconds, block_mode, "
                "schedule_start, schedule_end, created_at "
                "FROM applications WHERE is_active = 1"
            )
            apps: list[Application] = []
            path_map: dict[str, Application] = {}
            name_map: dict[str, Application] = {}

            for row in rows:
                app = Application(
                    id=row["id"],
                    name=row["name"],
                    exe_path=row["exe_path"] or "",
                    icon_path=row["icon_path"],
                    daily_limit_seconds=row["daily_limit_seconds"],
                    is_active=bool(row["is_active"]),
                    notify_enabled=bool(row["notify_enabled"]),
                    grace_period_seconds=row["grace_period_seconds"],
                    block_mode=row["block_mode"],
                    schedule_start=row["schedule_start"],
                    schedule_end=row["schedule_end"],
                    created_at=row["created_at"],
                )
                apps.append(app)
                if app.exe_path:
                    key: str = os.path.normpath(app.exe_path).lower()
                    path_map[key] = app
                    # Also map by exe filename for fallback matching
                    exe_name = os.path.basename(key)
                    name_map[exe_name] = app

            with self._lock:
                self._monitored_apps = apps
                self._app_by_path = path_map
                self._app_by_exe_name = name_map

            logger.debug("Refreshed monitored apps: %d app(s)", len(apps))
        except Exception:
            logger.exception("Failed to refresh monitored apps from database")

    def _check_midnight_reset(self) -> None:
        """If the date has rolled over, reset daily counters."""
        today: str = date.today().isoformat()
        if today != self._tracking_date:
            logger.info("Date changed (%s -> %s) - performing daily reset",
                        self._tracking_date, today)
            self._tracking_date = today
            self._timer.reset_daily()
            self._blocker.reset_daily()

    def _fire_tick_callback(self) -> None:
        """Invoke the on_tick callback with current summaries."""
        if self._on_tick is not None:
            try:
                summaries = self.get_app_summaries()
                self._on_tick(summaries)
            except Exception:
                logger.exception("Error in on_tick callback")

    @staticmethod
    def _sleep_remainder(loop_start: float) -> None:
        """Sleep for the remainder of a 1-second tick."""
        elapsed: float = time.time() - loop_start
        sleep_time: float = max(0.0, 1.0 - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)
