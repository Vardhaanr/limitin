from typing import Any, Callable, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum
import threading
from services.logger import get_logger
from database.schema import get_database


class AppState(Enum):
    """Application states."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class AppLimit:
    """Represents an app limit."""
    id: int
    app_name: str
    limit_minutes: int
    limit_type: str = "daily"
    is_active: bool = True
    elapsed_seconds: int = 0
    
    @property
    def elapsed_minutes(self) -> int:
        return self.elapsed_seconds // 60
    
    @property
    def remaining_seconds(self) -> int:
        return max(0, (self.limit_minutes * 60) - self.elapsed_seconds)
    
    @property
    def remaining_minutes(self) -> int:
        return self.remaining_seconds // 60
    
    @property
    def progress_ratio(self) -> float:
        if self.limit_minutes <= 0:
            return 0.0
        return min(1.0, self.elapsed_seconds / (self.limit_minutes * 60))


@dataclass
class UsageSession:
    """Represents a usage session."""
    id: int
    app_id: int
    app_name: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: int = 0


class StateManager:
    """Manages application state with persistence and notifications."""
    
    def __init__(self):
        self.logger = get_logger()
        self.db = get_database()
        
        self._state = AppState.INITIALIZING
        self._limits: Dict[int, AppLimit] = {}
        self._listeners: Dict[str, list[Callable]] = {}
        self._lock = threading.Lock()
        
        self._load_state()
    
    def _load_state(self):
        """Load state from database."""
        self.logger.info("Loading application state")
        
        # Load active limits
        rows = self.db.fetch_all("""
            SELECT l.id, a.name, l.limit_minutes, l.limit_type, l.is_active
            FROM limits l
            JOIN apps a ON l.app_id = a.id
            WHERE l.is_active = 1
        """)
        
        for row in rows:
            limit = AppLimit(
                id=row['id'],
                app_name=row['name'],
                limit_minutes=row['limit_minutes'],
                limit_type=row['limit_type'],
                is_active=bool(row['is_active'])
            )
            self._limits[limit.id] = limit
        
        self._state = AppState.RUNNING
        self.logger.info(f"Loaded {len(self._limits)} active limits")
    
    def get_state(self) -> AppState:
        """Get current application state."""
        return self._state
    
    def set_state(self, state: AppState):
        """Set application state."""
        old_state = self._state
        self._state = state
        self.logger.info(f"State changed: {old_state.value} -> {state.value}")
        self._notify_listeners("state", old_state, state)
    
    def get_limits(self) -> list[AppLimit]:
        """Get all active limits."""
        with self._lock:
            return list(self._limits.values())
    
    def get_limit(self, limit_id: int) -> Optional[AppLimit]:
        """Get a specific limit by ID."""
        with self._lock:
            return self._limits.get(limit_id)
    
    def get_limit_by_app(self, app_name: str) -> Optional[AppLimit]:
        """Get a limit by app name."""
        with self._lock:
            for limit in self._limits.values():
                if limit.app_name.lower() == app_name.lower():
                    return limit
            return None
    
    def add_limit(self, app_name: str, limit_minutes: int, 
                  limit_type: str = "daily") -> AppLimit:
        """Add a new app limit."""
        self.logger.info(f"Adding limit for {app_name}: {limit_minutes} min ({limit_type})")
        
        # First, ensure app exists
        app_row = self.db.fetch_one(
            "SELECT id FROM apps WHERE name = ?",
            (app_name,)
        )
        
        if not app_row:
            # Create app
            self.db.execute(
                "INSERT INTO apps (name, process_name) VALUES (?, ?)",
                (app_name, app_name.lower())
            )
            app_row = self.db.fetch_one(
                "SELECT id FROM apps WHERE name = ?",
                (app_name,)
            )
        
        app_id = app_row['id']
        
        # Create limit
        self.db.execute(
            """INSERT INTO limits (app_id, limit_minutes, limit_type, is_active)
               VALUES (?, ?, ?, 1)""",
            (app_id, limit_minutes, limit_type)
        )
        
        limit_row = self.db.fetch_one(
            "SELECT id FROM limits WHERE app_id = ? ORDER BY id DESC LIMIT 1",
            (app_id,)
        )
        
        limit = AppLimit(
            id=limit_row['id'],
            app_name=app_name,
            limit_minutes=limit_minutes,
            limit_type=limit_type,
            is_active=True
        )
        
        with self._lock:
            self._limits[limit.id] = limit
        
        self._notify_listeners("limit_added", None, limit)
        return limit
    
    def update_limit_elapsed(self, limit_id: int, elapsed_seconds: int):
        """Update elapsed time for a limit."""
        with self._lock:
            if limit_id in self._limits:
                old_elapsed = self._limits[limit_id].elapsed_seconds
                self._limits[limit_id].elapsed_seconds = elapsed_seconds
                
                if old_elapsed != elapsed_seconds:
                    self._notify_listeners(
                        "limit_updated",
                        self._limits[limit_id],
                        elapsed_seconds
                    )
    
    def remove_limit(self, limit_id: int) -> bool:
        """Remove a limit."""
        with self._lock:
            if limit_id not in self._limits:
                return False
            
            limit = self._limits.pop(limit_id)
        
        # Deactivate in database
        self.db.execute(
            "UPDATE limits SET is_active = 0 WHERE id = ?",
            (limit_id,)
        )
        
        self.logger.info(f"Removed limit for {limit.app_name}")
        self._notify_listeners("limit_removed", limit, None)
        return True
    
    def register_listener(self, event: str, callback: Callable):
        """Register a listener for state changes."""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)
    
    def unregister_listener(self, event: str, callback: Callable):
        """Unregister a listener."""
        if event in self._listeners:
            self._listeners[event] = [
                cb for cb in self._listeners[event] if cb != callback
            ]
    
    def _notify_listeners(self, event: str, old_value: Any, new_value: Any):
        """Notify listeners of a state change."""
        if event in self._listeners:
            for callback in self._listeners[event]:
                try:
                    callback(old_value, new_value)
                except Exception as e:
                    self.logger.error(f"Listener error for {event}: {e}", exc_info=True)
    
    def save_usage_session(self, app_id: int, limit_id: Optional[int],
                          start_time: str, end_time: str, duration_seconds: int):
        """Save a usage session to database."""
        from datetime import datetime
        
        session_date = datetime.fromisoformat(start_time).date().isoformat()
        
        self.db.execute(
            """INSERT INTO usage_sessions 
               (app_id, limit_id, start_time, end_time, duration_seconds, session_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (app_id, limit_id, start_time, end_time, duration_seconds, session_date)
        )
        
        self.logger.debug(f"Saved usage session: {duration_seconds}s for app_id {app_id}")


# Global state instance
_state_instance: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get the global state manager instance."""
    global _state_instance
    if _state_instance is None:
        _state_instance = StateManager()
    return _state_instance


def reset_state_manager():
    """Reset the global state manager instance (for testing)."""
    global _state_instance
    _state_instance = None
