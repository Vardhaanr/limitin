"""
Limitin Desktop — Centralized Logging

Provides rotating file handler + console output with configurable levels.
File logs capture DEBUG+, console shows INFO+ (with color when supported).

Usage:
    from utils.logger import setup_logging, get_logger
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Application started")
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
_SETUP_DONE: bool = False

# ANSI colour codes used when the console supports them
_LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG:    "\033[36m",   # Cyan
    logging.INFO:     "\033[32m",   # Green
    logging.WARNING:  "\033[33m",   # Yellow
    logging.ERROR:    "\033[31m",   # Red
    logging.CRITICAL: "\033[1;31m", # Bold Red
}
_RESET: Final[str] = "\033[0m"


# ---------------------------------------------------------------------------
# Coloured Formatter (console only)
# ---------------------------------------------------------------------------

class _ColoredFormatter(logging.Formatter):
    """Adds ANSI color codes to log level names for terminal output."""

    def __init__(self, fmt: str, datefmt: str | None = None) -> None:
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format *record* with colour applied to the level name."""
        color = _LEVEL_COLORS.get(record.levelno, "")
        if color:
            record.levelname = f"{color}{record.levelname}{_RESET}"
        return super().format(record)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    """Return ``True`` when the current stdout supports ANSI colours."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    # Windows 10+ supports ANSI natively; older versions do not.
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            # Enable VIRTUAL_TERMINAL_PROCESSING on the stdout handle.
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
            return True
        except Exception:
            return False
    return True


def _build_log_filename() -> str:
    """Return the log filename for the current day, e.g. ``limitin_2026-07-07.log``."""
    return f"limitin_{datetime.now().strftime('%Y-%m-%d')}.log"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging(
    log_dir: str = "logs",
    max_files: int = 10,
    max_size_mb: int = 5,
) -> None:
    """Initialise the root logger with rotating file + console handlers.

    This function is idempotent — calling it more than once is safe and has
    no effect after the first invocation.

    Args:
        log_dir:      Directory to store log files (created if missing).
        max_files:    Maximum number of rotated backup files to keep.
        max_size_mb:  Maximum size of a single log file in megabytes before
                      rotation occurs.
    """
    global _SETUP_DONE  # noqa: PLW0603
    if _SETUP_DONE:
        return

    # Resolve log directory relative to the application root.
    if not os.path.isabs(log_dir):
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(app_root, log_dir)

    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers if the root logger already has them.
    if root_logger.handlers:
        root_logger.handlers.clear()

    # ------------------------------------------------------------------
    # File handler — DEBUG level, rotating
    # ------------------------------------------------------------------
    log_path = os.path.join(log_dir, _build_log_filename())
    try:
        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=max_files,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        root_logger.addHandler(file_handler)
    except OSError as exc:
        # If we cannot write to the log directory, emit a warning to stderr
        # but do not crash the application.
        sys.stderr.write(f"[Limitin] Unable to create log file at {log_path}: {exc}\n")

    # ------------------------------------------------------------------
    # Console handler — INFO level, coloured if supported
    # ------------------------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    if _supports_color():
        console_handler.setFormatter(_ColoredFormatter(LOG_FORMAT, DATE_FORMAT))
    else:
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    root_logger.addHandler(console_handler)

    _SETUP_DONE = True
    root_logger.debug("Logging initialised — file: %s", log_path)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    If :func:`setup_logging` has not been called yet it is called
    automatically with default parameters so that every ``get_logger``
    call returns a fully configured logger.

    Args:
        name: The logger name, typically ``__name__``.

    Returns:
        A :class:`logging.Logger` instance.
    """
    if not _SETUP_DONE:
        setup_logging()
    return logging.getLogger(name)
