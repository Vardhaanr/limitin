"""
Limitin Desktop — Startup Service

Manages Windows auto-start registration via the ``HKEY_CURRENT_USER``
registry.  Writing to ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``
does **not** require Administrator privileges.

All methods are static since startup registration is a system-level,
stateless operation.
"""

from __future__ import annotations

import sys
import winreg
from typing import Optional

from services.logger import get_logger

logger = get_logger(__name__)


class StartupService:
    """Register / unregister Limitin Desktop for Windows auto-start."""

    REGISTRY_KEY: str = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME: str = "LimitinDesktop"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def is_registered() -> bool:
        """Check whether Limitin is registered to start on Windows login.

        Returns:
            True if the registry value exists under ``HKCU\\...\\Run``.
        """
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                StartupService.REGISTRY_KEY,
                0,
                winreg.KEY_READ,
            )
            try:
                value, _ = winreg.QueryValueEx(key, StartupService.APP_NAME)
                logger.debug("Startup registration found: %s", value)
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except OSError:
            logger.debug("Failed to read startup registry key", exc_info=True)
            return False

    @staticmethod
    def register(exe_path: Optional[str] = None) -> bool:
        """Add Limitin Desktop to Windows startup.

        Writes a ``REG_SZ`` value under the ``Run`` key.  If *exe_path*
        is not provided, ``sys.executable`` is used (suitable when running
        as a frozen PyInstaller bundle or via ``python main.py``).

        Args:
            exe_path: Optional explicit path to the executable.  If None,
                      ``sys.executable`` is used.

        Returns:
            True on success, False on failure.
        """
        if exe_path is None:
            exe_path = sys.executable

        # Wrap the path in quotes to handle spaces
        command: str = f'"{exe_path}"'

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                StartupService.REGISTRY_KEY,
                0,
                winreg.KEY_SET_VALUE,
            )
            try:
                winreg.SetValueEx(
                    key,
                    StartupService.APP_NAME,
                    0,
                    winreg.REG_SZ,
                    command,
                )
            finally:
                winreg.CloseKey(key)

            logger.info("Registered for startup: %s", command)
            return True

        except PermissionError:
            logger.error(
                "Permission denied writing startup registry value. "
                "Run as the current user (not a service account)."
            )
            return False
        except OSError:
            logger.exception("Failed to register for Windows startup")
            return False

    @staticmethod
    def unregister() -> bool:
        """Remove Limitin Desktop from Windows startup.

        Deletes the value from the ``Run`` key.  If the value does not
        exist, this is treated as success (idempotent).

        Returns:
            True on success (or already absent), False on error.
        """
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                StartupService.REGISTRY_KEY,
                0,
                winreg.KEY_SET_VALUE,
            )
            try:
                winreg.DeleteValue(key, StartupService.APP_NAME)
                logger.info("Unregistered from Windows startup")
            except FileNotFoundError:
                logger.debug("Startup value not found — already unregistered")
            finally:
                winreg.CloseKey(key)
            return True

        except PermissionError:
            logger.error("Permission denied removing startup registry value")
            return False
        except OSError:
            logger.exception("Failed to unregister from Windows startup")
            return False
