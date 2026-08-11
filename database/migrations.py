from .schema import Database, get_database
from typing import Optional
import sqlite3


class MigrationManager:
    """Manages database schema migrations."""
    
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
        self._ensure_migrations_table()
    
    def _ensure_migrations_table(self):
        """Create the migrations tracking table if it doesn't exist."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def get_current_version(self) -> int:
        """Get the current schema version."""
        row = self.db.fetch_one("SELECT MAX(version) as version FROM schema_migrations")
        return row['version'] if row and row['version'] else 0
    
    def apply_migration(self, version: int, sql: str):
        """Apply a migration."""
        with self.db.get_connection() as conn:
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            conn.commit()
    
    def migrate_to_latest(self):
        """Apply all pending migrations."""
        current = self.get_current_version()
        for version, migration in self._get_migrations().items():
            if version > current:
                self.apply_migration(version, migration)
    
    def _get_migrations(self) -> dict[int, str]:
        """Return all migrations indexed by version number."""
        return {
            # Future migrations will be added here
            # Example:
            # 2: """
            # ALTER TABLE apps ADD COLUMN category TEXT;
            # """
        }


def run_migrations():
    """Run all pending database migrations."""
    manager = MigrationManager()
    manager.migrate_to_latest()
