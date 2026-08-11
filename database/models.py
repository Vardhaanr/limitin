"""
Opal Desktop — Data Models

Dataclass definitions for all database entities. These are shared across
services, database, and UI layers. Every table in SQLite maps to one model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Application:
    """A monitored application with its usage limits and preferences."""

    name: str
    exe_path: str
    daily_limit_seconds: int = 3600              # Default: 1 hour
    icon_path: Optional[str] = None
    is_active: bool = True
    notify_enabled: bool = True
    grace_period_seconds: int = 60               # Countdown before block
    block_mode: str = "warn_then_block"          # "warn_then_block" or "immediate"
    schedule_start: Optional[str] = None         # "HH:MM" or None (always)
    schedule_end: Optional[str] = None           # "HH:MM" or None (always)
    created_at: Optional[str] = None             # ISO 8601 timestamp
    id: Optional[int] = None

    @property
    def daily_limit_minutes(self) -> float:
        """Daily limit in minutes (for display)."""
        return self.daily_limit_seconds / 60.0

    @property
    def daily_limit_hours(self) -> float:
        """Daily limit in hours (for display)."""
        return self.daily_limit_seconds / 3600.0

    @property
    def has_schedule(self) -> bool:
        """Whether this app has a time-of-day schedule restriction."""
        return self.schedule_start is not None and self.schedule_end is not None

    @property
    def exe_name(self) -> str:
        """Extract the executable filename from the full path."""
        if not self.exe_path:
            return ""
        return self.exe_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]


@dataclass
class UsageRecord:
    """Aggregated daily usage for one app on one day."""

    app_id: int
    date: str                                    # "YYYY-MM-DD"
    usage_seconds: int = 0
    was_blocked: bool = False
    id: Optional[int] = None

    @property
    def usage_minutes(self) -> float:
        return self.usage_seconds / 60.0

    @property
    def usage_hours(self) -> float:
        return self.usage_seconds / 3600.0


@dataclass
class UsageSession:
    """A single continuous usage session (foreground focus period)."""

    app_id: int
    start_time: str                              # ISO 8601
    end_time: Optional[str] = None               # ISO 8601 (None = still active)
    duration_seconds: int = 0
    id: Optional[int] = None

    @property
    def is_active(self) -> bool:
        return self.end_time is None


@dataclass
class FocusSession:
    """A focus mode session blocking distracting apps."""

    target_duration_seconds: int
    start_time: Optional[str] = None             # ISO 8601
    end_time: Optional[str] = None               # ISO 8601
    duration_seconds: int = 0
    apps_blocked: str = "[]"                     # JSON-encoded list of app IDs
    completed: bool = False
    id: Optional[int] = None

    @property
    def is_active(self) -> bool:
        return self.start_time is not None and self.end_time is None


@dataclass
class BlockedEvent:
    """Log entry for every time an app was blocked/terminated."""

    app_id: int
    timestamp: str                               # ISO 8601
    reason: str                                  # "limit_exceeded", "schedule", "focus_mode"
    action_taken: str                            # "terminated", "warned", "user_closed"
    id: Optional[int] = None


@dataclass
class AppSetting:
    """Key-value setting stored in the database."""

    key: str
    value: str


@dataclass
class DailyStats:
    """Computed statistics for a single day (not stored directly — derived)."""

    date: str
    total_usage_seconds: int = 0
    total_blocks: int = 0
    apps_used: int = 0
    focus_sessions_completed: int = 0
    focus_time_seconds: int = 0

    @property
    def total_usage_minutes(self) -> float:
        return self.total_usage_seconds / 60.0

    @property
    def total_usage_hours(self) -> float:
        return self.total_usage_seconds / 3600.0


@dataclass
class AppUsageSummary:
    """Summary of an app's usage for display in the UI."""

    app: Application
    usage_today_seconds: int = 0
    is_blocked: bool = False
    is_currently_active: bool = False
    current_session_seconds: int = 0

    @property
    def usage_percentage(self) -> float:
        """Usage as a percentage of daily limit (0.0 to 1.0+)."""
        if self.app.daily_limit_seconds <= 0:
            return 0.0
        return self.usage_today_seconds / self.app.daily_limit_seconds

    @property
    def remaining_seconds(self) -> int:
        """Seconds remaining before limit is reached."""
        return max(0, self.app.daily_limit_seconds - self.usage_today_seconds)

    @property
    def status(self) -> str:
        """Current status string for display."""
        if self.is_blocked:
            return "blocked"
        if not self.app.is_active:
            return "paused"
        if self.is_currently_active:
            return "active"
        pct = self.usage_percentage
        if pct >= 0.9:
            return "warning"
        return "idle"
