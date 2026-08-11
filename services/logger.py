"""
Opal Desktop — Services Logger Compatibility Layer

Re-exports ``get_logger`` from :mod:`utils.logger` so that modules importing
``from services.logger import get_logger`` continue to work.
"""

from utils.logger import get_logger, setup_logging  # noqa: F401

__all__ = ["get_logger", "setup_logging"]
