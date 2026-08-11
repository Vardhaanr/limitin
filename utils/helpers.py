"""
Opal Desktop — General-purpose Utility Helpers

Formatting, path handling, icon extraction, and text manipulation
functions used across every layer of the application.

Usage:
    from utils.helpers import format_duration, safe_path, extract_exe_icon
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Duration formatting
# ---------------------------------------------------------------------------

def format_duration(seconds: int) -> str:
    """Format *seconds* into a concise human string like ``"2h 30m"``.

    Returns ``"0s"`` for zero, ``"30s"`` for values under a minute,
    ``"45m"`` when there are no leftover hours, and ``"2h 30m"`` otherwise.

    Args:
        seconds: Non-negative duration in seconds.

    Returns:
        A compact human-readable duration string.
    """
    if seconds < 0:
        seconds = 0
    if seconds == 0:
        return "0s"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts: list[str] = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if not parts and secs > 0:
        # Only show seconds when total duration < 1 min
        parts.append(f"{secs}s")
    return " ".join(parts)


def format_duration_long(seconds: int) -> str:
    """Format *seconds* into a verbose string like ``"2 hours 30 minutes"``.

    Args:
        seconds: Non-negative duration in seconds.

    Returns:
        A full-text duration string.
    """
    if seconds < 0:
        seconds = 0
    if seconds == 0:
        return "0 seconds"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts: list[str] = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if not parts and secs > 0:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    return " ".join(parts)


def format_duration_digital(seconds: int) -> str:
    """Format *seconds* in digital-clock style ``"02:30:00"``.

    Args:
        seconds: Non-negative duration in seconds.

    Returns:
        A zero-padded ``HH:MM:SS`` string.
    """
    if seconds < 0:
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ---------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------

def format_percentage(value: float) -> str:
    """Format a float as a rounded percentage string (e.g. ``"75%"``).

    Values are clamped to ``[0, 100]`` for display but the raw value
    is accepted unclamped (i.e. >100% is possible).

    Args:
        value: A numeric value where ``1.0`` means 100%.

    Returns:
        A string like ``"75%"``.
    """
    return f"{round(value * 100)}%"


def format_bytes(bytes_val: int) -> str:
    """Format a byte count into a human-readable size string.

    Args:
        bytes_val: Size in bytes (non-negative).

    Returns:
        A string like ``"1.5 GB"`` or ``"256 KB"``.
    """
    if bytes_val < 0:
        bytes_val = 0

    units = ("B", "KB", "MB", "GB", "TB")
    size = float(bytes_val)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    # Unreachable, but satisfies the type checker.
    return f"{size:.1f} TB"  # pragma: no cover


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def safe_path(path: str) -> str:
    """Normalise a file path for consistent comparison on Windows.

    Converts forward slashes to backslashes, resolves ``.``/``..``
    components, and strips trailing separators.

    Args:
        path: A raw file path string.

    Returns:
        A normalised absolute-or-relative path string.
    """
    if not path:
        return path
    return os.path.normpath(path)


def resource_path(relative_path: str) -> str:
    """Return the absolute path to a bundled resource.

    When running from a PyInstaller ``--onefile`` bundle the resources
    live under ``sys._MEIPASS``.  During normal development they are
    resolved relative to the project root.

    Args:
        relative_path: Path relative to the application root.

    Returns:
        The resolved absolute path.
    """
    # PyInstaller sets ``_MEIPASS`` when running from a temp directory.
    base_path: str = getattr(sys, "_MEIPASS", "")
    if not base_path:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def get_app_dir() -> str:
    """Return the application root directory.

    When bundled with PyInstaller the root is the temporary extraction
    directory; otherwise it is the parent of the ``utils/`` package.

    Returns:
        Absolute path to the application root.
    """
    base_path: str = getattr(sys, "_MEIPASS", "")
    if not base_path:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return base_path


# ---------------------------------------------------------------------------
# Icon extraction
# ---------------------------------------------------------------------------

def extract_exe_icon(
    exe_path: str,
    output_dir: str,
    size: tuple[int, int] = (32, 32),
) -> Optional[str]:
    """Extract the main icon from an EXE and save it as a PNG.

    The function first tries ``icoextract`` (pure-Python PE icon
    extraction).  If that fails it falls back to the Win32 API via
    ``win32gui``/``win32ui``/``win32con``.

    Args:
        exe_path:   Absolute path to the ``.exe`` file.
        output_dir: Directory in which to save the PNG icon.
        size:       Target icon size in pixels ``(width, height)``.

    Returns:
        The absolute path to the saved PNG file, or ``None`` on failure.
    """
    if not os.path.isfile(exe_path):
        logger.warning("Icon extraction skipped — file not found: %s", exe_path)
        return None

    os.makedirs(output_dir, exist_ok=True)

    # Derive a stable filename from the executable name.
    exe_name = Path(exe_path).stem.lower()
    sanitized = sanitize_filename(exe_name)
    out_path = os.path.join(output_dir, f"{sanitized}.png")

    # If we already extracted this icon, return the cached version.
    if os.path.isfile(out_path):
        return out_path

    # --- Strategy 1: icoextract (cross-platform, pure-Python) ----------
    icon_image = _extract_via_icoextract(exe_path, size)
    if icon_image is not None:
        try:
            icon_image.save(out_path, "PNG")
            logger.debug("Icon extracted via icoextract: %s", out_path)
            return out_path
        except Exception as exc:
            logger.debug("icoextract save failed: %s", exc)

    # --- Strategy 2: win32gui (Windows-only fallback) ------------------
    icon_image = _extract_via_win32(exe_path, size)
    if icon_image is not None:
        try:
            icon_image.save(out_path, "PNG")
            logger.debug("Icon extracted via win32gui: %s", out_path)
            return out_path
        except Exception as exc:
            logger.debug("win32gui save failed: %s", exc)

    logger.warning("Could not extract icon from %s", exe_path)
    return None


def _extract_via_icoextract(
    exe_path: str,
    size: tuple[int, int],
) -> "Optional[object]":
    """Attempt icon extraction using the ``icoextract`` library.

    Returns:
        A :class:`PIL.Image.Image` or ``None``.
    """
    try:
        import io
        from icoextract import IconExtractor  # type: ignore[import-untyped]
        from PIL import Image  # type: ignore[import-untyped]

        extractor = IconExtractor(exe_path)
        icon_data = extractor.get_icon()
        image = Image.open(io.BytesIO(icon_data.getvalue()))
        image = image.resize(size, Image.LANCZOS)
        return image
    except Exception as exc:
        logger.debug("icoextract failed for %s: %s", exe_path, exc)
        return None


def _extract_via_win32(
    exe_path: str,
    size: tuple[int, int],
) -> "Optional[object]":
    """Attempt icon extraction using Win32 API (``pywin32``).

    Returns:
        A :class:`PIL.Image.Image` or ``None``.
    """
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        import ctypes.wintypes
        from PIL import Image  # type: ignore[import-untyped]

        # Use Shell32 to extract the icon.
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        large_icons = (ctypes.c_void_p * 1)()
        small_icons = (ctypes.c_void_p * 1)()
        count = shell32.ExtractIconExW(exe_path, 0, large_icons, small_icons, 1)
        if count == 0:
            return None

        hicon = large_icons[0] or small_icons[0]
        if not hicon:
            return None

        try:
            import win32gui  # type: ignore[import-untyped]
            import win32ui   # type: ignore[import-untyped]
            import win32con  # type: ignore[import-untyped]

            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, size[0], size[1])
            hdc_mem = hdc.CreateCompatibleDC()
            hdc_mem.SelectObject(hbmp)

            # Fill background with transparent colour
            hdc_mem.FillSolidRect((0, 0, size[0], size[1]), 0x00000000)
            win32gui.DrawIconEx(
                hdc_mem.GetHandleOutput(), 0, 0, hicon,
                size[0], size[1], 0, None, win32con.DI_NORMAL,
            )

            bmpinfo = hbmp.GetInfo()
            bmpstr = hbmp.GetBitmapBits(True)
            image = Image.frombuffer(
                "RGBA",
                (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                bmpstr, "raw", "BGRA", 0, 1,
            )

            # Clean up GDI objects
            hdc_mem.DeleteDC()
            win32gui.ReleaseDC(0, hdc.GetHandleOutput())
            win32gui.DestroyIcon(hicon)

            return image
        except ImportError:
            logger.debug("pywin32 not available for icon extraction fallback")
            if hicon:
                ctypes.windll.user32.DestroyIcon(hicon)  # type: ignore[attr-defined]
            return None
    except Exception as exc:
        logger.debug("win32 icon extraction failed for %s: %s", exe_path, exc)
        return None


# ---------------------------------------------------------------------------
# General-purpose helpers
# ---------------------------------------------------------------------------

def clamp(value: float | int, min_val: float | int, max_val: float | int) -> float | int:
    """Clamp *value* to the range ``[min_val, max_val]``.

    Args:
        value:   The number to clamp.
        min_val: Lower bound.
        max_val: Upper bound.

    Returns:
        The clamped value (preserves the original type when possible).
    """
    if min_val > max_val:
        min_val, max_val = max_val, min_val
    return max(min_val, min(max_val, value))


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate *text* to at most *max_length* characters, appending *suffix*.

    If *text* already fits, it is returned unchanged.

    Args:
        text:       The string to truncate.
        max_length: Maximum allowed character count (including suffix).
        suffix:     The string to append when truncation occurs.

    Returns:
        The (possibly truncated) string.
    """
    if not text or len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return suffix[:max_length]
    return text[: max_length - len(suffix)] + suffix


def is_valid_exe_path(path: str) -> bool:
    """Return ``True`` if *path* points to an existing ``.exe`` file.

    Args:
        path: A file-system path.

    Returns:
        ``True`` if the file exists and has a ``.exe`` extension.
    """
    if not path:
        return False
    try:
        p = Path(path)
        return p.is_file() and p.suffix.lower() == ".exe"
    except (OSError, ValueError):
        return False


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in Windows filenames.

    Args:
        name: A candidate filename (without path separators).

    Returns:
        A sanitised string safe for use as a Windows filename.
    """
    if not name:
        return "unnamed"
    # Strip characters forbidden in NTFS filenames.
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Collapse multiple underscores.
    sanitized = re.sub(r"_+", "_", sanitized).strip("_. ")
    return sanitized or "unnamed"
