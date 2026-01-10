"""Desktop Control MCP Server - Cross-platform desktop automation"""

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

from mcp_core.base_server import BaseMCPServer
from mcp_core.utils import setup_logging

from .backends import DesktopBackend, ScreenInfo, WindowInfo, get_backend


class DesktopControlMCPServer(BaseMCPServer):  # pylint: disable=too-many-public-methods
    """MCP Server for cross-platform desktop control and automation"""

    # Output directory for screenshots (relative to project root)
    DEFAULT_OUTPUT_DIR = "outputs/desktop-control"

    def __init__(self, force_platform: Optional[str] = None, output_dir: Optional[str] = None):
        super().__init__(
            name="Desktop Control MCP Server",
            version="1.0.0",
            port=8025,
        )

        self.logger = setup_logging("DesktopControlMCP")
        self._force_platform = force_platform

        # Setup output directory for screenshots
        # _output_dir: actual path used for writing (may be container path like /output)
        # _host_output_dir: path returned to clients (host-relative like outputs/desktop-control)
        self._output_dir = output_dir or os.environ.get("DESKTOP_CONTROL_OUTPUT_DIR", self.DEFAULT_OUTPUT_DIR)
        self._host_output_dir = os.environ.get("DESKTOP_CONTROL_HOST_PATH", self.DEFAULT_OUTPUT_DIR)
        self._ensure_output_dir()

        # Initialize backend (lazy loading for graceful degradation)
        self._backend: Optional[DesktopBackend] = None
        self._backend_error: Optional[str] = None
        self._initialize_backend()

    def _ensure_output_dir(self):
        """Ensure the output directory exists and is writable"""
        os.makedirs(self._output_dir, exist_ok=True)
        self.logger.info("Screenshot output directory: %s", self._output_dir)

        # Verify write permissions
        test_file = os.path.join(self._output_dir, ".write_test")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except (OSError, IOError) as e:
            self.logger.warning(
                "Cannot write to output directory '%s': %s. "
                "Screenshots will fail. Pre-create directory with correct permissions: "
                "mkdir -p %s && chown $(id -u):$(id -g) %s",
                self._output_dir,
                e,
                self._output_dir,
                self._output_dir,
            )

    def _initialize_backend(self):
        """Initialize the platform-specific backend"""
        try:
            self._backend = get_backend(self._force_platform)
            self.logger.info("Desktop backend initialized: %s", self._backend.platform_name)
        except RuntimeError as e:
            self._backend_error = str(e)
            self.logger.error("Failed to initialize desktop backend: %s", e)

    def _ensure_backend(self) -> DesktopBackend:
        """Ensure backend is available, raise if not"""
        if self._backend is None:
            raise RuntimeError(f"Desktop control not available: {self._backend_error or 'Unknown error'}")
        return self._backend

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available desktop control tools"""
        return {
            # Status
            "desktop_status": {
                "description": "Get desktop control status and platform information",
                "parameters": {"type": "object", "properties": {}},
            },
            # Window Management
            "list_windows": {
                "description": "List all windows, optionally filtered by title pattern",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title_filter": {
                            "type": "string",
                            "description": "Regex pattern to filter window titles",
                        },
                        "visible_only": {
                            "type": "boolean",
                            "description": "Only return visible windows",
                            "default": True,
                        },
                    },
                },
            },
            "get_active_window": {
                "description": "Get the currently focused/active window",
                "parameters": {"type": "object", "properties": {}},
            },
            "focus_window": {
                "description": "Bring a window to the foreground and focus it",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {
                            "type": "string",
                            "description": "Window identifier from list_windows",
                        },
                    },
                    "required": ["window_id"],
                },
            },
            "move_window": {
                "description": "Move a window to a specific screen position",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {
                            "type": "string",
                            "description": "Window identifier",
                        },
                        "x": {"type": "integer", "description": "New X position"},
                        "y": {"type": "integer", "description": "New Y position"},
                    },
                    "required": ["window_id", "x", "y"],
                },
            },
            "resize_window": {
                "description": "Resize a window to specific dimensions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {
                            "type": "string",
                            "description": "Window identifier",
                        },
                        "width": {"type": "integer", "description": "New width"},
                        "height": {"type": "integer", "description": "New height"},
                    },
                    "required": ["window_id", "width", "height"],
                },
            },
            "minimize_window": {
                "description": "Minimize a window",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {
                            "type": "string",
                            "description": "Window identifier",
                        },
                    },
                    "required": ["window_id"],
                },
            },
            "maximize_window": {
                "description": "Maximize a window",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {
                            "type": "string",
                            "description": "Window identifier",
                        },
                    },
                    "required": ["window_id"],
                },
            },
            "restore_window": {
                "description": "Restore a minimized or maximized window to normal state",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {
                            "type": "string",
                            "description": "Window identifier",
                        },
                    },
                    "required": ["window_id"],
                },
            },
            "close_window": {
                "description": "Close a window",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {
                            "type": "string",
                            "description": "Window identifier",
                        },
                    },
                    "required": ["window_id"],
                },
            },
            # Screen Information
            "list_screens": {
                "description": "List all displays/monitors with their positions and resolutions",
                "parameters": {"type": "object", "properties": {}},
            },
            "get_screen_size": {
                "description": "Get the primary screen resolution",
                "parameters": {"type": "object", "properties": {}},
            },
            # Screenshots
            "screenshot_screen": {
                "description": "Capture the entire screen or a specific monitor. "
                "Saves PNG to outputs/desktop-control/ and returns file path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "screen_id": {
                            "type": "integer",
                            "description": "Monitor ID (0 for primary, from list_screens)",
                        },
                    },
                },
            },
            "screenshot_window": {
                "description": "Capture a specific window. Saves PNG to outputs/desktop-control/ and returns file path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {
                            "type": "string",
                            "description": "Window identifier",
                        },
                    },
                    "required": ["window_id"],
                },
            },
            "screenshot_region": {
                "description": "Capture a specific region of the screen. "
                "Saves PNG to outputs/desktop-control/ and returns file path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "Left coordinate"},
                        "y": {"type": "integer", "description": "Top coordinate"},
                        "width": {"type": "integer", "description": "Region width"},
                        "height": {"type": "integer", "description": "Region height"},
                    },
                    "required": ["x", "y", "width", "height"],
                },
            },
            # Mouse Control
            "get_mouse_position": {
                "description": "Get current mouse cursor position",
                "parameters": {"type": "object", "properties": {}},
            },
            "move_mouse": {
                "description": "Move the mouse cursor to a position",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X position (or delta if relative)"},
                        "y": {"type": "integer", "description": "Y position (or delta if relative)"},
                        "relative": {
                            "type": "boolean",
                            "description": "Move relative to current position",
                            "default": False,
                        },
                    },
                    "required": ["x", "y"],
                },
            },
            "click_mouse": {
                "description": "Click the mouse at current or specified position",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "middle"],
                            "default": "left",
                            "description": "Mouse button to click",
                        },
                        "x": {"type": "integer", "description": "X position to click at"},
                        "y": {"type": "integer", "description": "Y position to click at"},
                        "clicks": {
                            "type": "integer",
                            "default": 1,
                            "description": "Number of clicks (1=single, 2=double)",
                        },
                    },
                },
            },
            "drag_mouse": {
                "description": "Drag the mouse from one position to another",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_x": {"type": "integer", "description": "Starting X position"},
                        "start_y": {"type": "integer", "description": "Starting Y position"},
                        "end_x": {"type": "integer", "description": "Ending X position"},
                        "end_y": {"type": "integer", "description": "Ending Y position"},
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "middle"],
                            "default": "left",
                        },
                        "duration": {
                            "type": "number",
                            "default": 0.5,
                            "description": "Duration of drag in seconds",
                        },
                    },
                    "required": ["start_x", "start_y", "end_x", "end_y"],
                },
            },
            "scroll_mouse": {
                "description": "Scroll the mouse wheel",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "amount": {
                            "type": "integer",
                            "description": "Scroll amount (positive=down/right, negative=up/left)",
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["vertical", "horizontal"],
                            "default": "vertical",
                        },
                        "x": {"type": "integer", "description": "X position to scroll at"},
                        "y": {"type": "integer", "description": "Y position to scroll at"},
                    },
                    "required": ["amount"],
                },
            },
            # Keyboard Control
            "type_text": {
                "description": "Type text using keyboard simulation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to type"},
                        "interval": {
                            "type": "number",
                            "default": 0.0,
                            "description": "Delay between keystrokes in seconds",
                        },
                    },
                    "required": ["text"],
                },
            },
            "send_key": {
                "description": "Send a single key or key combination (e.g., enter, tab, f1)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Key name (enter, tab, escape, a-z, f1-f12, etc.)",
                        },
                        "modifiers": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["ctrl", "alt", "shift", "win", "super"]},
                            "description": "Modifier keys to hold",
                        },
                    },
                    "required": ["key"],
                },
            },
            "send_hotkey": {
                "description": "Send a hotkey combination (e.g., ctrl+c, alt+tab)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keys to press together (e.g., ['ctrl', 'c'])",
                        },
                    },
                    "required": ["keys"],
                },
            },
        }

    # === Status ===

    async def desktop_status(self) -> Dict[str, Any]:
        """Get desktop control status and platform information"""
        if self._backend:
            screens = self._backend.list_screens()
            screen_size = self._backend.get_screen_size()
            return {
                "success": True,
                "available": True,
                "platform": self._backend.platform_name,
                "screen_count": len(screens),
                "primary_resolution": {"width": screen_size[0], "height": screen_size[1]},
                "screens": [s.to_dict() for s in screens],
            }
        else:
            return {
                "success": False,
                "available": False,
                "error": self._backend_error,
            }

    # === Window Management ===

    async def list_windows(
        self,
        title_filter: Optional[str] = None,
        visible_only: bool = True,
    ) -> Dict[str, Any]:
        """List all windows"""
        try:
            backend = self._ensure_backend()
            windows = backend.list_windows(title_filter=title_filter, visible_only=visible_only)
            return {
                "success": True,
                "count": len(windows),
                "windows": [w.to_dict() for w in windows],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_active_window(self) -> Dict[str, Any]:
        """Get the currently focused window"""
        try:
            backend = self._ensure_backend()
            window = backend.get_active_window()
            if window:
                return {"success": True, "window": window.to_dict()}
            else:
                return {"success": False, "error": "No active window found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def focus_window(self, window_id: str) -> Dict[str, Any]:
        """Focus a window"""
        try:
            backend = self._ensure_backend()
            success = backend.focus_window(window_id)
            return {"success": success, "window_id": window_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def move_window(self, window_id: str, x: int, y: int) -> Dict[str, Any]:
        """Move a window"""
        try:
            backend = self._ensure_backend()
            success = backend.move_window(window_id, x, y)
            return {"success": success, "window_id": window_id, "position": {"x": x, "y": y}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def resize_window(self, window_id: str, width: int, height: int) -> Dict[str, Any]:
        """Resize a window"""
        try:
            backend = self._ensure_backend()
            success = backend.resize_window(window_id, width, height)
            return {"success": success, "window_id": window_id, "size": {"width": width, "height": height}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def minimize_window(self, window_id: str) -> Dict[str, Any]:
        """Minimize a window"""
        try:
            backend = self._ensure_backend()
            success = backend.minimize_window(window_id)
            return {"success": success, "window_id": window_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def maximize_window(self, window_id: str) -> Dict[str, Any]:
        """Maximize a window"""
        try:
            backend = self._ensure_backend()
            success = backend.maximize_window(window_id)
            return {"success": success, "window_id": window_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def restore_window(self, window_id: str) -> Dict[str, Any]:
        """Restore a window"""
        try:
            backend = self._ensure_backend()
            success = backend.restore_window(window_id)
            return {"success": success, "window_id": window_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close_window(self, window_id: str) -> Dict[str, Any]:
        """Close a window"""
        try:
            backend = self._ensure_backend()
            success = backend.close_window(window_id)
            return {"success": success, "window_id": window_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Screen Information ===

    async def list_screens(self) -> Dict[str, Any]:
        """List all displays"""
        try:
            backend = self._ensure_backend()
            screens = backend.list_screens()
            return {
                "success": True,
                "count": len(screens),
                "screens": [s.to_dict() for s in screens],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_screen_size(self) -> Dict[str, Any]:
        """Get primary screen resolution"""
        try:
            backend = self._ensure_backend()
            width, height = backend.get_screen_size()
            return {"success": True, "width": width, "height": height}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Screenshots ===

    def _save_screenshot(self, png_data: bytes, prefix: str) -> str:
        """Save screenshot to file and return the host-relative path"""
        timestamp = int(time.time() * 1000)  # Millisecond precision
        filename = f"{prefix}_{timestamp}.png"
        # Write to container/actual path
        filepath = os.path.join(self._output_dir, filename)
        with open(filepath, "wb") as f:
            f.write(png_data)
        # Return host-relative path for client accessibility
        return os.path.join(self._host_output_dir, filename)

    async def screenshot_screen(self, screen_id: Optional[int] = None) -> Dict[str, Any]:
        """Capture the screen and save to file"""
        try:
            backend = self._ensure_backend()
            png_data = backend.screenshot_screen(screen_id)
            filepath = self._save_screenshot(png_data, f"screen_{screen_id or 0}")
            return {
                "success": True,
                "output_path": filepath,
                "format": "png",
                "size_bytes": len(png_data),
                "screen_id": screen_id or 0,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot_window(self, window_id: str) -> Dict[str, Any]:
        """Capture a specific window and save to file"""
        try:
            backend = self._ensure_backend()
            png_data = backend.screenshot_window(window_id)
            # Sanitize window_id for filename (replace non-alphanumeric with underscore)
            safe_id = "".join(c if c.isalnum() else "_" for c in window_id)
            filepath = self._save_screenshot(png_data, f"window_{safe_id}")
            return {
                "success": True,
                "output_path": filepath,
                "format": "png",
                "size_bytes": len(png_data),
                "window_id": window_id,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot_region(self, x: int, y: int, width: int, height: int) -> Dict[str, Any]:
        """Capture a region of the screen and save to file"""
        try:
            backend = self._ensure_backend()
            png_data = backend.screenshot_region(x, y, width, height)
            filepath = self._save_screenshot(png_data, f"region_{x}_{y}_{width}x{height}")
            return {
                "success": True,
                "output_path": filepath,
                "format": "png",
                "size_bytes": len(png_data),
                "region": {"x": x, "y": y, "width": width, "height": height},
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Mouse Control ===

    async def get_mouse_position(self) -> Dict[str, Any]:
        """Get current mouse position"""
        try:
            backend = self._ensure_backend()
            x, y = backend.get_mouse_position()
            return {"success": True, "x": x, "y": y}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def move_mouse(self, x: int, y: int, relative: bool = False) -> Dict[str, Any]:
        """Move the mouse cursor"""
        try:
            backend = self._ensure_backend()
            success = backend.move_mouse(x, y, relative=relative)
            new_x, new_y = backend.get_mouse_position()
            return {
                "success": success,
                "position": {"x": new_x, "y": new_y},
                "relative": relative,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click_mouse(
        self,
        button: str = "left",
        x: Optional[int] = None,
        y: Optional[int] = None,
        clicks: int = 1,
    ) -> Dict[str, Any]:
        """Click the mouse"""
        try:
            backend = self._ensure_backend()
            success = backend.click_mouse(button=button, x=x, y=y, clicks=clicks)
            return {
                "success": success,
                "button": button,
                "clicks": clicks,
                "position": {"x": x, "y": y} if x is not None else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def drag_mouse(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        button: str = "left",
        duration: float = 0.5,
    ) -> Dict[str, Any]:
        """Drag the mouse"""
        try:
            backend = self._ensure_backend()
            # Use asyncio.to_thread to avoid blocking the event loop during drag operation
            success = await asyncio.to_thread(
                backend.drag_mouse, start_x, start_y, end_x, end_y, button=button, duration=duration
            )
            return {
                "success": success,
                "start": {"x": start_x, "y": start_y},
                "end": {"x": end_x, "y": end_y},
                "button": button,
                "duration": duration,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll_mouse(
        self,
        amount: int,
        direction: str = "vertical",
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Scroll the mouse wheel"""
        try:
            backend = self._ensure_backend()
            success = backend.scroll_mouse(amount, direction=direction, x=x, y=y)
            return {
                "success": success,
                "amount": amount,
                "direction": direction,
                "position": {"x": x, "y": y} if x is not None else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Keyboard Control ===

    async def type_text(self, text: str, interval: float = 0.0) -> Dict[str, Any]:
        """Type text"""
        try:
            backend = self._ensure_backend()
            # Use asyncio.to_thread to avoid blocking the event loop during typing
            success = await asyncio.to_thread(backend.type_text, text, interval=interval)
            return {
                "success": success,
                "text_length": len(text),
                "interval": interval,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_key(self, key: str, modifiers: Optional[List[str]] = None) -> Dict[str, Any]:
        """Send a key or key combination"""
        try:
            backend = self._ensure_backend()
            success = backend.send_key(key, modifiers=modifiers)
            return {
                "success": success,
                "key": key,
                "modifiers": modifiers or [],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def send_hotkey(self, keys: List[str]) -> Dict[str, Any]:
        """Send a hotkey combination"""
        try:
            backend = self._ensure_backend()
            success = backend.send_hotkey(*keys)
            return {
                "success": success,
                "keys": keys,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


def main():
    """Run the Desktop Control MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="Desktop Control MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="Server mode (http or stdio)",
    )
    parser.add_argument(
        "--platform",
        choices=["linux", "windows"],
        default=None,
        help="Force specific platform (auto-detected by default)",
    )
    args = parser.parse_args()

    server = DesktopControlMCPServer(force_platform=args.platform)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
