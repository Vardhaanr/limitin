"""
Opal Desktop — Usage Timer Service

Manages per-application usage counters in memory with periodic flushing to the
database.  All access is thread-safe via a reentrant lock so the tracking loop
and the UI can read concurrently.

Counters are keyed by ``app_id`` (the database primary key for the Application).
Each tick adds one second for the given app.  Pending deltas accumulate and are
batch-written to SQLite on ``flush_to_db()``, which should be called every
~10 seconds by the orchestrator.
"""

from __future__ import annotations

import threading
from datetime import date
from typing import Optional

from database.schema import Database
from services.logger import get_logger

logger = get_logger(__name__)


class UsageTimer:
    """Thread-safe, in-memory usage counter with periodic DB persistence."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, db: Database) -> None:
        """Initialise the usage timer.

        Args:
            db: The database instance used for persistence.
        """
        self._db: Database = db
        # Current accumulated seconds per app_id for *today*
        self._counters: dict[int, int] = {}
        # Delta (seconds added) since the last flush, per app_id
        self._pending: dict[int, int] = {}
        # Date for which the counters are valid
        self._current_date: str = date.today().isoformat()
        # Lock guards both _counters and _pending
        self._lock: threading.RLock = threading.RLock()

        logger.info("UsageTimer initialised for date %s", self._current_date)

    # ------------------------------------------------------------------
    # Public API — called from the tracking loop (daemon thread)
    # ------------------------------------------------------------------

    def tick(self, app_id: int) -> int:
        """Add one second of usage for *app_id*.

        This is called once per second from the tracking loop for the
        currently-focused monitored application.

        Args:
            app_id: The application's database ID.

        Returns:
            The new total usage (seconds) for this app today.
        """
        with self._lock:
            current: int = self._counters.get(app_id, 0) + 1
            self._counters[app_id] = current
            self._pending[app_id] = self._pending.get(app_id, 0) + 1
            return current

    def get_usage(self, app_id: int) -> int:
        """Return the current usage in seconds for *app_id* today.

        Args:
            app_id: The application's database ID.

        Returns:
            Seconds of usage recorded today (in-memory value).
        """
        with self._lock:
            return self._counters.get(app_id, 0)

    def get_all_usage(self) -> dict[int, int]:
        """Return a snapshot of all usage counters.

        Returns:
            Mapping of ``app_id -> seconds_used_today``.
        """
        with self._lock:
            return dict(self._counters)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def flush_to_db(self) -> None:
        """Write pending deltas to the database.

        Only app_ids with new usage since the last flush are written.
        Each delta is added to the existing stored value for today's date.
        Called periodically (e.g. every 10 s) by the orchestrator.
        """
        with self._lock:
            if not self._pending:
                return
            # Snapshot and clear pending under the lock
            to_flush: dict[int, int] = dict(self._pending)
            self._pending.clear()

        today: str = self._current_date
        flushed_count: int = 0

        for app_id, delta in to_flush.items():
            if delta <= 0:
                continue
            try:
                # ── Update usage_sessions (granular session tracking) ──
                row = self._db.fetch_one(
                    "SELECT id, duration_seconds FROM usage_sessions "
                    "WHERE app_id = ? AND session_date = ? "
                    "ORDER BY id DESC LIMIT 1",
                    (app_id, today),
                )
                if row:
                    new_total: int = row["duration_seconds"] + delta
                    self._db.execute(
                        "UPDATE usage_sessions SET duration_seconds = ?, "
                        "end_time = CURRENT_TIMESTAMP WHERE id = ?",
                        (new_total, row["id"]),
                    )
                else:
                    # Create a new daily session row
                    self._db.execute(
                        "INSERT INTO usage_sessions "
                        "(app_id, start_time, duration_seconds, session_date) "
                        "VALUES (?, CURRENT_TIMESTAMP, ?, ?)",
                        (app_id, delta, today),
                    )

                # ── Update usage_history (daily summary for UI pages) ──
                hist_row = self._db.fetch_one(
                    "SELECT id, usage_seconds FROM usage_history "
                    "WHERE app_id = ? AND date = ?",
                    (app_id, today),
                )
                if hist_row:
                    self._db.execute(
                        "UPDATE usage_history SET usage_seconds = ? WHERE id = ?",
                        (hist_row["usage_seconds"] + delta, hist_row["id"]),
                    )
                else:
                    self._db.execute(
                        "INSERT INTO usage_history (app_id, date, usage_seconds) "
                        "VALUES (?, ?, ?)",
                        (app_id, today, delta),
                    )

                flushed_count += 1
            except Exception:
                logger.exception(
                    "Failed to flush usage for app_id=%d, delta=%d", app_id, delta
                )
                # Re-add the delta so it isn't lost
                with self._lock:
                    self._pending[app_id] = self._pending.get(app_id, 0) + delta

        if flushed_count:
            logger.debug("Flushed usage for %d app(s) to database", flushed_count)

    def load_from_db(self) -> None:
        """Load today's existing usage from the database into memory.

        Should be called once at startup so in-memory counters reflect
        usage already recorded earlier in the day.
        """
        today: str = date.today().isoformat()
        self._current_date = today

        with self._lock:
            self._counters.clear()
            self._pending.clear()

        try:
            rows = self._db.fetch_all(
                "SELECT app_id, SUM(duration_seconds) AS total "
                "FROM usage_sessions WHERE session_date = ? GROUP BY app_id",
                (today,),
            )
            with self._lock:
                for row in rows:
                    app_id: int = row["app_id"]
                    total: int = row["total"] or 0
                    self._counters[app_id] = total

            logger.info(
                "Loaded usage for %d app(s) from DB for %s",
                len(rows),
                today,
            )
        except Exception:
            logger.exception("Failed to load usage from database")

    def reset_daily(self) -> None:
        """Reset all counters for a new day.

        Flushes any remaining pending data first, then clears counters
        and updates the internal date reference.
        """
        logger.info("Performing daily usage counter reset")
        # Flush leftover data under yesterday's date
        self.flush_to_db()

        with self._lock:
            self._counters.clear()
            self._pending.clear()
            self._current_date = date.today().isoformat()

        logger.info("Counters reset — new date is %s", self._current_date)

    def force_flush(self) -> None:
        """Immediately flush all pending data.

        Convenience alias called during shutdown to prevent data loss.
        """
        logger.info("Force-flushing usage data to database")
        self.flush_to_db()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def set_usage(self, app_id: int, seconds: int) -> None:
        """Directly set the in-memory counter for an app (e.g. after DB load).

        Args:
            app_id: The application's database ID.
            seconds: Total seconds to set.
        """
        with self._lock:
            self._counters[app_id] = max(0, seconds)

    @property
    def current_date(self) -> str:
        """The ISO-format date string the counters are tracking."""
        return self._current_date
