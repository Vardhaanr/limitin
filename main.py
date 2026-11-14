"""
Limitin Desktop — Entry Point

Bootstraps logging, loads configuration, opens the database, and launches
the main application window.

Usage:
    python main.py
"""

from __future__ import annotations

import os
import sys

# Ensure the project root is on sys.path so that all package imports resolve.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import customtkinter as ctk

from utils.logger import get_logger, setup_logging
from utils.storage import ConfigManager
from database.database import DatabaseManager

# ── Bootstrap logging ────────────────────────────────────────────────────────
setup_logging()
logger = get_logger("main")


def main() -> None:
    """Application entry point."""
    logger.info("=" * 60)
    logger.info("Limitin Desktop starting")
    logger.info("=" * 60)

    # ── Configuration ────────────────────────────────────────────────────
    config = ConfigManager()
    logger.info("Configuration loaded from %s", config._path)

    # ── Appearance ───────────────────────────────────────────────────────
    appearance = config.get("appearance.mode", "dark")
    ctk.set_appearance_mode(appearance)
    logger.info("Appearance mode: %s", appearance)

    # ── Database ─────────────────────────────────────────────────────────
    db_path = config.get("database.path", "data/limitin.db")
    db = DatabaseManager(db_path)
    logger.info("Database ready at %s", db.db_path)

    # ── Launch main window ───────────────────────────────────────────────
    from app import LimitinApp

    app = LimitinApp(config=config, db=db)
    logger.info("Entering main loop")
    app.mainloop()

    # ── Cleanup ──────────────────────────────────────────────────────────
    logger.info("Limitin Desktop shut down cleanly")


if __name__ == "__main__":
    main()