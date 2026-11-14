"""
Limitin Desktop — Database Schema Compatibility Layer

Re-exports ``DatabaseManager`` as ``Database`` so that modules importing
``from database.schema import Database`` continue to work.
"""

from __future__ import annotations

from database.database import DatabaseManager

# Alias for backward-compatibility with modules that import ``Database``
Database = DatabaseManager


def get_database() -> Database:
    """Get a default database instance.

    Prefer injecting a ``DatabaseManager`` explicitly via constructor.
    This is provided for convenience in auxiliary/utility modules.
    """
    return Database()
