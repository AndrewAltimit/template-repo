"""Linux desktop control backend using X11/Wayland tools"""

import io
import logging
import re
import shutil
import subprocess
import time
from typing import List, Optional, Tuple

from .base import DesktopBackend, ScreenInfo, WindowInfo

logger = logging.getLogger(__name__)


class LinuxBackend(DesktopBackend):
    """Linux desktop control using xdotool, wmctrl, scrot, and xrandr"""

    def __init__(self):
        self._has_xdotool = shutil.which("xdotool") is not None
        self._has_wmctrl = shutil.which("wmctrl") is not None
        self._has_scrot = shutil.which("scrot") is not None
        self._has_import = shutil.which("import") is not None  # ImageMagick
        self._has_xrandr = shutil.which("xrandr") is not None
        self._has_xclip = shutil.which("xclip") is not None

        # Check for python automation libraries as fallback
        self._has_pyautogui = False
        self._has_pyscreeze = False
        self._has_mss = False

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

    @property
    def platform_name(self) -> str:
        return "linux"

    def is_available(self) -> bool:
        """Check if basic X11 tools are available"""
        # Require at least xdotool for basic functionality
        return self._has_xdotool

    def _run_command(
        self,
        cmd: List[str],
        check: bool = False,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a shell command with proper error handling"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                errors="replace",  # Handle invalid UTF-8 in window titles gracefully
                timeout=10,
                check=check,
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error("Command timed out: %s", " ".join(cmd))
            raise
        except subprocess.CalledProcessError as e:
            logger.error("Command failed: %s, stderr: %s", " ".join(cmd), e.stderr)
            raise

    # === Window Management ===

    def list_windows(
        self,
        title_filter: Optional[str] = None,
        visible_only: bool = True,
    ) -> List[WindowInfo]:
        """List windows using wmctrl or xdotool"""
        windows = []

        if self._has_wmctrl:
            # wmctrl -l -G -p gives: id desktop pid x y w h hostname [title]
            # Note: title is optional - windows without titles have only 8 parts
            result = self._run_command(["wmctrl", "-l", "-G", "-p"])
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split(None, 8)
                    if len(parts) >= 8:  # Allow windows without titles (8 parts minimum)
                        window_id = parts[0]
                        # desktop = parts[1]
                        pid = int(parts[2]) if parts[2] != "-1" else None
                        x, y, w, h = int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6])
                        # hostname = parts[7]
                        title = parts[8] if len(parts) > 8 else ""  # Handle missing title

                        # Get additional window info via xdotool
                        class_name = self._get_window_class(window_id)
                        process_name = self._get_process_name(pid) if pid else None

                        windows.append(
                            WindowInfo(
                                id=window_id,
                                title=title,
                                x=x,
                                y=y,
                                width=w,
                                height=h,
                                process_id=pid,
                                process_name=process_name,
                                class_name=class_name,
                            )
                        )
        elif self._has_xdotool:
            # Fallback to xdotool
            result = self._run_command(["xdotool", "search", "--name", ""])
            if result.returncode == 0:
                for wid in result.stdout.strip().split("\n"):
                    if not wid:
                        continue
                    info = self._get_window_info_xdotool(wid)
                    if info:
                        windows.append(info)

        # Apply title filter
        if title_filter:
            pattern = re.compile(title_filter, re.IGNORECASE)
            windows = [w for w in windows if pattern.search(w.title)]

        return windows

    def _get_window_info_xdotool(self, window_id: str) -> Optional[WindowInfo]:
        """Get window information using xdotool"""
        try:
            # Get window name
            name_result = self._run_command(["xdotool", "getwindowname", window_id])
            title = name_result.stdout.strip() if name_result.returncode == 0 else ""

            # Get window geometry
            geo_result = self._run_command(["xdotool", "getwindowgeometry", window_id])
            x, y, w, h = 0, 0, 0, 0
            if geo_result.returncode == 0:
                geo_lines = geo_result.stdout.strip().split("\n")
                for line in geo_lines:
                    if "Position:" in line:
                        match = re.search(r"Position:\s*(\d+),(\d+)", line)
                        if match:
                            x, y = int(match.group(1)), int(match.group(2))
                    if "Geometry:" in line:
                        match = re.search(r"Geometry:\s*(\d+)x(\d+)", line)
                        if match:
                            w, h = int(match.group(1)), int(match.group(2))

            # Get PID
            pid_result = self._run_command(["xdotool", "getwindowpid", window_id])
            pid = int(pid_result.stdout.strip()) if pid_result.returncode == 0 else None

            return WindowInfo(
                id=window_id,
                title=title,
                x=x,
                y=y,
                width=w,
                height=h,
                process_id=pid,
                process_name=self._get_process_name(pid) if pid else None,
                class_name=self._get_window_class(window_id),
            )
        except Exception as e:
            logger.debug("Failed to get window info for %s: %s", window_id, e)
            return None

    def _get_window_class(self, window_id: str) -> Optional[str]:
        """Get window class using xprop"""
        try:
            result = self._run_command(["xprop", "-id", window_id, "WM_CLASS"])
            if result.returncode == 0 and "WM_CLASS" in result.stdout:
                match = re.search(r'WM_CLASS.*=\s*"([^"]*)",\s*"([^"]*)"', result.stdout)
                if match:
                    return match.group(2)  # Return the class name (second part)
        except Exception:
            pass
        return None

    def _get_process_name(self, pid: int) -> Optional[str]:
        """Get process name from PID"""
        try:
            result = self._run_command(["ps", "-p", str(pid), "-o", "comm="])
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def get_active_window(self) -> Optional[WindowInfo]:
        """Get the currently focused window"""
        if self._has_xdotool:
            result = self._run_command(["xdotool", "getactivewindow"])
            if result.returncode == 0:
                window_id = result.stdout.strip()
                return self._get_window_info_xdotool(window_id)
        return None

    def focus_window(self, window_id: str) -> bool:
        """Activate and focus a window"""
        if self._has_wmctrl:
            # wmctrl can activate by window ID (hex format)
            result = self._run_command(["wmctrl", "-i", "-a", window_id])
            return result.returncode == 0
        elif self._has_xdotool:
            result = self._run_command(["xdotool", "windowactivate", "--sync", window_id])
            return result.returncode == 0
        return False

    def move_window(self, window_id: str, x: int, y: int) -> bool:
        """Move a window to a specific position"""
        if self._has_xdotool:
            result = self._run_command(["xdotool", "windowmove", window_id, str(x), str(y)])
            return result.returncode == 0
        elif self._has_wmctrl:
            # wmctrl: -e gravity,x,y,width,height (-1 to keep current)
            result = self._run_command(["wmctrl", "-i", "-r", window_id, "-e", f"0,{x},{y},-1,-1"])
            return result.returncode == 0
        return False

    def resize_window(self, window_id: str, width: int, height: int) -> bool:
        """Resize a window"""
        if self._has_xdotool:
            result = self._run_command(["xdotool", "windowsize", window_id, str(width), str(height)])
            return result.returncode == 0
        elif self._has_wmctrl:
            result = self._run_command(["wmctrl", "-i", "-r", window_id, "-e", f"0,-1,-1,{width},{height}"])
            return result.returncode == 0
        return False

    def minimize_window(self, window_id: str) -> bool:
        """Minimize a window"""
        if self._has_xdotool:
            result = self._run_command(["xdotool", "windowminimize", window_id])
            return result.returncode == 0
        return False

    def maximize_window(self, window_id: str) -> bool:
        """Maximize a window"""
        if self._has_wmctrl:
            result = self._run_command(["wmctrl", "-i", "-r", window_id, "-b", "add,maximized_vert,maximized_horz"])
            return result.returncode == 0
        return False

    def restore_window(self, window_id: str) -> bool:
        """Restore a minimized/maximized window"""
        if self._has_wmctrl:
            result = self._run_command(["wmctrl", "-i", "-r", window_id, "-b", "remove,maximized_vert,maximized_horz"])
            return result.returncode == 0
        elif self._has_xdotool:
            # xdotool doesn't have direct unminimize, but activate can work
            result = self._run_command(["xdotool", "windowactivate", window_id])
            return result.returncode == 0
        return False

    def close_window(self, window_id: str) -> bool:
        """Close a window"""
        if self._has_wmctrl:
            result = self._run_command(["wmctrl", "-i", "-c", window_id])
            return result.returncode == 0
        elif self._has_xdotool:
            # Fallback: Send Alt+F4 to close (may not work for all applications)
            logger.warning(
                "Using Alt+F4 fallback to close window %s (wmctrl not available). "
                "This may trigger confirmation dialogs or not work for some applications.",
                window_id,
            )
            result = self._run_command(["xdotool", "windowactivate", "--sync", window_id, "key", "alt+F4"])
            return result.returncode == 0
        return False

    # === Screen/Display Information ===

    def list_screens(self) -> List[ScreenInfo]:
        """List all monitors using xrandr"""
        screens = []
        if not self._has_xrandr:
            # Return single screen with primary resolution
            w, h = self.get_screen_size()
            screens.append(ScreenInfo(id=0, x=0, y=0, width=w, height=h, is_primary=True))
            return screens

        result = self._run_command(["xrandr", "--query"])
        if result.returncode == 0:
            screen_id = 0
            for line in result.stdout.split("\n"):
                # Match connected monitors with resolution
                match = re.match(
                    r"(\S+)\s+connected\s+(?:primary\s+)?(\d+)x(\d+)\+(\d+)\+(\d+)",
                    line,
                )
                if match:
                    name = match.group(1)
                    w, h = int(match.group(2)), int(match.group(3))
                    x, y = int(match.group(4)), int(match.group(5))
                    is_primary = "primary" in line
                    screens.append(
                        ScreenInfo(
                            id=screen_id,
                            x=x,
                            y=y,
                            width=w,
                            height=h,
                            is_primary=is_primary,
                            name=name,
                        )
                    )
                    screen_id += 1

        return screens

    def get_screen_size(self) -> Tuple[int, int]:
        """Get primary screen resolution"""
        if self._has_xdotool:
            result = self._run_command(["xdotool", "getdisplaygeometry"])
            if result.returncode == 0:
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    return int(parts[0]), int(parts[1])

        if self._has_pyautogui:
            import pyautogui

            size = pyautogui.size()
            return size.width, size.height

        # Default fallback
        return 1920, 1080

    # === Screenshots ===

    def screenshot_screen(self, screen_id: Optional[int] = None) -> bytes:
        """Capture the screen using mss or scrot.

        Args:
            screen_id: Monitor index (0=primary, 1=second, etc.) or None for all monitors combined
        """
        if self._has_mss:
            import mss

            with mss.mss() as sct:
                monitors = sct.monitors
                # monitors[0] is all screens combined, monitors[1+] are individual
                if screen_id is None:
                    monitor_idx = 0  # All monitors combined
                else:
                    monitor_idx = screen_id + 1  # Individual monitor (mss uses 1-indexed)
                    if monitor_idx >= len(monitors):
                        monitor_idx = 1  # Default to primary if out of range

                screenshot = sct.grab(monitors[monitor_idx])
                # Convert to PNG bytes
                from PIL import Image

                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                return buffer.getvalue()

        if self._has_scrot:
            # scrot captures to file, we need to read it back
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                temp_path = f.name

            try:
                self._run_command(["scrot", temp_path], check=True)
                with open(temp_path, "rb") as f:
                    return f.read()
            finally:
                import os

                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        raise RuntimeError("No screenshot tool available (install mss or scrot)")

    def screenshot_window(self, window_id: str) -> bytes:
        """Capture a specific window"""
        if self._has_import:
            # ImageMagick import can capture by window ID
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                temp_path = f.name

            try:
                self._run_command(["import", "-window", window_id, temp_path], check=True)
                with open(temp_path, "rb") as f:
                    return f.read()
            finally:
                import os

                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        # Fallback: get window geometry and capture region
        info = self._get_window_info_xdotool(window_id)
        if info:
            return self.screenshot_region(info.x, info.y, info.width, info.height)

        raise RuntimeError("Failed to capture window screenshot")

    def screenshot_region(self, x: int, y: int, width: int, height: int) -> bytes:
        """Capture a specific region of the screen"""
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

        if self._has_scrot:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                temp_path = f.name

            try:
                # scrot with selection
                self._run_command(
                    ["scrot", "-a", f"{x},{y},{width},{height}", temp_path],
                    check=True,
                )
                with open(temp_path, "rb") as f:
                    return f.read()
            finally:
                import os

                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        raise RuntimeError("No screenshot tool available for region capture")

    # === Mouse Control ===

    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position"""
        if self._has_xdotool:
            result = self._run_command(["xdotool", "getmouselocation"])
            if result.returncode == 0:
                match = re.search(r"x:(\d+)\s+y:(\d+)", result.stdout)
                if match:
                    return int(match.group(1)), int(match.group(2))

        if self._has_pyautogui:
            import pyautogui

            pos = pyautogui.position()
            return pos.x, pos.y

        return 0, 0

    def move_mouse(self, x: int, y: int, relative: bool = False) -> bool:
        """Move the mouse cursor"""
        if self._has_xdotool:
            if relative:
                result = self._run_command(["xdotool", "mousemove_relative", str(x), str(y)])
            else:
                result = self._run_command(["xdotool", "mousemove", str(x), str(y)])
            return result.returncode == 0

        if self._has_pyautogui:
            import pyautogui

            if relative:
                pyautogui.moveRel(x, y)
            else:
                pyautogui.moveTo(x, y)
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
        button_map = {"left": "1", "middle": "2", "right": "3"}
        btn = button_map.get(button.lower(), "1")

        if self._has_xdotool:
            cmd = ["xdotool"]
            if x is not None and y is not None:
                cmd.extend(["mousemove", str(x), str(y)])
            cmd.extend(["click", "--repeat", str(clicks), btn])
            result = self._run_command(cmd)
            return result.returncode == 0

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
        button_map = {"left": "1", "middle": "2", "right": "3"}
        btn = button_map.get(button.lower(), "1")

        if self._has_xdotool:
            # Move to start, press button, move to end, release
            self._run_command(["xdotool", "mousemove", str(start_x), str(start_y)])
            self._run_command(["xdotool", "mousedown", btn])
            # Calculate steps for smooth drag
            steps = max(10, int(duration * 20))
            dx = (end_x - start_x) / steps
            dy = (end_y - start_y) / steps
            for i in range(steps):
                new_x = int(start_x + dx * (i + 1))
                new_y = int(start_y + dy * (i + 1))
                self._run_command(["xdotool", "mousemove", str(new_x), str(new_y)])
                time.sleep(duration / steps)
            self._run_command(["xdotool", "mouseup", btn])
            return True

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
        if self._has_xdotool:
            cmd = ["xdotool"]
            if x is not None and y is not None:
                cmd.extend(["mousemove", str(x), str(y)])

            if direction == "vertical":
                button = "5" if amount > 0 else "4"  # 4=up, 5=down
            else:
                button = "7" if amount > 0 else "6"  # 6=left, 7=right

            cmd.extend(["click", "--repeat", str(abs(amount)), button])
            result = self._run_command(cmd)
            return result.returncode == 0

        if self._has_pyautogui:
            import pyautogui

            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
            if direction == "vertical":
                pyautogui.scroll(-amount)  # pyautogui: positive = up
            else:
                pyautogui.hscroll(amount)
            return True

        return False

    # === Keyboard Control ===

    def type_text(self, text: str, interval: float = 0.0) -> bool:
        """Type text"""
        if self._has_xdotool:
            cmd = ["xdotool", "type"]
            if interval > 0:
                cmd.extend(["--delay", str(int(interval * 1000))])
            cmd.append(text)
            result = self._run_command(cmd)
            return result.returncode == 0

        if self._has_pyautogui:
            import pyautogui

            pyautogui.typewrite(text, interval=interval)
            return True

        return False

    def send_key(self, key: str, modifiers: Optional[List[str]] = None) -> bool:
        """Send a key or key combination"""
        if modifiers:
            key_combo = "+".join(modifiers) + "+" + key
        else:
            key_combo = key

        if self._has_xdotool:
            result = self._run_command(["xdotool", "key", key_combo])
            return result.returncode == 0

        if self._has_pyautogui:
            import pyautogui

            if modifiers:
                pyautogui.hotkey(*modifiers, key)
            else:
                pyautogui.press(key)
            return True

        return False

    def send_hotkey(self, *keys: str) -> bool:
        """Send a hotkey combination"""
        key_combo = "+".join(keys)

        if self._has_xdotool:
            result = self._run_command(["xdotool", "key", key_combo])
            return result.returncode == 0

        if self._has_pyautogui:
            import pyautogui

            pyautogui.hotkey(*keys)
            return True

        return False
