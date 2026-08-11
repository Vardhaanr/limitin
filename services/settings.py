import json
from typing import Any, Optional
from database.schema import get_database


class SettingsManager:
    """Manages application settings with persistence."""
    
    # Default settings
    DEFAULTS = {
        "theme": "dark",
        "accent_color": "#3b82f6",
        "window_width": 1060,
        "window_height": 640,
        "sidebar_width": 230,
        "notifications_enabled": True,
        "sound_enabled": True,
        "strict_mode": False,
        "auto_start": False,
        "minimize_to_tray": True,
        "daily_reset_time": "00:00",
        "focus_mode_duration": 25,
        "break_duration": 5,
        "long_break_duration": 15,
    }
    
    def __init__(self):
        self.db = get_database()
        self._cache: dict[str, Any] = {}
        self._load_defaults()
    
    def _load_defaults(self):
        """Load default settings into cache."""
        self._cache = self.DEFAULTS.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        # Check cache first
        if key in self._cache:
            return self._cache[key]
        
        # Check database
        row = self.db.fetch_one(
            "SELECT value, value_type FROM settings WHERE key = ?",
            (key,)
        )
        
        if row:
            value = self._deserialize_value(row['value'], row['value_type'])
            self._cache[key] = value
            return value
        
        # Return default
        if default is not None:
            return default
        return self.DEFAULTS.get(key)
    
    def set(self, key: str, value: Any) -> bool:
        """Set a setting value."""
        value_str, value_type = self._serialize_value(value)
        
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO settings (key, value, value_type)
                VALUES (?, ?, ?)
            """, (key, value_str, value_type))
            conn.commit()
        
        self._cache[key] = value
        return True
    
    def delete(self, key: str) -> bool:
        """Delete a setting (reverts to default)."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))
            conn.commit()
        
        if key in self._cache:
            del self._cache[key]
        
        return True
    
    def get_all(self) -> dict[str, Any]:
        """Get all settings."""
        rows = self.db.fetch_all("SELECT key, value, value_type FROM settings")
        
        for row in rows:
            key = row['key']
            value = self._deserialize_value(row['value'], row['value_type'])
            self._cache[key] = value
        
        return {**self.DEFAULTS, **self._cache}
    
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM settings")
            conn.commit()
        
        self._cache.clear()
        self._load_defaults()
    
    def _serialize_value(self, value: Any) -> tuple[str, str]:
        """Serialize a value for storage."""
        if isinstance(value, bool):
            return str(int(value)), "bool"
        elif isinstance(value, int):
            return str(value), "int"
        elif isinstance(value, float):
            return str(value), "float"
        elif isinstance(value, (dict, list)):
            return json.dumps(value), "json"
        else:
            return str(value), "string"
    
    def _deserialize_value(self, value_str: str, value_type: str) -> Any:
        """Deserialize a value from storage."""
        if value_type == "bool":
            return bool(int(value_str))
        elif value_type == "int":
            return int(value_str)
        elif value_type == "float":
            return float(value_str)
        elif value_type == "json":
            return json.loads(value_str)
        else:
            return value_str


# Global settings instance
_settings_instance: Optional[SettingsManager] = None


def get_settings() -> SettingsManager:
    """Get the global settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = SettingsManager()
    return _settings_instance


def reset_settings():
    """Reset the global settings instance (for testing)."""
    global _settings_instance
    _settings_instance = None
