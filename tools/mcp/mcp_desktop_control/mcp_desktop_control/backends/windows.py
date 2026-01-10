"""Windows desktop control backend using pywinauto, pyautogui, and mss"""

import io
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import DesktopBackend, ScreenInfo, WindowInfo

logger = logging.getLogger(__name__)


class WindowsBackend(DesktopBackend):
    """Windows desktop control using pywinauto, pyautogui, and win32 APIs"""

    def __init__(self):
        self._has_pywinauto = False
        self._has_pyautogui = False
        self._has_mss = False
        self._has_win32gui = False
        self._has_win32con = False

        # Try to import Windows-specific libraries
        try:
            import pywinauto  # noqa: F401

            self._has_pywinauto = True
        except ImportError:
            pass

        try:
            import pyautogui  # noqa: F401

            self._has_pyautogui = True
        except ImportError:
            pass

        try:
            import mss  # noqa: F401

            self._has_mss = True
        except ImportError:
            pass

        try:
            import win32con  # noqa: F401
            import win32gui  # noqa: F401

            self._has_win32gui = True
            self._has_win32con = True
        except ImportError:
            pass

    @property
    def platform_name(self) -> str:
        return "windows"

    def is_available(self) -> bool:
        """Check if Windows automation libraries are available"""
        # Require at least pywinauto or win32gui for window management
        return self._has_pywinauto or self._has_win32gui

    def _get_pywinauto_desktop(self):
        """Get pywinauto Desktop object"""
        from pywinauto import Desktop

        return Desktop(backend="uia")

    # === Window Management ===

    def list_windows(
        self,
        title_filter: Optional[str] = None,
        visible_only: bool = True,
    ) -> List[WindowInfo]:
        """List all windows"""
        windows = []

        if self._has_pywinauto:
            try:
                desktop = self._get_pywinauto_desktop()
                for win in desktop.windows():
                    try:
                        if visible_only and not win.is_visible():
                            continue

                        rect = win.rectangle()
                        windows.append(
                            WindowInfo(
                                id=str(win.handle),
                                title=win.window_text(),
                                x=rect.left,
                                y=rect.top,
                                width=rect.width(),
                                height=rect.height(),
                                is_visible=win.is_visible(),
                                is_minimized=win.is_minimized(),
                                is_maximized=win.is_maximized(),
                                process_id=win.process_id(),
                                class_name=win.class_name(),
                            )
                        )
                    except Exception as e:
                        logger.debug("Error getting window info: %s", e)
                        continue
            except Exception as e:
                logger.error("Error listing windows: %s", e)

        elif self._has_win32gui:
            import win32gui
            import win32process

            def enum_callback(hwnd, results):
                if visible_only and not win32gui.IsWindowVisible(hwnd):
                    return True

                try:
                    title = win32gui.GetWindowText(hwnd)
                    rect = win32gui.GetWindowRect(hwnd)
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    class_name = win32gui.GetClassName(hwnd)

                    results.append(
                        WindowInfo(
                            id=str(hwnd),
                            title=title,
                            x=rect[0],
                            y=rect[1],
                            width=rect[2] - rect[0],
                            height=rect[3] - rect[1],
                            is_visible=win32gui.IsWindowVisible(hwnd),
                            is_minimized=win32gui.IsIconic(hwnd),
                            process_id=pid,
                            class_name=class_name,
                        )
                    )
                except Exception:
                    pass
                return True

            win32gui.EnumWindows(enum_callback, windows)

        # Apply title filter
        if title_filter:
            pattern = re.compile(title_filter, re.IGNORECASE)
            windows = [w for w in windows if pattern.search(w.title)]

        return windows

    def get_active_window(self) -> Optional[WindowInfo]:
        """Get the currently focused window"""
        if self._has_win32gui:
            import win32gui

            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                try:
                    title = win32gui.GetWindowText(hwnd)
                    rect = win32gui.GetWindowRect(hwnd)
                    return WindowInfo(
                        id=str(hwnd),
                        title=title,
                        x=rect[0],
                        y=rect[1],
                        width=rect[2] - rect[0],
                        height=rect[3] - rect[1],
                    )
                except Exception:
                    pass

        if self._has_pywinauto:
            try:
                desktop = self._get_pywinauto_desktop()
                # Get foreground window
                import win32gui

                hwnd = win32gui.GetForegroundWindow()
                win = desktop.window(handle=hwnd)
                rect = win.rectangle()
                return WindowInfo(
                    id=str(hwnd),
                    title=win.window_text(),
                    x=rect.left,
                    y=rect.top,
                    width=rect.width(),
                    height=rect.height(),
                )
            except Exception:
                pass

        return None

    def focus_window(self, window_id: str) -> bool:
        """Bring a window to the foreground"""
        hwnd = int(window_id)

        if self._has_pywinauto:
            try:
                from pywinauto import Application

                app = Application(backend="uia").connect(handle=hwnd)
                win = app.window(handle=hwnd)
                win.set_focus()
                return True
            except Exception as e:
                logger.error("Failed to focus window: %s", e)

        if self._has_win32gui:
            import win32con
            import win32gui

            try:
                # Restore if minimized
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                return True
            except Exception as e:
                logger.error("Failed to focus window: %s", e)

        return False

    def move_window(self, window_id: str, x: int, y: int) -> bool:
        """Move a window"""
        hwnd = int(window_id)

        if self._has_win32gui:
            import win32gui

            try:
                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                win32gui.MoveWindow(hwnd, x, y, width, height, True)
                return True
            except Exception as e:
                logger.error("Failed to move window: %s", e)

        return False

    def resize_window(self, window_id: str, width: int, height: int) -> bool:
        """Resize a window"""
        hwnd = int(window_id)

        if self._has_win32gui:
            import win32gui

            try:
                rect = win32gui.GetWindowRect(hwnd)
                x, y = rect[0], rect[1]
                win32gui.MoveWindow(hwnd, x, y, width, height, True)
                return True
            except Exception as e:
                logger.error("Failed to resize window: %s", e)

        return False

    def minimize_window(self, window_id: str) -> bool:
        """Minimize a window"""
        hwnd = int(window_id)

        if self._has_win32gui:
            import win32con
            import win32gui

            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                return True
            except Exception as e:
                logger.error("Failed to minimize window: %s", e)

        return False

    def maximize_window(self, window_id: str) -> bool:
        """Maximize a window"""
        hwnd = int(window_id)

        if self._has_win32gui:
            import win32con
            import win32gui

            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                return True
            except Exception as e:
                logger.error("Failed to maximize window: %s", e)

        return False

    def restore_window(self, window_id: str) -> bool:
        """Restore a minimized/maximized window"""
        hwnd = int(window_id)

        if self._has_win32gui:
            import win32con
            import win32gui

            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                return True
            except Exception as e:
                logger.error("Failed to restore window: %s", e)

        return False

    def close_window(self, window_id: str) -> bool:
        """Close a window"""
        hwnd = int(window_id)

        if self._has_win32gui:
            import win32con
            import win32gui

            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True
            except Exception as e:
                logger.error("Failed to close window: %s", e)

        return False

    # === Screen/Display Information ===

    def list_screens(self) -> List[ScreenInfo]:
        """List all monitors"""
        screens = []

        if self._has_mss:
            import mss

            with mss.mss() as sct:
                for i, monitor in enumerate(sct.monitors[1:], start=0):  # Skip combined monitor
                    screens.append(
                        ScreenInfo(
                            id=i,
                            x=monitor["left"],
                            y=monitor["top"],
                            width=monitor["width"],
                            height=monitor["height"],
                            is_primary=(i == 0),
                        )
                    )
        elif self._has_win32gui:
            import win32api

            try:
                monitors = win32api.EnumDisplayMonitors()
                for i, (hmon, hdc, rect) in enumerate(monitors):
                    screens.append(
                        ScreenInfo(
                            id=i,
                            x=rect[0],
                            y=rect[1],
                            width=rect[2] - rect[0],
                            height=rect[3] - rect[1],
                            is_primary=(i == 0),
                        )
                    )
            except Exception:
                # Fallback to primary screen
                import win32api

                w = win32api.GetSystemMetrics(0)
                h = win32api.GetSystemMetrics(1)
                screens.append(ScreenInfo(id=0, x=0, y=0, width=w, height=h, is_primary=True))

        return screens

    def get_screen_size(self) -> Tuple[int, int]:
        """Get primary screen resolution"""
        if self._has_pyautogui:
            import pyautogui

            size = pyautogui.size()
            return size.width, size.height

        if self._has_win32gui:
            import win32api

            return win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)

        return 1920, 1080

    # === Screenshots ===

    def screenshot_screen(self, screen_id: Optional[int] = None) -> bytes:
        """Capture the screen"""
        if self._has_mss:
            import mss

            with mss.mss() as sct:
                monitors = sct.monitors
                monitor_idx = (screen_id or 0) + 1
                if monitor_idx >= len(monitors):
                    monitor_idx = 1

                screenshot = sct.grab(monitors[monitor_idx])
                from PIL import Image

                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                return buffer.getvalue()

        if self._has_pyautogui:
            import pyautogui

            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            return buffer.getvalue()

        raise RuntimeError("No screenshot tool available")

    def screenshot_window(self, window_id: str) -> bytes:
        """Capture a specific window"""
        hwnd = int(window_id)

        if self._has_win32gui:
            import win32gui

            try:
                rect = win32gui.GetWindowRect(hwnd)
                x, y, x2, y2 = rect
                return self.screenshot_region(x, y, x2 - x, y2 - y)
            except Exception as e:
                logger.error("Failed to get window rect: %s", e)

        raise RuntimeError("Failed to capture window screenshot")

    def screenshot_region(self, x: int, y: int, width: int, height: int) -> bytes:
        """Capture a specific region"""
        if self._has_mss:
            import mss

            with mss.mss() as sct:
                region = {"left": x, "top": y, "width": width, "height": height}
                screenshot = sct.grab(region)
                from PIL import Image

                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                return buffer.getvalue()

        if self._has_pyautogui:
            import pyautogui

            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            return buffer.getvalue()

        raise RuntimeError("No screenshot tool available")

    # === Mouse Control ===

    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position"""
        if self._has_pyautogui:
            import pyautogui

            pos = pyautogui.position()
            return pos.x, pos.y

        if self._has_win32gui:
            import win32api

            pos = win32api.GetCursorPos()
            return pos[0], pos[1]

        return 0, 0

    def move_mouse(self, x: int, y: int, relative: bool = False) -> bool:
        """Move the mouse cursor"""
        if self._has_pyautogui:
            import pyautogui

            if relative:
                pyautogui.moveRel(x, y)
            else:
                pyautogui.moveTo(x, y)
            return True

        if self._has_win32gui:
            import win32api

            if relative:
                curr_x, curr_y = win32api.GetCursorPos()
                win32api.SetCursorPos((curr_x + x, curr_y + y))
            else:
                win32api.SetCursorPos((x, y))
            return True

        return False

    def click_mouse(
        self,
        button: str = "left",
        x: Optional[int] = None,
        y: Optional[int] = None,
        clicks: int = 1,
    ) -> bool:
        """Click the mouse"""
        if self._has_pyautogui:
            import pyautogui

            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return True

        return False

    def drag_mouse(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: str = "left",
        duration: float = 0.5,
    ) -> bool:
        """Drag the mouse"""
        if self._has_pyautogui:
            import pyautogui

            pyautogui.moveTo(start_x, start_y)
            pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)
            return True

        return False

    def scroll_mouse(
        self,
        amount: int,
        direction: str = "vertical",
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> bool:
        """Scroll the mouse wheel"""
        if self._has_pyautogui:
            import pyautogui

            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
            if direction == "vertical":
                pyautogui.scroll(-amount)
            else:
                pyautogui.hscroll(amount)
            return True

        return False

    # === Keyboard Control ===

    def type_text(self, text: str, interval: float = 0.0) -> bool:
        """Type text"""
        if self._has_pyautogui:
            import pyautogui

            pyautogui.typewrite(text, interval=interval)
            return True

        if self._has_pywinauto:
            from pywinauto import keyboard

            keyboard.send_keys(text, with_spaces=True)
            return True

        return False

    def send_key(self, key: str, modifiers: Optional[List[str]] = None) -> bool:
        """Send a key or key combination"""
        if self._has_pyautogui:
            import pyautogui

            if modifiers:
                pyautogui.hotkey(*modifiers, key)
            else:
                pyautogui.press(key)
            return True

        if self._has_pywinauto:
            from pywinauto import keyboard

            # Convert to pywinauto format
            key_str = ""
            if modifiers:
                mod_map = {"ctrl": "^", "alt": "%", "shift": "+", "win": "#"}
                for mod in modifiers:
                    key_str += mod_map.get(mod.lower(), "")
            key_str += f"{{{key}}}"
            keyboard.send_keys(key_str)
            return True

        return False

    def send_hotkey(self, *keys: str) -> bool:
        """Send a hotkey combination"""
        if self._has_pyautogui:
            import pyautogui

            pyautogui.hotkey(*keys)
            return True

        if self._has_pywinauto:
            from pywinauto import keyboard

            # Convert to pywinauto format
            mod_map = {"ctrl": "^", "alt": "%", "shift": "+", "win": "#"}
            key_str = ""
            for key in keys[:-1]:  # Modifiers
                key_str += mod_map.get(key.lower(), "")
            key_str += f"{{{keys[-1]}}}"  # Final key
            keyboard.send_keys(key_str)
            return True

        return False
