# Desktop Control MCP Server

> Cross-platform desktop automation MCP server supporting Linux and Windows.

## Overview

The Desktop Control MCP Server provides tools for:
- **Window Management**: List, focus, move, resize, minimize, maximize, and close windows
- **Screenshots**: Capture full screen, specific windows, or screen regions
- **Mouse Control**: Move, click, drag, and scroll
- **Keyboard Control**: Type text and send key combinations

## Platform Support

| Platform | Backend | Requirements |
|----------|---------|--------------|
| Linux | X11 (xdotool, wmctrl) | `xdotool`, `wmctrl`, `scrot`, `mss` |
| Windows | pywinauto + win32 | `pywinauto`, `pywin32`, `mss`, `pyautogui` |

## Quick Start

### Direct Execution (Linux)

```bash
# Install system dependencies
sudo apt-get install xdotool wmctrl scrot imagemagick

# Install Python package
pip install -e ./tools/mcp/mcp_desktop_control

# Run server
python -m mcp_desktop_control.server --mode http
```

### Docker (Linux Only)

```bash
# Build and start
docker compose up -d mcp-desktop-control

# Note: Requires X11 display access (see Docker section below)
```

## Available Tools

### Status
| Tool | Description |
|------|-------------|
| `desktop_status` | Get platform info and display configuration |

### Window Management
| Tool | Description |
|------|-------------|
| `list_windows` | List all windows with optional title filter |
| `get_active_window` | Get the currently focused window |
| `focus_window` | Bring a window to the foreground |
| `move_window` | Move a window to x,y position |
| `resize_window` | Resize a window to width,height |
| `minimize_window` | Minimize a window |
| `maximize_window` | Maximize a window |
| `restore_window` | Restore a minimized/maximized window |
| `close_window` | Close a window |

### Screenshots
| Tool | Description |
|------|-------------|
| `screenshot_screen` | Capture entire screen, save to `outputs/desktop-control/` |
| `screenshot_window` | Capture a specific window, save to file |
| `screenshot_region` | Capture a screen region, save to file |

Screenshots are saved as PNG files to `outputs/desktop-control/` (configurable via `DESKTOP_CONTROL_OUTPUT_DIR`). The tool returns the file path, which Claude can read with the `Read` tool when needed. This is more token-efficient than returning base64 data.

### Mouse Control
| Tool | Description |
|------|-------------|
| `get_mouse_position` | Get current cursor position |
| `move_mouse` | Move cursor to position (absolute or relative) |
| `click_mouse` | Click at position (left/right/middle, single/double) |
| `drag_mouse` | Drag from start to end position |
| `scroll_mouse` | Scroll wheel (vertical or horizontal) |

### Keyboard Control
| Tool | Description |
|------|-------------|
| `type_text` | Type text string with optional interval |
| `send_key` | Send single key with optional modifiers |
| `send_hotkey` | Send key combination (e.g., Ctrl+C) |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DESKTOP_CONTROL_PORT` | `8025` | HTTP server port |
| `DISPLAY` | `:0` | X11 display (Linux) |

### .mcp.json Configuration

```json
{
  "mcpServers": {
    "desktop-control": {
      "command": "python",
      "args": ["-m", "mcp_desktop_control.server", "--mode", "stdio"],
      "env": {
        "DISPLAY": ":0"
      }
    }
  }
}
```

## Docker Support

Running desktop automation in Docker requires X11 display access:

```yaml
# docker-compose.yml
mcp-desktop-control:
  build:
    context: .
    dockerfile: docker/mcp-desktop-control.Dockerfile
  environment:
    - DISPLAY=${DISPLAY}
  volumes:
    - /tmp/.X11-unix:/tmp/.X11-unix:ro
    - ${XAUTHORITY:-~/.Xauthority}:/home/appuser/.Xauthority:ro
  network_mode: host  # Required for X11 access
```

Before running:
```bash
# Allow container access to X server
xhost +local:docker
```

## Testing

```bash
# Run unit tests
docker compose run --rm python-ci pytest tools/mcp/mcp_desktop_control/tests/ -v

# Test server directly
python tools/mcp/mcp_desktop_control/scripts/test_server.py
```

## Troubleshooting

### Linux: "xdotool not found"
```bash
sudo apt-get install xdotool wmctrl scrot
```

### Linux: "Cannot open display"
```bash
# Check DISPLAY is set
echo $DISPLAY

# If empty, set it
export DISPLAY=:0
```

### Windows: "pywinauto not found"
```bash
pip install pywinauto pywin32 pyautogui
```

### Screenshots fail
```bash
# Linux: Install mss
pip install mss Pillow

# Or use scrot fallback
sudo apt-get install scrot
```

## Security Considerations

- This server provides full desktop control capabilities
- Only run in trusted environments
- Consider network isolation when exposing HTTP endpoint
- The server runs as the user who starts it (inherits their permissions)

## Known Limitations

1. **Wayland (Linux)**: Limited support - X11 is recommended
2. **UAC (Windows)**: Some windows require elevated privileges
3. **Docker**: Requires host X11 access, complex setup
4. **macOS**: Not currently supported

## API Examples

### List all visible windows
```python
result = await server.list_windows(visible_only=True)
# Returns: {"success": true, "count": 5, "windows": [...]}
```

### Take a screenshot
```python
result = await server.screenshot_screen()
# Returns: {"success": true, "output_path": "outputs/desktop-control/screen_0_1234567890.png", "format": "png", "size_bytes": 12345}
```

### Click at position
```python
result = await server.click_mouse(button="left", x=100, y=200, clicks=1)
# Returns: {"success": true, "button": "left", "clicks": 1}
```

### Send hotkey
```python
result = await server.send_hotkey(keys=["ctrl", "c"])
# Returns: {"success": true, "keys": ["ctrl", "c"]}
```
