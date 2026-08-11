"""
Opal Desktop — SQLite Database Manager

Thread-safe, WAL-mode SQLite database with parameterised queries,
automatic schema creation, and migration support.

Usage:
    from database.database import DatabaseManager
    db = DatabaseManager("data/opal.db")
    app_id = db.add_application(app)
    usage  = db.get_usage_today(app_id)
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from database.models import (
    Application,
    BlockedEvent,
    FocusSession,
    UsageRecord,
    UsageSession,
)
from utils.logger import get_logger
from utils.time_utils import now_iso, today_str

logger = get_logger(__name__)

# Current schema version — bump when adding migrations.
_SCHEMA_VERSION: int = 1


class DatabaseManager:
    """Thread-safe SQLite database manager for Opal Desktop.

    All write operations are serialised through a :class:`threading.Lock`
    so the database can be shared across monitoring threads and the UI
    thread without corruption.

    Args:
        db_path: Path to the SQLite database file (created if missing).
                 Relative paths are resolved from the project root.
    """

    # ------------------------------------------------------------------
    # Construction / setup
    # ------------------------------------------------------------------

    def __init__(self, db_path: str = "data/opal.db") -> None:
        if not os.path.isabs(db_path):
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(app_root, db_path)

        self._db_path: str = db_path
        self._lock: threading.Lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

        # Ensure parent directory exists.
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        self._connect()
        self._create_tables()
        self._run_migrations()
        logger.info("Database opened: %s", self._db_path)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Open (or re-open) the database connection with recommended pragmas."""
        try:
            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                timeout=10.0,
            )
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA busy_timeout = 5000")
            self._conn.row_factory = sqlite3.Row
        except sqlite3.DatabaseError as exc:
            logger.critical("Database connection failed: %s", exc)
            self._handle_corruption()

    def _handle_corruption(self) -> None:
        """Last-resort handler for a corrupt database file.

        Renames the corrupt file, creates a fresh database, and logs a
        critical warning.
        """
        corrupt_path = self._db_path + ".corrupt"
        logger.critical(
            "Database appears corrupt — renaming to %s and recreating",
            corrupt_path,
        )
        try:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            if os.path.isfile(self._db_path):
                os.replace(self._db_path, corrupt_path)
        except OSError as exc:
            logger.error("Could not rename corrupt database: %s", exc)

        # Re-create from scratch.
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=10.0,
        )
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        """Create all required tables if they do not already exist."""
        assert self._conn is not None
        try:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    name                 TEXT    NOT NULL,
                    exe_path             TEXT    NOT NULL UNIQUE,
                    icon_path            TEXT,
                    daily_limit_seconds  INTEGER NOT NULL DEFAULT 3600,
                    is_active            INTEGER NOT NULL DEFAULT 1,
                    notify_enabled       INTEGER NOT NULL DEFAULT 1,
                    grace_period_seconds INTEGER NOT NULL DEFAULT 60,
                    block_mode           TEXT    NOT NULL DEFAULT 'warn_then_block',
                    schedule_start       TEXT,
                    schedule_end         TEXT,
                    created_at           TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS usage_history (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id        INTEGER NOT NULL,
                    date          TEXT    NOT NULL,
                    usage_seconds INTEGER NOT NULL DEFAULT 0,
                    was_blocked   INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (app_id) REFERENCES applications(id) ON DELETE CASCADE,
                    UNIQUE(app_id, date)
                );

                CREATE TABLE IF NOT EXISTS usage_sessions (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id           INTEGER NOT NULL,
                    start_time       TEXT    NOT NULL,
                    end_time         TEXT,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    session_date     TEXT,
                    FOREIGN KEY (app_id) REFERENCES applications(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS focus_sessions (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time              TEXT,
                    end_time                TEXT,
                    duration_seconds        INTEGER NOT NULL DEFAULT 0,
                    target_duration_seconds INTEGER NOT NULL,
                    apps_blocked            TEXT    NOT NULL DEFAULT '[]',
                    completed               INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS blocked_events (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id       INTEGER NOT NULL,
                    timestamp    TEXT    NOT NULL,
                    reason       TEXT    NOT NULL,
                    action_taken TEXT    NOT NULL,
                    FOREIGN KEY (app_id) REFERENCES applications(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL
                );

                -- Performance indexes
                CREATE INDEX IF NOT EXISTS idx_usage_history_app_date
                    ON usage_history(app_id, date);
                CREATE INDEX IF NOT EXISTS idx_usage_history_date
                    ON usage_history(date);
                CREATE INDEX IF NOT EXISTS idx_usage_sessions_app
                    ON usage_sessions(app_id);
                CREATE INDEX IF NOT EXISTS idx_blocked_events_timestamp
                    ON blocked_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_focus_sessions_start
                    ON focus_sessions(start_time);
                """
            )
            self._conn.commit()
        except sqlite3.DatabaseError as exc:
            logger.critical("Table creation failed: %s", exc)
            self._handle_corruption()

    def _run_migrations(self) -> None:
        """Apply any pending schema migrations."""
        assert self._conn is not None
        current = self._get_schema_version()
        if current < _SCHEMA_VERSION:
            # --- Migration 1: initial schema (tables already exist) ---
            # Future migrations can be added here as elif blocks.
            self._set_schema_version(_SCHEMA_VERSION)
            logger.info(
                "Database migrated from v%d to v%d", current, _SCHEMA_VERSION
            )

    def _get_schema_version(self) -> int:
        """Return the current schema version stored in the database."""
        try:
            row = self._fetchone("SELECT MAX(version) AS v FROM schema_version")
            if row and row[0] is not None:
                return int(row[0])
        except sqlite3.OperationalError:
            pass
        return 0

    def _set_schema_version(self, version: int) -> None:
        """Record *version* as the current schema version."""
        self._execute(
            "INSERT INTO schema_version (version) VALUES (?)", (version,)
        )

    # ------------------------------------------------------------------
    # Low-level query helpers (all serialised through _lock)
    # ------------------------------------------------------------------

    def _execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a write query under the lock and return the cursor.

        Args:
            query:  SQL statement with ``?`` placeholders.
            params: Parameter tuple.

        Returns:
            The :class:`sqlite3.Cursor` after execution.
        """
        with self._lock:
            assert self._conn is not None
            try:
                cursor = self._conn.execute(query, params)
                self._conn.commit()
                return cursor
            except sqlite3.DatabaseError as exc:
                logger.error("SQL execute failed: %s | query=%s", exc, query)
                raise

    def _executemany(self, query: str, params: list) -> None:
        """Execute *query* for each parameter set in *params*.

        Args:
            query:  SQL statement with ``?`` placeholders.
            params: List of parameter tuples.
        """
        with self._lock:
            assert self._conn is not None
            try:
                self._conn.executemany(query, params)
                self._conn.commit()
            except sqlite3.DatabaseError as exc:
                logger.error("SQL executemany failed: %s | query=%s", exc, query)
                raise

    def _fetchone(
        self, query: str, params: tuple = ()
    ) -> Optional[sqlite3.Row]:
        """Execute a read query and return the first row, or ``None``.

        Args:
            query:  SQL statement.
            params: Parameter tuple.

        Returns:
            A :class:`sqlite3.Row` or ``None``.
        """
        assert self._conn is not None
        try:
            cursor = self._conn.execute(query, params)
            return cursor.fetchone()
        except sqlite3.DatabaseError as exc:
            logger.error("SQL fetchone failed: %s | query=%s", exc, query)
            raise

    def _fetchall(
        self, query: str, params: tuple = ()
    ) -> list[sqlite3.Row]:
        """Execute a read query and return all matching rows.

        Args:
            query:  SQL statement.
            params: Parameter tuple.

        Returns:
            A (possibly empty) list of :class:`sqlite3.Row` objects.
        """
        assert self._conn is not None
        try:
            cursor = self._conn.execute(query, params)
            return cursor.fetchall()
        except sqlite3.DatabaseError as exc:
            logger.error("SQL fetchall failed: %s | query=%s", exc, query)
            raise

    # ------------------------------------------------------------------
    # Row ↔ Model mappers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_application(row: sqlite3.Row) -> Application:
        """Convert a database row to an :class:`Application` model."""
        return Application(
            id=row["id"],
            name=row["name"],
            exe_path=row["exe_path"],
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

    @staticmethod
    def _row_to_usage_record(row: sqlite3.Row) -> UsageRecord:
        """Convert a database row to a :class:`UsageRecord` model."""
        return UsageRecord(
            id=row["id"],
            app_id=row["app_id"],
            date=row["date"],
            usage_seconds=row["usage_seconds"],
            was_blocked=bool(row["was_blocked"]),
        )

    @staticmethod
    def _row_to_usage_session(row: sqlite3.Row) -> UsageSession:
        """Convert a database row to a :class:`UsageSession` model."""
        return UsageSession(
            id=row["id"],
            app_id=row["app_id"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_seconds=row["duration_seconds"],
        )

    @staticmethod
    def _row_to_focus_session(row: sqlite3.Row) -> FocusSession:
        """Convert a database row to a :class:`FocusSession` model."""
        return FocusSession(
            id=row["id"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_seconds=row["duration_seconds"],
            target_duration_seconds=row["target_duration_seconds"],
            apps_blocked=row["apps_blocked"],
            completed=bool(row["completed"]),
        )

    @staticmethod
    def _row_to_blocked_event(row: sqlite3.Row) -> BlockedEvent:
        """Convert a database row to a :class:`BlockedEvent` model."""
        return BlockedEvent(
            id=row["id"],
            app_id=row["app_id"],
            timestamp=row["timestamp"],
            reason=row["reason"],
            action_taken=row["action_taken"],
        )

    # ==================================================================
    # APPLICATION CRUD
    # ==================================================================

    def add_application(self, app: Application) -> int:
        """Insert a new application and return its generated ID.

        Args:
            app: An :class:`Application` instance (``id`` is ignored).

        Returns:
            The auto-generated ``id`` of the new row.
        """
        created_at = app.created_at or now_iso()
        cursor = self._execute(
            """
            INSERT INTO applications
                (name, exe_path, icon_path, daily_limit_seconds, is_active,
                 notify_enabled, grace_period_seconds, block_mode,
                 schedule_start, schedule_end, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                app.name,
                app.exe_path,
                app.icon_path,
                app.daily_limit_seconds,
                int(app.is_active),
                int(app.notify_enabled),
                app.grace_period_seconds,
                app.block_mode,
                app.schedule_start,
                app.schedule_end,
                created_at,
            ),
        )
        new_id = cursor.lastrowid
        logger.info("Added application '%s' (id=%d)", app.name, new_id)
        return new_id  # type: ignore[return-value]

    def get_application(self, app_id: int) -> Optional[Application]:
        """Retrieve an application by ID.

        Args:
            app_id: The application's primary key.

        Returns:
            An :class:`Application` or ``None`` if not found.
        """
        row = self._fetchone(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        )
        if row is None:
            return None
        return self._row_to_application(row)

    def get_application_by_path(self, exe_path: str) -> Optional[Application]:
        """Retrieve an application by its executable path.

        Args:
            exe_path: The normalised path to the ``.exe``.

        Returns:
            An :class:`Application` or ``None`` if not found.
        """
        row = self._fetchone(
            "SELECT * FROM applications WHERE exe_path = ?", (exe_path,)
        )
        if row is None:
            return None
        return self._row_to_application(row)

    def get_all_applications(self) -> list[Application]:
        """Return every registered application.

        Returns:
            A list of :class:`Application` objects, ordered by name.
        """
        rows = self._fetchall(
            "SELECT * FROM applications ORDER BY name COLLATE NOCASE"
        )
        return [self._row_to_application(r) for r in rows]

    def update_application(self, app: Application) -> None:
        """Update an existing application's fields.

        Args:
            app: The :class:`Application` with an ``id`` set. All mutable
                 fields are overwritten.
        """
        if app.id is None:
            logger.warning("Cannot update application without an id")
            return
        self._execute(
            """
            UPDATE applications SET
                name                 = ?,
                exe_path             = ?,
                icon_path            = ?,
                daily_limit_seconds  = ?,
                is_active            = ?,
                notify_enabled       = ?,
                grace_period_seconds = ?,
                block_mode           = ?,
                schedule_start       = ?,
                schedule_end         = ?
            WHERE id = ?
            """,
            (
                app.name,
                app.exe_path,
                app.icon_path,
                app.daily_limit_seconds,
                int(app.is_active),
                int(app.notify_enabled),
                app.grace_period_seconds,
                app.block_mode,
                app.schedule_start,
                app.schedule_end,
                app.id,
            ),
        )
        logger.debug("Updated application id=%d (%s)", app.id, app.name)

    def delete_application(self, app_id: int) -> None:
        """Delete an application and all its related data (cascading).

        Args:
            app_id: The application's primary key.
        """
        self._execute("DELETE FROM applications WHERE id = ?", (app_id,))
        logger.info("Deleted application id=%d", app_id)

    # ==================================================================
    # USAGE HISTORY
    # ==================================================================

    def get_usage_today(self, app_id: int) -> int:
        """Return total usage seconds for *app_id* today.

        Args:
            app_id: Application primary key.

        Returns:
            Seconds of usage today (0 if no record exists).
        """
        return self.get_usage_for_date(app_id, today_str())

    def update_usage_today(self, app_id: int, seconds: int) -> None:
        """Upsert today's usage record for *app_id*.

        Uses ``INSERT … ON CONFLICT … DO UPDATE`` (SQLite 3.24+).

        Args:
            app_id:  Application primary key.
            seconds: Total accumulated seconds for today.
        """
        date = today_str()
        self._execute(
            """
            INSERT INTO usage_history (app_id, date, usage_seconds)
            VALUES (?, ?, ?)
            ON CONFLICT(app_id, date) DO UPDATE SET
                usage_seconds = excluded.usage_seconds
            """,
            (app_id, date, seconds),
        )

    def get_usage_for_date(self, app_id: int, date: str) -> int:
        """Return total usage seconds for *app_id* on a specific date.

        Args:
            app_id: Application primary key.
            date:   Date string ``"YYYY-MM-DD"``.

        Returns:
            Seconds of usage (0 if no record exists).
        """
        row = self._fetchone(
            "SELECT usage_seconds FROM usage_history WHERE app_id = ? AND date = ?",
            (app_id, date),
        )
        if row is None:
            return 0
        return int(row["usage_seconds"])

    def get_all_usage_for_date(self, date: str) -> list[UsageRecord]:
        """Return all apps' usage records for a single date.

        Args:
            date: Date string ``"YYYY-MM-DD"``.

        Returns:
            A list of :class:`UsageRecord` objects.
        """
        rows = self._fetchall(
            "SELECT * FROM usage_history WHERE date = ?", (date,)
        )
        return [self._row_to_usage_record(r) for r in rows]

    def get_usage_range(
        self, app_id: int, start_date: str, end_date: str
    ) -> list[UsageRecord]:
        """Return usage records for one app over a date range.

        Args:
            app_id:     Application primary key.
            start_date: Inclusive start ``"YYYY-MM-DD"``.
            end_date:   Inclusive end ``"YYYY-MM-DD"``.

        Returns:
            A list of :class:`UsageRecord` objects ordered by date.
        """
        rows = self._fetchall(
            """
            SELECT * FROM usage_history
            WHERE app_id = ? AND date BETWEEN ? AND ?
            ORDER BY date
            """,
            (app_id, start_date, end_date),
        )
        return [self._row_to_usage_record(r) for r in rows]

    def get_all_usage_range(
        self, start_date: str, end_date: str
    ) -> list[UsageRecord]:
        """Return all apps' usage records over a date range.

        Args:
            start_date: Inclusive start ``"YYYY-MM-DD"``.
            end_date:   Inclusive end ``"YYYY-MM-DD"``.

        Returns:
            A list of :class:`UsageRecord` objects ordered by date.
        """
        rows = self._fetchall(
            """
            SELECT * FROM usage_history
            WHERE date BETWEEN ? AND ?
            ORDER BY date, app_id
            """,
            (start_date, end_date),
        )
        return [self._row_to_usage_record(r) for r in rows]

    def get_total_usage_for_date(self, date: str) -> int:
        """Return summed usage seconds across all apps for one date.

        Args:
            date: Date string ``"YYYY-MM-DD"``.

        Returns:
            Total seconds of usage across all applications.
        """
        row = self._fetchone(
            "SELECT COALESCE(SUM(usage_seconds), 0) AS total FROM usage_history WHERE date = ?",
            (date,),
        )
        if row is None:
            return 0
        return int(row["total"])

    # ==================================================================
    # USAGE SESSIONS
    # ==================================================================

    def start_session(self, app_id: int) -> int:
        """Begin a new usage session for *app_id*.

        Args:
            app_id: Application primary key.

        Returns:
            The auto-generated session ID.
        """
        cursor = self._execute(
            """
            INSERT INTO usage_sessions (app_id, start_time, duration_seconds)
            VALUES (?, ?, 0)
            """,
            (app_id, now_iso()),
        )
        session_id: int = cursor.lastrowid  # type: ignore[assignment]
        logger.debug("Started session id=%d for app_id=%d", session_id, app_id)
        return session_id

    def end_session(self, session_id: int, duration: int) -> None:
        """Close a usage session with the final duration.

        Args:
            session_id: The session's primary key.
            duration:   Total session duration in seconds.
        """
        self._execute(
            """
            UPDATE usage_sessions SET
                end_time         = ?,
                duration_seconds = ?
            WHERE id = ?
            """,
            (now_iso(), duration, session_id),
        )
        logger.debug(
            "Ended session id=%d, duration=%ds", session_id, duration
        )

    # ==================================================================
    # FOCUS SESSIONS
    # ==================================================================

    def start_focus_session(self, session: FocusSession) -> int:
        """Begin a new focus session.

        Args:
            session: A :class:`FocusSession` with ``target_duration_seconds``
                     and ``apps_blocked`` set.

        Returns:
            The auto-generated session ID.
        """
        start_time = session.start_time or now_iso()
        cursor = self._execute(
            """
            INSERT INTO focus_sessions
                (start_time, target_duration_seconds, apps_blocked,
                 duration_seconds, completed)
            VALUES (?, ?, ?, 0, 0)
            """,
            (
                start_time,
                session.target_duration_seconds,
                session.apps_blocked,
            ),
        )
        session_id: int = cursor.lastrowid  # type: ignore[assignment]
        logger.info("Started focus session id=%d", session_id)
        return session_id

    def end_focus_session(
        self, session_id: int, completed: bool, duration: int
    ) -> None:
        """Close a focus session.

        Args:
            session_id: The session's primary key.
            completed:  Whether the user finished the target duration.
            duration:   Actual duration in seconds.
        """
        self._execute(
            """
            UPDATE focus_sessions SET
                end_time         = ?,
                duration_seconds = ?,
                completed        = ?
            WHERE id = ?
            """,
            (now_iso(), duration, int(completed), session_id),
        )
        logger.info(
            "Ended focus session id=%d, completed=%s, duration=%ds",
            session_id,
            completed,
            duration,
        )

    def get_focus_sessions(
        self, start_date: str, end_date: str
    ) -> list[FocusSession]:
        """Retrieve focus sessions whose start time falls within a date range.

        Args:
            start_date: Inclusive start ``"YYYY-MM-DD"``.
            end_date:   Inclusive end ``"YYYY-MM-DD"``.

        Returns:
            A list of :class:`FocusSession` objects ordered by start time.
        """
        rows = self._fetchall(
            """
            SELECT * FROM focus_sessions
            WHERE DATE(start_time) BETWEEN ? AND ?
            ORDER BY start_time
            """,
            (start_date, end_date),
        )
        return [self._row_to_focus_session(r) for r in rows]

    def get_active_focus_session(self) -> Optional[FocusSession]:
        """Return the currently-active focus session, if any.

        An active session is one that has a ``start_time`` but no
        ``end_time``.

        Returns:
            A :class:`FocusSession` or ``None``.
        """
        row = self._fetchone(
            """
            SELECT * FROM focus_sessions
            WHERE start_time IS NOT NULL AND end_time IS NULL
            ORDER BY start_time DESC
            LIMIT 1
            """
        )
        if row is None:
            return None
        return self._row_to_focus_session(row)

    # ==================================================================
    # BLOCKED EVENTS
    # ==================================================================

    def log_blocked_event(self, event: BlockedEvent) -> None:
        """Record a block/termination event.

        Args:
            event: A :class:`BlockedEvent` with all required fields set.
        """
        timestamp = event.timestamp or now_iso()
        self._execute(
            """
            INSERT INTO blocked_events (app_id, timestamp, reason, action_taken)
            VALUES (?, ?, ?, ?)
            """,
            (event.app_id, timestamp, event.reason, event.action_taken),
        )
        logger.info(
            "Logged blocked event: app_id=%d reason=%s action=%s",
            event.app_id,
            event.reason,
            event.action_taken,
        )

    def get_blocked_events(
        self, start_date: str, end_date: str
    ) -> list[BlockedEvent]:
        """Retrieve blocked events within a date range.

        Args:
            start_date: Inclusive start ``"YYYY-MM-DD"``.
            end_date:   Inclusive end ``"YYYY-MM-DD"``.

        Returns:
            A list of :class:`BlockedEvent` objects ordered by timestamp.
        """
        rows = self._fetchall(
            """
            SELECT * FROM blocked_events
            WHERE DATE(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp
            """,
            (start_date, end_date),
        )
        return [self._row_to_blocked_event(r) for r in rows]

    def get_blocked_count_today(self) -> int:
        """Return the number of block events recorded today.

        Returns:
            Count of today's blocked events.
        """
        row = self._fetchone(
            """
            SELECT COUNT(*) AS cnt FROM blocked_events
            WHERE DATE(timestamp) = ?
            """,
            (today_str(),),
        )
        if row is None:
            return 0
        return int(row["cnt"])

    # ==================================================================
    # SETTINGS (key-value store)
    # ==================================================================

    def get_setting(self, key: str, default: str = "") -> str:
        """Read a setting value by key.

        Args:
            key:     The setting key.
            default: Fallback if the key does not exist.

        Returns:
            The stored value string, or *default*.
        """
        row = self._fetchone(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        if row is None:
            return default
        return str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        """Upsert a setting value.

        Args:
            key:   The setting key.
            value: The value to store.
        """
        self._execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    # ==================================================================
    # MAINTENANCE
    # ==================================================================

    def backup(self, backup_path: str) -> bool:
        """Create a hot backup using the SQLite backup API.

        This is safe to call while the database is in use.

        Args:
            backup_path: Destination file path for the backup.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        try:
            os.makedirs(os.path.dirname(backup_path) or ".", exist_ok=True)
            with self._lock:
                assert self._conn is not None
                dest = sqlite3.connect(backup_path)
                try:
                    self._conn.backup(dest)
                finally:
                    dest.close()
            logger.info("Database backed up to %s", backup_path)
            return True
        except (sqlite3.Error, OSError) as exc:
            logger.error("Database backup failed: %s", exc)
            return False

    def restore(self, backup_path: str) -> bool:
        """Restore the database from a backup file.

        The current database is replaced in-place.

        Args:
            backup_path: Path to the backup ``.db`` file.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        if not os.path.isfile(backup_path):
            logger.error("Restore failed — backup not found: %s", backup_path)
            return False

        try:
            with self._lock:
                assert self._conn is not None
                source = sqlite3.connect(backup_path)
                try:
                    source.backup(self._conn)
                finally:
                    source.close()
            logger.info("Database restored from %s", backup_path)
            return True
        except (sqlite3.Error, OSError) as exc:
            logger.error("Database restore failed: %s", exc)
            return False

    def close(self) -> None:
        """Close the database connection and release resources."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                    logger.info("Database connection closed")
                except sqlite3.Error as exc:
                    logger.error("Error closing database: %s", exc)
                finally:
                    self._conn = None

    # ------------------------------------------------------------------
    # Public compatibility API
    # ------------------------------------------------------------------
    # Several service modules call db.execute() / db.fetch_one() / etc.
    # directly instead of using the higher-level named methods.  These
    # thin wrappers ensure backward-compatibility.

    @property
    def db_path(self) -> str:
        """Return the path to the database file."""
        return self._db_path

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Public wrapper around :meth:`_execute`."""
        return self._execute(query, params)

    def fetch_one(
        self, query: str, params: tuple = ()
    ) -> Optional[sqlite3.Row]:
        """Public wrapper around :meth:`_fetchone`."""
        return self._fetchone(query, params)

    def fetch_all(
        self, query: str, params: tuple = ()
    ) -> list[sqlite3.Row]:
        """Public wrapper around :meth:`_fetchall`."""
        return self._fetchall(query, params)

    def get_connection(self) -> sqlite3.Connection:
        """Return the underlying connection (use with caution)."""
        assert self._conn is not None, "Database connection is closed"
        return self._conn

