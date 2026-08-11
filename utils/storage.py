"""
Opal Desktop — Configuration Management & Data Import/Export

Provides:
  - ``ConfigManager``:  JSON-based configuration with dot-path access,
    atomic saves, and automatic defaults merging.
  - ``export_usage_csv`` / ``import_usage_csv``: CSV round-tripping for
    usage records.
  - ``backup_database`` / ``list_backups``: Database backup utilities.

Usage:
    from utils.storage import ConfigManager, export_usage_csv
    config = ConfigManager()
    accent = config.get("appearance.accent_color", "#7C3AED")
"""

from __future__ import annotations

import copy
import csv
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Default application configuration
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: dict[str, Any] = {
    "appearance": {
        "theme": "dark",
        "accent_color": "#7C3AED",
        "font_family": "Segoe UI",
        "font_size": 13,
        "sidebar_width": 260,
    },
    "monitoring": {
        "poll_interval_ms": 1000,
        "track_idle": True,
        "idle_timeout_seconds": 300,
        "auto_detect_apps": True,
    },
    "notifications": {
        "enabled": True,
        "sound_enabled": True,
        "warning_threshold": 0.8,
        "warning_interval_seconds": 300,
    },
    "blocking": {
        "default_mode": "warn_then_block",
        "grace_period_seconds": 60,
        "default_daily_limit_seconds": 3600,
    },
    "focus": {
        "default_duration_minutes": 25,
        "break_duration_minutes": 5,
        "auto_start_break": False,
    },
    "data": {
        "database_path": "data/opal.db",
        "backup_dir": "data/backups",
        "max_backups": 10,
        "export_dir": "data/exports",
    },
    "general": {
        "start_with_windows": False,
        "minimize_to_tray": True,
        "start_minimized": False,
        "check_updates": True,
        "language": "en",
    },
}


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class ConfigManager:
    """JSON-backed configuration store with dot-path access and atomic writes.

    The config file is automatically created with sensible defaults if it
    does not exist.  Missing keys are merged from the defaults dict on
    load so that newly added settings are always available.

    Args:
        config_path: Path (relative to project root or absolute) to the
                     JSON configuration file.
    """

    def __init__(self, config_path: str = "config/config.json") -> None:
        if not os.path.isabs(config_path):
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(app_root, config_path)
        self._path: str = config_path
        self._data: dict[str, Any] = {}
        self._load()

    # -- Public API --------------------------------------------------------

    def get(self, key_path: str, default: Any = None) -> Any:
        """Retrieve a value by dot-separated path.

        Args:
            key_path: Dot-separated key such as ``"appearance.accent_color"``.
            default:  Fallback value if the key is not found.

        Returns:
            The stored value, or *default*.
        """
        keys = key_path.split(".")
        current: Any = self._data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def set(self, key_path: str, value: Any) -> None:
        """Set a value at the given dot-separated path.

        Intermediate dictionaries are created automatically when they
        do not exist.

        Args:
            key_path: Dot-separated key.
            value:    The value to store.
        """
        keys = key_path.split(".")
        current = self._data
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        logger.debug("Config set: %s = %r", key_path, value)

    def save(self) -> None:
        """Persist the current configuration to disk atomically.

        Writes to a temporary file first, then atomically replaces the
        target.  This prevents data loss on crash.
        """
        config_dir = os.path.dirname(self._path)
        os.makedirs(config_dir, exist_ok=True)

        try:
            fd, tmp_path = tempfile.mkstemp(
                suffix=".json",
                prefix=".opal_config_",
                dir=config_dir,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, indent=2, ensure_ascii=False)
                    fh.write("\n")
            except Exception:
                # On write failure, remove the temp file and re-raise.
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            # Atomic rename (Windows: os.replace is atomic within same volume).
            os.replace(tmp_path, self._path)
            logger.debug("Configuration saved to %s", self._path)
        except OSError as exc:
            logger.error("Failed to save configuration: %s", exc)
            raise

    def reload(self) -> None:
        """Re-read the configuration from disk."""
        self._load()
        logger.debug("Configuration reloaded from %s", self._path)

    def get_default_config(self) -> dict[str, Any]:
        """Return a deep copy of the hardcoded default configuration.

        Returns:
            A new ``dict`` matching the default schema.
        """
        return copy.deepcopy(_DEFAULT_CONFIG)

    def reset_to_defaults(self) -> None:
        """Replace the in-memory config with defaults and persist."""
        self._data = copy.deepcopy(_DEFAULT_CONFIG)
        self.save()
        logger.info("Configuration reset to defaults")

    # -- Internal helpers --------------------------------------------------

    def _load(self) -> None:
        """Load and merge the config from disk, falling back to defaults."""
        defaults = copy.deepcopy(_DEFAULT_CONFIG)
        if os.path.isfile(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    user_data = json.load(fh)
                if isinstance(user_data, dict):
                    self._data = self._deep_merge(defaults, user_data)
                    logger.debug("Configuration loaded from %s", self._path)
                    return
                else:
                    logger.warning(
                        "Config file contains non-dict root — using defaults"
                    )
            except json.JSONDecodeError as exc:
                logger.warning(
                    "Corrupt config file %s (%s) — using defaults",
                    self._path,
                    exc,
                )
            except OSError as exc:
                logger.warning("Cannot read config file %s: %s", self._path, exc)
        else:
            logger.info(
                "Config file not found at %s — creating with defaults", self._path
            )

        self._data = defaults
        # Persist so the file exists on disk for the first time.
        try:
            self.save()
        except OSError:
            pass  # Non-fatal — we keep the in-memory defaults.

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge *override* into *base*.

        Keys present in *override* win; missing keys inherit from *base*.

        Returns:
            A new merged dict.
        """
        merged = base.copy()
        for key, value in override.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = ConfigManager._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged


# ---------------------------------------------------------------------------
# CSV export / import
# ---------------------------------------------------------------------------

def export_usage_csv(records: list[Any], output_path: str) -> bool:
    """Export a list of usage records to a CSV file.

    Each record is expected to be a dataclass-like object with the
    attributes ``app_id``, ``date``, ``usage_seconds``, and (optionally)
    ``was_blocked``.

    Args:
        records:     List of usage-record objects.
        output_path: Destination CSV path.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    try:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["app_id", "date", "usage_seconds", "was_blocked"])
            for record in records:
                writer.writerow([
                    getattr(record, "app_id", ""),
                    getattr(record, "date", ""),
                    getattr(record, "usage_seconds", 0),
                    int(getattr(record, "was_blocked", False)),
                ])
        logger.info("Exported %d records to %s", len(records), output_path)
        return True
    except OSError as exc:
        logger.error("CSV export failed: %s", exc)
        return False


def import_usage_csv(input_path: str) -> list[dict[str, Any]]:
    """Import usage records from a CSV file.

    Args:
        input_path: Path to the CSV file.

    Returns:
        A list of dicts with keys ``app_id``, ``date``, ``usage_seconds``,
        ``was_blocked``.  Returns an empty list on failure.
    """
    result: list[dict[str, Any]] = []
    if not os.path.isfile(input_path):
        logger.warning("Import file not found: %s", input_path)
        return result

    try:
        with open(input_path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    result.append({
                        "app_id": int(row.get("app_id", 0)),
                        "date": row.get("date", ""),
                        "usage_seconds": int(row.get("usage_seconds", 0)),
                        "was_blocked": bool(int(row.get("was_blocked", 0))),
                    })
                except (ValueError, TypeError) as exc:
                    logger.debug("Skipping malformed CSV row: %s (%s)", row, exc)
        logger.info("Imported %d records from %s", len(result), input_path)
    except OSError as exc:
        logger.error("CSV import failed: %s", exc)
    return result


# ---------------------------------------------------------------------------
# Database backup helpers
# ---------------------------------------------------------------------------

def backup_database(db_path: str, backup_dir: str) -> str:
    """Copy the SQLite database file to *backup_dir* with a timestamp suffix.

    Args:
        db_path:    Path to the live database file.
        backup_dir: Directory to store backup files.

    Returns:
        The absolute path to the newly created backup file.

    Raises:
        FileNotFoundError: If *db_path* does not exist.
        OSError: On copy failure.
    """
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"opal_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_name)

    try:
        shutil.copy2(db_path, backup_path)
        logger.info("Database backed up to %s", backup_path)
        return os.path.abspath(backup_path)
    except OSError as exc:
        logger.error("Database backup failed: %s", exc)
        raise


def list_backups(backup_dir: str) -> list[dict[str, Any]]:
    """List available database backups sorted newest-first.

    Args:
        backup_dir: Directory containing backup files.

    Returns:
        A list of dicts with keys ``path``, ``filename``, ``size_bytes``,
        ``created_at`` (ISO 8601 string).
    """
    result: list[dict[str, Any]] = []
    if not os.path.isdir(backup_dir):
        return result

    try:
        for entry in os.scandir(backup_dir):
            if entry.is_file() and entry.name.endswith(".db"):
                stat = entry.stat()
                result.append({
                    "path": os.path.abspath(entry.path),
                    "filename": entry.name,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(
                        stat.st_ctime
                    ).isoformat(),
                })
    except OSError as exc:
        logger.error("Failed to list backups in %s: %s", backup_dir, exc)

    result.sort(key=lambda b: b["created_at"], reverse=True)
    return result
