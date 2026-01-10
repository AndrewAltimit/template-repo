"""Factory for creating platform-specific desktop control backends"""

import logging
import platform
from typing import Optional

from .base import DesktopBackend

logger = logging.getLogger(__name__)


def get_backend(force_platform: Optional[str] = None) -> DesktopBackend:
    """
    Get the appropriate desktop control backend for the current platform.

    Args:
        force_platform: Force a specific platform ("linux" or "windows")

    Returns:
        DesktopBackend instance for the current/specified platform

    Raises:
        RuntimeError: If no suitable backend is available
    """
    system = force_platform or platform.system().lower()

    if system == "linux":
        from .linux import LinuxBackend

        backend = LinuxBackend()
        if backend.is_available():
            logger.info("Using Linux desktop backend")
            return backend
        else:
            raise RuntimeError(
                "Linux desktop backend not available. Install xdotool: sudo apt-get install xdotool wmctrl scrot"
            )

    elif system == "windows":
        from .windows import WindowsBackend

        backend = WindowsBackend()
        if backend.is_available():
            logger.info("Using Windows desktop backend")
            return backend
        else:
            raise RuntimeError(
                "Windows desktop backend not available. Install dependencies: pip install pywinauto pyautogui mss pywin32"
            )

    elif system == "darwin":
        # macOS support would go here
        raise RuntimeError("macOS is not yet supported. Consider contributing support using pyautogui and applescript.")

    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def get_backend_safe(force_platform: Optional[str] = None) -> Optional[DesktopBackend]:
    """
    Get the desktop backend, returning None instead of raising on failure.

    Args:
        force_platform: Force a specific platform

    Returns:
        DesktopBackend instance or None if unavailable
    """
    try:
        return get_backend(force_platform)
    except RuntimeError as e:
        logger.warning("Desktop backend unavailable: %s", e)
        return None
