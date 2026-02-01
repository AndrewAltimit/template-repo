# Desktop Control MCP Server (Rust)

> A Model Context Protocol server for cross-platform desktop control and automation, built in Rust with X11 (Linux) and Windows API backends.

## Overview

This MCP server provides:
- Window management (list, focus, move, resize, minimize, maximize, close)
- Screen information and multi-monitor support
- Screenshot capture (full screen, window, or region)
- Mouse control (move, click, drag, scroll)
- Keyboard simulation (type text, send keys, hotkeys)
- Lazy initialization with platform-specific backends

**Note**: Currently supports Linux (X11) with Windows support planned.

## Quick Start

```bash
# Build from source
cargo build --release

# Run in standalone HTTP mode
./target/release/mcp-desktop-control --mode standalone --port 8030

# Run in STDIO mode (for Claude Code)
./target/release/mcp-desktop-control --mode stdio

# Test health
curl http://localhost:8030/health
```

## Available Tools

### Status
| Tool | Description | Parameters |
|------|-------------|------------|
| `desktop_status` | Get server status and platform info | None |

### Window Management
| Tool | Description | Parameters |
|------|-------------|------------|
| `list_windows` | List all windows | `title_filter`, `visible_only` |
| `get_active_window` | Get currently focused window | None |
| `focus_window` | Focus a window | `window_id` (required) |
| `move_window` | Move window to position | `window_id`, `x`, `y` (all required) |
| `resize_window` | Resize a window | `window_id`, `width`, `height` (all required) |
| `minimize_window` | Minimize a window | `window_id` (required) |
| `maximize_window` | Maximize a window | `window_id` (required) |
| `restore_window` | Restore minimized/maximized window | `window_id` (required) |
| `close_window` | Close a window | `window_id` (required) |

### Screen Information
| Tool | Description | Parameters |
|------|-------------|------------|
| `list_screens` | List all monitors | None |
| `get_screen_size` | Get primary screen resolution | None |

### Screenshots
| Tool | Description | Parameters |
|------|-------------|------------|
| `screenshot_screen` | Capture full screen | `screen_id`, `output_path` |
| `screenshot_window` | Capture specific window | `window_id` (required), `output_path` |
| `screenshot_region` | Capture screen region | `x`, `y`, `width`, `height` (all required), `output_path` |

### Mouse Control
| Tool | Description | Parameters |
|------|-------------|------------|
| `get_mouse_position` | Get cursor position | None |
| `move_mouse` | Move cursor | `x`, `y` (required), `relative` |
| `click_mouse` | Click mouse button | `button`, `x`, `y`, `clicks` |
| `drag_mouse` | Drag mouse | `start_x`, `start_y`, `end_x`, `end_y` (required), `button`, `duration_ms` |
| `scroll_mouse` | Scroll mouse wheel | `amount` (required), `direction`, `x`, `y` |

### Keyboard Control
| Tool | Description | Parameters |
|------|-------------|------------|
| `type_text` | Type text | `text` (required), `interval_ms` |
| `send_key` | Send key with modifiers | `key` (required), `modifiers` |
| `send_hotkey` | Send hotkey combination | `keys` (required) |

## Configuration

### CLI Arguments

```
--mode <MODE>         Server mode: standalone, stdio, server, client [default: standalone]
--port <PORT>         Port to listen on [default: 8030]
--backend-url <URL>   Backend URL for client mode
--log-level <LEVEL>   Log level [default: info]
```

### Screenshots Directory

Screenshots are saved to:
- Linux: `~/.local/share/mcp-desktop-control/screenshots/`
- macOS: `~/Library/Application Support/mcp-desktop-control/screenshots/`
- Windows: `%LOCALAPPDATA%\mcp-desktop-control\screenshots\`

## Transport Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **standalone** | Full MCP server with HTTP transport | Production, Docker |
| **stdio** | STDIO transport for direct integration | Claude Code, local MCP clients |
| **server** | REST API only (no MCP protocol) | Microservices |
| **client** | MCP proxy to REST backend | Horizontal scaling |

## Docker Support

### Using docker-compose

```bash
# Start the MCP server (requires X11 access)
docker compose up -d mcp-desktop-control

# View logs
docker compose logs -f mcp-desktop-control

# Test health
curl http://localhost:8030/health
```

**Note**: Docker container needs access to the host's X11 display. Mount `/tmp/.X11-unix` and set `DISPLAY` environment variable.

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "desktop-control": {
      "command": "mcp-desktop-control",
      "args": ["--mode", "stdio"]
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "desktop-control": {
      "command": "docker compose",
      "args": ["-f", "./docker-compose.yml", "--profile", "services", "run", "--rm", "-T", "mcp-desktop-control", "mcp-desktop-control", "--mode", "stdio"]
    }
  }
}
```

## Building from Source

```bash
cd tools/mcp/mcp_desktop_control

# Debug build
cargo build

# Release build (optimized)
cargo build --release

# Run tests
cargo test

# Run clippy
cargo clippy -- -D warnings

# Format code
cargo fmt
```

## Project Structure

```
tools/mcp/mcp_desktop_control/
├── Cargo.toml          # Package configuration
├── Cargo.lock          # Dependency lock file
├── README.md           # This file
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation
    ├── types.rs        # Data types
    └── backend/
        ├── mod.rs      # Backend trait and factory
        └── linux.rs    # Linux X11 implementation
```

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/mcp/tools` | GET | List available tools |
| `/mcp/execute` | POST | Execute a tool |
| `/messages` | POST | MCP JSON-RPC endpoint |
| `/.well-known/mcp` | GET | MCP discovery |

## Testing

```bash
# Run unit tests
cargo test

# Test with output
cargo test -- --nocapture

# Test HTTP endpoints (after starting server)
curl http://localhost:8030/health
curl http://localhost:8030/mcp/tools

# Test list windows
curl -X POST http://localhost:8030/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "list_windows", "arguments": {"visible_only": true}}'

# Test screenshot
curl -X POST http://localhost:8030/mcp/execute \
  -H 'Content-Type: application/json' \
  -d '{"tool": "screenshot_screen", "arguments": {}}'
```

## Architecture

### Platform Backends

The server uses platform-specific backends implementing the `DesktopBackend` trait:

- **Linux**: X11 via `x11rb` crate (Xlib/XCB bindings)
- **Windows**: Win32 API via `windows` crate (planned)

### Lazy Initialization

The backend initializes on first tool execution to minimize startup time. The status endpoint shows initialization state.

### X11 Implementation Details

On Linux, the server uses:
- **XTest extension** for simulated input (mouse/keyboard)
- **RANDR extension** for multi-monitor support
- **Composite extension** for window screenshots
- **XKB extension** for keyboard handling

## Response Format

### Window List

```json
{
  "success": true,
  "count": 5,
  "windows": [
    {
      "id": "12345678",
      "title": "Terminal - bash",
      "x": 100,
      "y": 50,
      "width": 800,
      "height": 600,
      "visible": true,
      "minimized": false,
      "maximized": false
    }
  ]
}
```

### Screenshot Result

```json
{
  "success": true,
  "output_path": "/home/user/.local/share/mcp-desktop-control/screenshots/screen_20240115_143022.png",
  "format": "png",
  "size_bytes": 524288
}
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Desktop control not available" | No X11 display | Ensure DISPLAY env var is set |
| "Window not found" | Invalid window ID | Use `list_windows` to get valid IDs |
| Screenshots are black | Compositor issue | Try `screenshot_region` instead |
| Keys not sending | Focus issue | Use `focus_window` first |
| Mouse stuck | XTest issue | Restart X session |

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [x11rb](https://github.com/psychon/x11rb) - X11 Rust bindings
- [xkbcommon](https://github.com/nicira/rust-xkbcommon) - Keyboard handling
- [image](https://github.com/image-rs/image) - Image encoding
- [tokio](https://tokio.rs/) - Async runtime

## Performance

| Operation | Time |
|-----------|------|
| Server startup | ~20ms |
| First tool call | ~100ms (backend init) |
| List windows | ~10-50ms |
| Screenshot | ~50-200ms (depends on size) |
| Mouse click | ~5ms |
| Type text | ~50ms/char (with interval) |

## Security Notes

This server provides full desktop control capabilities. Use with caution:
- Only run on trusted networks
- Consider authentication in production
- Be careful with keyboard/mouse automation
- Screenshots may capture sensitive content

## License

Part of the template-repo project. See repository LICENSE file.
