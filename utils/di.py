from typing import TypeVar, Type, Callable, Any, Optional
from services.logger import get_logger

T = TypeVar('T')


class ServiceLocator:
    """Simple service locator for dependency injection."""
    
    def __init__(self):
        self.logger = get_logger()
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._singletons: dict[str, bool] = {}
    
    def register(self, service_type: Type[T], instance: T, singleton: bool = True):
        """Register a service instance."""
        name = service_type.__name__
        self._services[name] = instance
        self._singletons[name] = singleton
        self.logger.debug(f"Registered service: {name}")
    
    def register_factory(self, service_type: Type[T], factory: Callable[[], T], 
                        singleton: bool = True):
        """Register a factory function for a service."""
        name = service_type.__name__
        self._factories[name] = factory
        self._singletons[name] = singleton
        self.logger.debug(f"Registered factory for: {name}")
    
    def get(self, service_type: Type[T]) -> Optional[T]:
        """Get a service instance."""
        name = service_type.__name__
        
        # Check if instance already exists
        if name in self._services:
            return self._services[name]
        
        # Check if factory exists
        if name in self._factories:
            instance = self._factories[name]()
            
            if self._singletons.get(name, True):
                self._services[name] = instance
            
            return instance
        
        self.logger.warning(f"Service not found: {name}")
        return None
    
    def has(self, service_type: Type[T]) -> bool:
        """Check if a service is registered."""
        name = service_type.__name__
        return name in self._services or name in self._factories
    
    def clear(self):
        """Clear all registered services."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self.logger.debug("Cleared all services")


# Global service locator instance
_service_locator: Optional[ServiceLocator] = None


def get_service_locator() -> ServiceLocator:
    """Get the global service locator instance."""
    global _service_locator
    if _service_locator is None:
        _service_locator = ServiceLocator()
    return _service_locator


def reset_service_locator():
    """Reset the global service locator instance (for testing)."""
    global _service_locator
    _service_locator = None


def initialize_services():
    """Initialize and register all core services."""
    from database.schema import Database, get_database
    from services.settings import SettingsManager, get_settings
    from services.logger import LimitinLogger, get_logger
    from services.state import StateManager, get_state_manager
    from core.background import BackgroundService, UIUpdateScheduler, \
        get_background_service, get_ui_scheduler
    
    locator = get_service_locator()
    
    # Register core services
    locator.register(Database, get_database())
    locator.register(SettingsManager, get_settings())
    locator.register(LimitinLogger, get_logger())
    locator.register(StateManager, get_state_manager())
    locator.register(BackgroundService, get_background_service())
    locator.register(UIUpdateScheduler, get_ui_scheduler())
