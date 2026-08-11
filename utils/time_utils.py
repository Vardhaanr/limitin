"""
Opal Desktop — Time Utilities

Pure date/time helpers used throughout the application.  All functions
return deterministic results based on the current clock, and they
avoid the low-level ``time`` module in favour of ``datetime``.

Usage:
    from utils.time_utils import today_str, now_iso, seconds_until_midnight
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from typing import Final


# ---------------------------------------------------------------------------
# Current-time helpers
# ---------------------------------------------------------------------------

def now() -> datetime:
    """Return the current local date-time.

    Returns:
        The current :class:`datetime.datetime` with local timezone awareness
        omitted (naive) for consistency across the application.
    """
    return datetime.now()


def today_str() -> str:
    """Return today's date as ``"YYYY-MM-DD"``.

    Returns:
        A date string formatted as ``"YYYY-MM-DD"``.
    """
    return date.today().isoformat()


def now_iso() -> str:
    """Return the current date-time as an ISO 8601 string.

    Returns:
        An ISO 8601 formatted string, e.g. ``"2026-07-07T22:15:30.123456"``.
    """
    return datetime.now().isoformat()


def get_hour_of_day() -> int:
    """Return the current hour of the day (0–23).

    Returns:
        An integer in the range ``[0, 23]``.
    """
    return datetime.now().hour


# ---------------------------------------------------------------------------
# Midnight / day-boundary helpers
# ---------------------------------------------------------------------------

def seconds_until_midnight() -> int:
    """Return the number of whole seconds remaining until midnight.

    Returns:
        Seconds until 00:00:00 of the next day.
    """
    right_now = datetime.now()
    midnight = datetime.combine(right_now.date() + timedelta(days=1), time.min)
    delta = midnight - right_now
    return int(delta.total_seconds())


def is_same_day(dt1: datetime, dt2: datetime) -> bool:
    """Check whether two datetimes fall on the same calendar day.

    Args:
        dt1: First datetime.
        dt2: Second datetime.

    Returns:
        ``True`` if both dates have the same year/month/day.
    """
    return dt1.date() == dt2.date()


# ---------------------------------------------------------------------------
# Date-range builders
# ---------------------------------------------------------------------------

def get_week_range(reference: date | str | None = None) -> tuple[str, str]:
    """Return ``(start, end)`` date strings for the ISO week containing *reference*.

    The week starts on Monday and ends on Sunday.

    Args:
        reference: A :class:`date` or ``"YYYY-MM-DD"`` string.  Defaults to
                   today when ``None``.

    Returns:
        A 2-tuple of ``"YYYY-MM-DD"`` strings ``(monday, sunday)``.
    """
    ref = _coerce_date(reference)
    monday = ref - timedelta(days=ref.weekday())  # weekday(): 0 = Monday
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def get_month_range(reference: date | str | None = None) -> tuple[str, str]:
    """Return ``(start, end)`` date strings for the month containing *reference*.

    Args:
        reference: A :class:`date` or ``"YYYY-MM-DD"`` string.  Defaults to
                   today when ``None``.

    Returns:
        A 2-tuple ``("YYYY-MM-01", "YYYY-MM-{last_day}")``.
    """
    ref = _coerce_date(reference)
    first_day = ref.replace(day=1)
    _, last_day_num = calendar.monthrange(ref.year, ref.month)
    last_day = ref.replace(day=last_day_num)
    return first_day.isoformat(), last_day.isoformat()


def get_year_range(reference: date | str | None = None) -> tuple[str, str]:
    """Return ``(start, end)`` date strings for the year containing *reference*.

    Args:
        reference: A :class:`date` or ``"YYYY-MM-DD"`` string.  Defaults to
                   today when ``None``.

    Returns:
        A 2-tuple ``("YYYY-01-01", "YYYY-12-31")``.
    """
    ref = _coerce_date(reference)
    return f"{ref.year}-01-01", f"{ref.year}-12-31"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_time(time_str: str) -> time:
    """Parse a ``"HH:MM"`` string into a :class:`datetime.time` object.

    Args:
        time_str: A time string in ``"HH:MM"`` format (24-hour).

    Returns:
        The corresponding :class:`time` object.

    Raises:
        ValueError: If *time_str* is not in the expected format.
    """
    try:
        parsed = datetime.strptime(time_str.strip(), "%H:%M")
        return parsed.time()
    except ValueError as exc:
        raise ValueError(
            f"Expected time in 'HH:MM' format, got {time_str!r}"
        ) from exc


def is_within_schedule(start: str, end: str) -> bool:
    """Check whether the current time falls within a ``HH:MM``–``HH:MM`` window.

    Handles overnight ranges (e.g. ``"22:00"`` – ``"06:00"``).

    Args:
        start: Start time as ``"HH:MM"``.
        end:   End time as ``"HH:MM"``.

    Returns:
        ``True`` if the current local time is between *start* and *end*.
    """
    current = datetime.now().time()
    start_t = parse_time(start)
    end_t = parse_time(end)

    if start_t <= end_t:
        # Same-day window, e.g. 09:00–17:00
        return start_t <= current <= end_t
    else:
        # Overnight window, e.g. 22:00–06:00
        return current >= start_t or current <= end_t


# ---------------------------------------------------------------------------
# Date enumeration / arithmetic
# ---------------------------------------------------------------------------

def date_range(start_date: str, end_date: str) -> list[str]:
    """Return a list of ``"YYYY-MM-DD"`` date strings from *start_date* to *end_date* (inclusive).

    Args:
        start_date: Start date as ``"YYYY-MM-DD"``.
        end_date:   End date as ``"YYYY-MM-DD"``.

    Returns:
        An ordered list of date strings.  If *start_date* > *end_date*
        the list will be empty.
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    result: list[str] = []
    current = start
    while current <= end:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def days_ago(n: int) -> str:
    """Return the date string for *n* days before today.

    Args:
        n: Number of days in the past (0 = today).

    Returns:
        A ``"YYYY-MM-DD"`` string.
    """
    return (date.today() - timedelta(days=n)).isoformat()


# ---------------------------------------------------------------------------
# Display / formatting helpers
# ---------------------------------------------------------------------------

def format_date_display(date_str: str) -> str:
    """Format a ``"YYYY-MM-DD"`` string for human display.

    Args:
        date_str: A date in ``"YYYY-MM-DD"`` format.

    Returns:
        A formatted string like ``"Mon, Jun 29"``.
    """
    try:
        dt = date.fromisoformat(date_str)
        return dt.strftime("%a, %b %d").replace(" 0", " ")
    except ValueError:
        return date_str


def get_day_of_week(date_str: str) -> int:
    """Return the ISO day-of-week for *date_str* (0 = Monday … 6 = Sunday).

    Args:
        date_str: A date in ``"YYYY-MM-DD"`` format.

    Returns:
        An integer in ``[0, 6]``.
    """
    return date.fromisoformat(date_str).weekday()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _coerce_date(value: date | str | None) -> date:
    """Convert *value* to a :class:`date`, defaulting to today."""
    if value is None:
        return date.today()
    if isinstance(value, str):
        return date.fromisoformat(value)
    if isinstance(value, datetime):
        return value.date()
    return value
