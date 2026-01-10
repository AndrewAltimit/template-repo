"""Desktop control backends for different platforms"""

from .base import DesktopBackend, ScreenInfo, WindowInfo
from .factory import get_backend

__all__ = ["DesktopBackend", "WindowInfo", "ScreenInfo", "get_backend"]
