"""Base class and data models for desktop control backends"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class WindowInfo:
    """Information about a window"""

    id: str  # Platform-specific window identifier
    title: str
    x: int
    y: int
    width: int
    height: int
    is_visible: bool = True
    is_minimized: bool = False
    is_maximized: bool = False
    process_id: Optional[int] = None
    process_name: Optional[str] = None
    class_name: Optional[str] = None  # Windows class name or Linux window class
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "title": self.title,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "is_visible": self.is_visible,
            "is_minimized": self.is_minimized,
            "is_maximized": self.is_maximized,
            "process_id": self.process_id,
            "process_name": self.process_name,
            "class_name": self.class_name,
            "extra": self.extra,
        }


@dataclass
class ScreenInfo:
    """Information about a display/monitor"""

    id: int
    x: int
    y: int
    width: int
    height: int
    is_primary: bool = False
    name: Optional[str] = None
    scale_factor: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "is_primary": self.is_primary,
            "name": self.name,
            "scale_factor": self.scale_factor,
        }


class DesktopBackend(ABC):  # pylint: disable=too-many-public-methods
    """Abstract base class for desktop control backends"""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name (e.g., 'linux', 'windows')"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current system"""

    # === Window Management ===

    @abstractmethod
    def list_windows(
        self,
        title_filter: Optional[str] = None,
        visible_only: bool = True,
    ) -> List[WindowInfo]:
        """
        List all windows, optionally filtered by title.

        Args:
            title_filter: Regex pattern to filter window titles
            visible_only: Only return visible windows

        Returns:
            List of WindowInfo objects
        """

    @abstractmethod
    def get_active_window(self) -> Optional[WindowInfo]:
        """Get the currently focused/active window"""

    @abstractmethod
    def focus_window(self, window_id: str) -> bool:
        """
        Bring a window to the foreground and focus it.

        Args:
            window_id: Platform-specific window identifier

        Returns:
            True if successful
        """

    @abstractmethod
    def move_window(self, window_id: str, x: int, y: int) -> bool:
        """
        Move a window to a specific position.

        Args:
            window_id: Window identifier
            x: New X position
            y: New Y position

        Returns:
            True if successful
        """

    @abstractmethod
    def resize_window(self, window_id: str, width: int, height: int) -> bool:
        """
        Resize a window.

        Args:
            window_id: Window identifier
            width: New width
            height: New height

        Returns:
            True if successful
        """

    @abstractmethod
    def minimize_window(self, window_id: str) -> bool:
        """Minimize a window"""

    @abstractmethod
    def maximize_window(self, window_id: str) -> bool:
        """Maximize a window"""

    @abstractmethod
    def restore_window(self, window_id: str) -> bool:
        """Restore a minimized/maximized window"""

    @abstractmethod
    def close_window(self, window_id: str) -> bool:
        """Close a window"""

    # === Screen/Display Information ===

    @abstractmethod
    def list_screens(self) -> List[ScreenInfo]:
        """List all displays/monitors"""

    @abstractmethod
    def get_screen_size(self) -> Tuple[int, int]:
        """Get the primary screen resolution as (width, height)"""

    # === Screenshots ===

    @abstractmethod
    def screenshot_screen(self, screen_id: Optional[int] = None) -> bytes:
        """
        Capture the entire screen or a specific monitor.

        Args:
            screen_id: Optional monitor ID, None for primary

        Returns:
            PNG image data as bytes
        """

    @abstractmethod
    def screenshot_window(self, window_id: str) -> bytes:
        """
        Capture a specific window.

        Args:
            window_id: Window identifier

        Returns:
            PNG image data as bytes
        """

    @abstractmethod
    def screenshot_region(self, x: int, y: int, width: int, height: int) -> bytes:
        """
        Capture a specific region of the screen.

        Args:
            x: Left coordinate
            y: Top coordinate
            width: Region width
            height: Region height

        Returns:
            PNG image data as bytes
        """

    # === Mouse Control ===

    @abstractmethod
    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse cursor position as (x, y)"""

    @abstractmethod
    def move_mouse(self, x: int, y: int, relative: bool = False) -> bool:
        """
        Move the mouse cursor.

        Args:
            x: Target X position (or delta if relative)
            y: Target Y position (or delta if relative)
            relative: If True, move relative to current position

        Returns:
            True if successful
        """

    @abstractmethod
    def click_mouse(
        self,
        button: str = "left",
        x: Optional[int] = None,
        y: Optional[int] = None,
        clicks: int = 1,
    ) -> bool:
        """
        Click the mouse.

        Args:
            button: "left", "right", or "middle"
            x: Optional X position to click at
            y: Optional Y position to click at
            clicks: Number of clicks (1 for single, 2 for double)

        Returns:
            True if successful
        """

    @abstractmethod
    def drag_mouse(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: str = "left",
        duration: float = 0.5,
    ) -> bool:
        """
        Drag the mouse from one position to another.

        Args:
            start_x: Starting X position
            start_y: Starting Y position
            end_x: Ending X position
            end_y: Ending Y position
            button: Mouse button to hold
            duration: Duration of the drag in seconds

        Returns:
            True if successful
        """

    @abstractmethod
    def scroll_mouse(
        self,
        amount: int,
        direction: str = "vertical",
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> bool:
        """
        Scroll the mouse wheel.

        Args:
            amount: Scroll amount (positive = down/right, negative = up/left)
            direction: "vertical" or "horizontal"
            x: Optional X position to scroll at
            y: Optional Y position to scroll at

        Returns:
            True if successful
        """

    # === Keyboard Control ===

    @abstractmethod
    def type_text(self, text: str, interval: float = 0.0) -> bool:
        """
        Type text using keyboard simulation.

        Args:
            text: Text to type
            interval: Delay between keystrokes in seconds

        Returns:
            True if successful
        """

    @abstractmethod
    def send_key(self, key: str, modifiers: Optional[List[str]] = None) -> bool:
        """
        Send a single key or key combination.

        Args:
            key: Key name (e.g., "enter", "tab", "a", "f1")
            modifiers: Optional list of modifiers ("ctrl", "alt", "shift", "win/super")

        Returns:
            True if successful
        """

    @abstractmethod
    def send_hotkey(self, *keys: str) -> bool:
        """
        Send a hotkey combination.

        Args:
            *keys: Keys to press together (e.g., "ctrl", "c" for Ctrl+C)

        Returns:
            True if successful
        """
