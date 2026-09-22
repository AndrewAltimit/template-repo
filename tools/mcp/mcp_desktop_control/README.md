# Desktop Control MCP Server (Rust)

> A Model Context Protocol server for desktop automation: windows, monitors,
> screenshots, mouse and keyboard. Native backends for **Linux/X11** and
> **Windows**; one tool surface on both.

## Overview

| Area | What you get |
|------|--------------|
| Windows | List (with process name/PID), focus, move, resize, minimize, maximize, restore, close |
| Screens | Multi-monitor layout (negative coordinates supported), primary screen, DPI scale |
| Screenshots | Monitor, window or region as PNG; optional inline image return and downscaling |
| Mouse | Move (absolute/relative), click/double-click, smooth drag, vertical/horizontal scroll |
| Keyboard | Type arbitrary Unicode text, single keys with modifiers, hotkey chords |

Design points:

- **Lazy, self-healing backend**: the display connection is opened on first use
  (so the server starts without a display) and re-opened automatically if it
  is lost (e.g. the X server restarts).
- **Non-blocking**: every platform call runs on a blocking thread with a
  timeout, so a slow or wedged display server cannot stall the MCP transport.
- **Serialized input**: mouse/keyboard operations never interleave, even when a
  client issues calls concurrently.
- **No stuck keys/buttons**: chords release every pressed key in reverse order
  and drags always release the button, even when a step fails.
- **Honest results**: bad arguments are rejected with a clear message
  (JSON-RPC `Invalid params`); runtime failures come back as `isError` tool
  results with `{"success": false, "error": "..."}`; `type_text` reports any
  characters it could not type instead of dropping them silently.

## Quick Start

```bash
cd tools/mcp/mcp_desktop_control
cargo build --release

# STDIO mode (Claude Code / local MCP clients)
./target/release/mcp-desktop-control --mode stdio

# HTTP mode
./target/release/mcp-desktop-control --mode standalone --port 8026
curl http://localhost:8026/health
```

Always pass `--port` in HTTP mode: the shared `mcp-core` default is 8000; the
repository convention for this server is **8026** (docker-compose, Dockerfile).

## Tools

All coordinates are absolute desktop pixels. On multi-monitor setups the
desktop can extend into negative coordinates (see `get_screen_size` ->
`virtual_screen`). Integer parameters also accept integral floats (`100.0`)
and numeric strings (`"100"`).

### Status

| Tool | Parameters | Notes |
|------|------------|-------|
| `desktop_status` | - | Version, platform, `available`, the connection error if any, output dir, limits, platform diagnostics (X11: display, window manager, XTEST/RandR support). Connects to the display if needed. |

### Windows

| Tool | Parameters | Notes |
|------|------------|-------|
| `list_windows` | `title_filter` (case-insensitive substring), `visible_only` (default `true`) | Returns `id`, `title`, `process_name`, `pid`, `x`, `y`, `width`, `height`, `visible`, `minimized`, `maximized` |
| `get_active_window` | - | `window: null` when nothing is focused |
| `focus_window` | `window_id` * | Restores a minimized window first. On Windows, fails with an explanation if focus-stealing prevention blocks it |
| `move_window` | `window_id` *, `x` *, `y` * | Positions the window's top-left corner |
| `resize_window` | `window_id` *, `width` *, `height` * (1..32767) | |
| `minimize_window` | `window_id` * | |
| `maximize_window` | `window_id` * | X11: needs an EWMH window manager |
| `restore_window` | `window_id` * | Un-minimizes and un-maximizes |
| `close_window` | `window_id` * | Polite close (like the title-bar X button); the app may prompt to save. Never force-kills |

`window_id` is the string `id` from `list_windows`. Integers and `0x`-prefixed
hex ids (as printed by `xdotool`/`wmctrl`/`xwininfo`) are accepted too.

### Screens

| Tool | Parameters | Notes |
|------|------------|-------|
| `list_screens` | - | `id` (0-based), `name`, `x`, `y`, `width`, `height`, `is_primary`, `scale` |
| `get_screen_size` | - | Primary screen `width`/`height`, `screen_count`, and `virtual_screen` (bounding box of all monitors) |

### Screenshots

| Tool | Parameters |
|------|------------|
| `screenshot_screen` | `screen_id` (default: primary screen) |
| `screenshot_window` | `window_id` * |
| `screenshot_region` | `x` *, `y` *, `width` *, `height` * |

Shared optional parameters:

| Parameter | Description |
|-----------|-------------|
| `output_path` | File name or relative path inside the output directory. `.png` is appended when missing; any other extension is rejected. Absolute paths are accepted only if they are inside the output directory; `..` is rejected. |
| `return_image` | `true` to also return the PNG inline as MCP image content (so the model can see it). Default `false`. Images over 5 MB are not inlined (`image_omitted` explains why). |
| `max_dimension` | Downscale (aspect preserved) so neither side exceeds this many pixels (min 16). Applies to both the saved file and the inline image. Recommended with `return_image`, e.g. `1280`. |

Response: `output_path`, `host_path` (when `DESKTOP_CONTROL_HOST_PATH` is set),
`format`, `size_bytes`, final `width`/`height`, and `captured_region` (the
desktop area actually captured; regions are clipped to the desktop).

### Mouse

| Tool | Parameters | Notes |
|------|------------|-------|
| `get_mouse_position` | - | |
| `move_mouse` | `x` *, `y` *, `relative` (default `false`) | Response includes the final `position` |
| `click_mouse` | `button` (`left`/`right`/`middle`), `x` + `y` (both or neither), `clicks` (1..10) | `clicks: 2` = double-click |
| `drag_mouse` | `start_x` *, `start_y` *, `end_x` *, `end_y` *, `button`, `duration_ms` (0..10000, default 500) | Smooth interpolated movement |
| `scroll_mouse` | `amount` * (-100..100; positive = down/right), `direction` (`vertical`/`horizontal`), `x` + `y` | |

### Keyboard

| Tool | Parameters | Notes |
|------|------------|-------|
| `type_text` | `text` * (max 10000 chars), `interval_ms` (0..1000, default 50) | Types literal text; `\n` = Enter, `\t` = Tab. Returns `typed` and, if any, `skipped` characters (then `success: false`) |
| `send_key` | `key` *, `modifiers` (`ctrl`, `alt`, `shift`, `win`, `super`) | `{"key": "s", "modifiers": ["ctrl", "shift"]}` = Ctrl+Shift+S |
| `send_hotkey` | `keys` * (1..8 keys) | Pressed in order, released in reverse: `["ctrl", "c"]`, `["alt", "F4"]`, `["super", "l"]` |

Key names (case-insensitive; `_`, `-` and spaces ignored): any single
character, `enter`/`return`, `tab`, `escape`/`esc`, `backspace`, `delete`,
`insert`, `home`, `end`, `pageup`/`prior`, `pagedown`/`next`, `left`, `right`,
`up`, `down`, `space`, `f1`-`f24`, `capslock`, `numlock`, `scrolllock`,
`printscreen`, `pause`, `menu`, `ctrl`, `alt`, `shift`,
`super`/`win`/`meta`/`cmd`, `volumeup`, `volumedown`, `volumemute`,
`playpause`, `nexttrack`, `prevtrack`, plus `plus`, `minus`, `comma`,
`period`, `slash`, `backslash`, `semicolon`, `quote`, `grave`,
`bracketleft`, `bracketright`.

In `send_key`/`send_hotkey`, letters are case-insensitive (`"A"` is the A key;
add `shift` explicitly). Symbols that need Shift on the active layout (`!`,
`@`, ...) get Shift added automatically. Characters that are not on the
keyboard layout cannot be sent as key presses; use `type_text` for those.

### Limits

| Limit | Value |
|-------|-------|
| Base operation timeout | 20 s (+ requested delays for `type_text`/`drag_mouse`) |
| Display connect timeout | 10 s |
| `type_text` length | 10000 characters |
| `interval_ms` | 1000 ms |
| `duration_ms` | 10000 ms |
| `clicks` | 10 |
| `scroll` amount | +/-100 |
| Hotkey keys | 8 |
| Inline image | 5 MB PNG |

## Configuration

### CLI

```
--mode <MODE>          standalone | stdio | server | client   [default: standalone]
--port <PORT>          HTTP port (ignored in stdio mode)       [default: 8000]
--backend-url <URL>    Backend URL for client mode
--log-level <LEVEL>    Log level (RUST_LOG overrides)          [default: info]
--output-dir <DIR>     Screenshot directory (overrides DESKTOP_CONTROL_OUTPUT_DIR)
```

### Environment

| Variable | Purpose |
|----------|---------|
| `DISPLAY` | X display to control (Linux) |
| `XAUTHORITY` | X authority file (Linux, when the server requires auth) |
| `DESKTOP_CONTROL_OUTPUT_DIR` | Screenshot directory (default: `~/.local/share/mcp-desktop-control/screenshots` on Linux, `%LOCALAPPDATA%\mcp-desktop-control\screenshots` on Windows) |
| `DESKTOP_CONTROL_HOST_PATH` | Host-side path of the output directory when running in a container; screenshot responses then include `host_path` |
| `RUST_LOG` | Log filter (logs go to stderr) |

## Platform Backends

### Linux (X11)

Pure-Rust X11 client (`x11rb`); no libX11/libxcb or X11 command-line tools are
needed at build or run time.

- **Input** via the XTEST extension. Keys are resolved through the server's
  live keyboard mapping, so non-US layouts work. Characters not present on
  the layout (e.g. `€`, emoji, CJK) are typed by temporarily binding them to
  an unused keycode, then removing the binding.
- **Monitors** via RandR 1.3 (`GetScreenResourcesCurrent`, no slow hardware
  re-probe); falls back to the root window size.
- **Window management** uses EWMH messages when the window manager supports
  them and plain ICCCM requests otherwise, so it also works on a bare Xvfb
  without a window manager (maximize is then unavailable and reported as such).
- **Screenshots** read the root window, so `screenshot_window` captures the
  window's on-screen area including anything overlapping it.
- 32 bpp (depth 24/32) displays only.

### Windows

- **Input** via `SendInput`; `type_text` sends Unicode directly
  (`KEYEVENTF_UNICODE`), so any character works regardless of layout.
- The process opts into **per-monitor DPI awareness**: all coordinates are
  physical pixels and match the screenshots.
- **Window geometry** is the visible frame (DWM extended frame bounds, without
  the invisible resize borders); `move_window`/`resize_window` compensate so
  values round-trip with `list_windows`. Cloaked (hidden UWP) windows are
  reported as not visible.
- **Window screenshots** use `PrintWindow(PW_RENDERFULLCONTENT)`, so occluded
  windows capture correctly; falls back to a screen-area capture.

## Running in Docker (Linux)

```bash
mkdir -p outputs/desktop-control
docker compose --profile desktop up -d mcp-desktop-control
curl http://localhost:8026/health
```

The container needs the host X socket and authority:
`/tmp/.X11-unix` mounted, `DISPLAY` set, and `XAUTHORITY` pointing at a
mounted Xauthority file (or `xhost +SI:localuser:$(id -un)` on the host).
`network_mode: host` is used for X11 access. Screenshots land in
`/output` inside the container (`outputs/desktop-control` on the host).

## MCP Client Configuration

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

## Examples

```bash
# List windows whose title contains "firefox"
curl -s -X POST http://localhost:8026/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "list_windows", "arguments": {"title_filter": "firefox"}}'

# Screenshot of the primary screen, returned inline at <= 1280 px
curl -s -X POST http://localhost:8026/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "screenshot_screen", "arguments": {"return_image": true, "max_dimension": 1280}}'

# Double-click, then type and press Ctrl+S
curl -s -X POST http://localhost:8026/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "click_mouse", "arguments": {"x": 400, "y": 300, "clicks": 2}}'
curl -s -X POST http://localhost:8026/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "type_text", "arguments": {"text": "Hello, world\n", "interval_ms": 10}}'
curl -s -X POST http://localhost:8026/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "send_hotkey", "arguments": {"keys": ["ctrl", "s"]}}'
```

## Development

```bash
cd tools/mcp/mcp_desktop_control
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

Unit tests never touch the real desktop: tool behaviour is exercised against
an in-memory mock backend that records input events. An optional read-only
X11 smoke test runs against a real display when enabled:

```bash
Xvfb :99 & DISPLAY=:99 MCP_DESKTOP_X11_TEST=1 cargo test live_read_only_smoke
```

The crate builds on both Linux and Windows; platform code is `cfg`-gated.
To check the Linux build from Windows:

```bash
docker run --rm -v "$PWD/..":/w -w /w/mcp_desktop_control -e CARGO_TARGET_DIR=/tmp/t \
  rust:1.93 sh -c 'rustup component add clippy && cargo clippy --all-targets -- -D warnings && cargo test'
```

## Project Structure

```
src/
  main.rs          CLI entry point
  server.rs        Tool definitions, schemas, handlers, backend lifecycle
  args.rs          Typed argument structs and validation
  actions.rs       Platform-neutral composites (click, drag, chord, filters)
  keys.rs          Key-name parsing, X11 keysym and Win32 VK tables
  imaging.rs       Pixel conversion, downscaling, PNG encoding
  output.rs        Output directory and path confinement
  types.rs         Shared data types
  backend/
    mod.rs         DesktopBackend trait, errors, platform selection
    linux.rs       X11 backend
    win32.rs       Windows backend
    mock.rs        Test backend
```

## Limitations

- **Wayland** sessions are only reachable through XWayland: native Wayland
  windows are not listed or controllable, and input may be ignored by them.
- **macOS** is not supported (`desktop_status` reports the backend as
  unavailable).
- On X11, `process_name` needs the server and the target app to share a PID
  namespace (typically not the case inside Docker); `pid` is still reported.
- On Windows, input cannot reach windows of elevated (administrator) processes
  unless the server is elevated too (UIPI), nor the lock screen / UAC secure
  desktop; this is reported as an error. Some GPU-rendered windows may capture
  black via `PrintWindow`.
- Caps Lock state affects typed letter case on X11.

## Security Notes

This server can see the screen and send arbitrary input as the logged-in user.

- Prefer STDIO mode; the HTTP transport has no authentication, so bind it only
  on trusted hosts/networks.
- Screenshot writes are confined to the output directory (no `..`, no absolute
  paths outside it, symlinked sub-directories rejected).
- Screenshots may capture sensitive content.

## License

Part of the template-repo project. See repository LICENSE file.
