"""
Limitin Desktop — Scheduler Service

Evaluates time-of-day schedule restrictions for monitored applications.
An app with ``schedule_start`` / ``schedule_end`` set (both in "HH:MM" format)
is only allowed to run during that window.  Outside the window the tracker
should treat the app as blocked.

Handles edge cases:
- Overnight schedules (e.g. 22:00 – 06:00).
- Missing or partially-set schedules (treated as always-allowed).
- Invalid time strings (logged, treated as always-allowed).
"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
from typing import Optional

from database.models import Application
from services.logger import get_logger

logger = get_logger(__name__)


class Scheduler:
    """Schedule-based time-of-day restrictions for monitored applications."""

    def __init__(self) -> None:
        """Initialise the scheduler."""
        logger.info("Scheduler initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_app_allowed(self, app: Application) -> bool:
        """Check if *app* is allowed at the current moment.

        An app is allowed when:
        - It has no schedule (both start and end are ``None``).
        - The current time falls inside ``[schedule_start, schedule_end)``.

        For overnight schedules (start > end, e.g. 22:00–06:00), the
        allowed window wraps past midnight.

        Args:
            app: The Application instance to evaluate.

        Returns:
            True if the app may run right now, False otherwise.
        """
        if not app.has_schedule:
            return True

        start: Optional[dt_time] = self._parse_time(app.schedule_start)
        end: Optional[dt_time] = self._parse_time(app.schedule_end)

        if start is None or end is None:
            # Malformed schedule — fail open (allow)
            logger.warning(
                "App '%s' has invalid schedule (%s – %s); treating as always-allowed",
                app.name, app.schedule_start, app.schedule_end,
            )
            return True

        now: dt_time = datetime.now().time()

        if start <= end:
            # Normal (same-day) window: e.g. 09:00 – 17:00
            return start <= now < end
        else:
            # Overnight window: e.g. 22:00 – 06:00
            return now >= start or now < end

    def get_next_allowed_time(self, app: Application) -> Optional[str]:
        """Return the next time the app will become allowed, as ``"HH:MM"``.

        If the app is already allowed (or has no schedule), returns ``None``.

        Args:
            app: The Application instance.

        Returns:
            ``"HH:MM"`` string, or None.
        """
        if not app.has_schedule:
            return None

        start: Optional[dt_time] = self._parse_time(app.schedule_start)
        end: Optional[dt_time] = self._parse_time(app.schedule_end)

        if start is None or end is None:
            return None

        now: dt_time = datetime.now().time()

        if start <= end:
            # Same-day window
            if now < start:
                return self._format_time(start)
            if now >= end:
                # Next allowed is tomorrow's start
                return self._format_time(start)
            return None  # currently allowed
        else:
            # Overnight window
            if now >= start or now < end:
                return None  # currently allowed
            # Between end and start — next allowed is today's start
            return self._format_time(start)

    @staticmethod
    def seconds_until_midnight() -> int:
        """Return the number of seconds until the next midnight.

        Returns:
            Integer seconds (always ≥ 0, at most 86 399).
        """
        now: datetime = datetime.now()
        midnight: datetime = datetime.combine(
            now.date() + timedelta(days=1), dt_time.min
        )
        delta: timedelta = midnight - now
        return max(0, int(delta.total_seconds()))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_time(value: Optional[str]) -> Optional[dt_time]:
        """Parse an ``"HH:MM"`` string into a ``datetime.time``.

        Args:
            value: Time string, or None.

        Returns:
            ``datetime.time`` on success, None on failure.
        """
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        try:
            parts = value.split(":")
            if len(parts) != 2:
                return None
            hour: int = int(parts[0])
            minute: int = int(parts[1])
            return dt_time(hour=hour, minute=minute)
        except (ValueError, TypeError):
            logger.debug("Failed to parse time string: %r", value)
            return None

    @staticmethod
    def _format_time(t: dt_time) -> str:
        """Format a ``datetime.time`` as ``"HH:MM"``."""
        return f"{t.hour:02d}:{t.minute:02d}"
