"""
Opal Desktop — Window Detector Service

Detects the currently focused window on Windows using Win32 APIs.
Provides process information including executable path, PID, and window title.
Handles edge cases: system processes, UWP apps, minimized windows, access denied.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import psutil
import win32con
import win32gui
import win32process

from services.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """Information about the currently focused window."""

    hwnd: int
    pid: int
    process_name: str          # e.g., 'chrome.exe'
    exe_path: str              # Full path to the executable
    window_title: str
    is_minimized: bool

    @property
    def exe_name_lower(self) -> str:
        """Lowercase executable name for case-insensitive comparisons."""
        return self.process_name.lower()


# System-level process names that should be ignored during tracking.
_SYSTEM_PROCESSES: frozenset[str] = frozenset({
    "explorer.exe",
    "searchui.exe",
    "searchhost.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "lockapp.exe",
    "systemsettings.exe",
    "textinputhost.exe",
    "runtimebroker.exe",
    "applicationframehost.exe",
    "dwm.exe",
    "csrss.exe",
    "winlogon.exe",
    "taskmgr.exe",
})


class WindowDetector:
    """Detects the currently focused (foreground) window on Windows.

    Uses Win32 APIs to identify the foreground window, its owning process,
    and metadata. Designed for repeated polling from the tracking loop.
    """

    def __init__(self) -> None:
        """Initialise the window detector."""
        self._last_hwnd: int = 0
        self._last_info: Optional[WindowInfo] = None
        logger.debug("WindowDetector initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_foreground_window(self) -> Optional[WindowInfo]:
        """Get information about the currently focused window.

        Returns:
            WindowInfo with process details, or None when detection fails
            (e.g. desktop is focused, system process, access denied).
        """
        try:
            hwnd: int = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return None

            # Quick path: if the same HWND as last call, return cached info
            # with an updated minimised flag (it can change between polls).
            if hwnd == self._last_hwnd and self._last_info is not None:
                current_minimized = self.is_window_minimized(hwnd)
                if current_minimized == self._last_info.is_minimized:
                    return self._last_info
                # Rebuild with updated minimised state
                info = WindowInfo(
                    hwnd=self._last_info.hwnd,
                    pid=self._last_info.pid,
                    process_name=self._last_info.process_name,
                    exe_path=self._last_info.exe_path,
                    window_title=self._last_info.window_title,
                    is_minimized=current_minimized,
                )
                self._last_info = info
                return info

            # Resolve PID from window handle
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                logger.debug("Failed to get PID for HWND %s", hwnd)
                return None

            if pid <= 0:
                return None

            # Get executable path
            exe_path = self.get_process_exe_path(pid)
            if exe_path is None:
                return None

            process_name = os.path.basename(exe_path).lower()

            # Skip known system / shell processes
            if process_name in _SYSTEM_PROCESSES:
                return None

            # Window title
            try:
                window_title: str = win32gui.GetWindowText(hwnd) or ""
            except Exception:
                window_title = ""

            is_minimized = self.is_window_minimized(hwnd)

            info = WindowInfo(
                hwnd=hwnd,
                pid=pid,
                process_name=process_name,
                exe_path=exe_path,
                window_title=window_title,
                is_minimized=is_minimized,
            )

            # Cache for fast-path on next poll
            self._last_hwnd = hwnd
            self._last_info = info
            return info

        except Exception:
            logger.exception("Unexpected error detecting foreground window")
            return None

    def is_window_minimized(self, hwnd: int) -> bool:
        """Check if a window handle refers to a minimised window.

        Args:
            hwnd: The Win32 window handle.

        Returns:
            True if the window is minimised (iconic), False otherwise or on
            error.
        """
        try:
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement is None:
                return False
            # placement is a tuple: (flags, showCmd, minPos, maxPos, normalPos)
            show_cmd = placement[1]
            return show_cmd == win32con.SW_SHOWMINIMIZED
        except Exception:
            # Window may have been destroyed between detection and this call
            return False

    def get_process_exe_path(self, pid: int) -> Optional[str]:
        """Get the full executable path for a process ID.

        Handles psutil.AccessDenied and psutil.NoSuchProcess gracefully.

        Args:
            pid: The process identifier.

        Returns:
            Absolute path to the .exe, or None on failure.
        """
        try:
            proc = psutil.Process(pid)
            exe_path: Optional[str] = proc.exe()
            if exe_path and os.path.isfile(exe_path):
                return os.path.normpath(exe_path)
            # Some UWP/store apps return empty or invalid paths
            return None
        except psutil.AccessDenied:
            logger.debug("Access denied for PID %d", pid)
            return None
        except psutil.NoSuchProcess:
            logger.debug("Process %d no longer exists", pid)
            return None
        except psutil.ZombieProcess:
            logger.debug("Process %d is a zombie", pid)
            return None
        except Exception:
            logger.debug("Failed to get exe path for PID %d", pid, exc_info=True)
            return None
