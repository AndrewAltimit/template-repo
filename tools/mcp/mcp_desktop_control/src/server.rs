//! MCP tool definitions for desktop control.
//!
//! Each tool is a [`DesktopTool`]: a name, description, JSON schema and an
//! async handler. Handlers parse typed arguments (see [`crate::args`]) and
//! run backend work through [`Ctx::run`], which
//!
//! * lazily connects to the display (and reconnects after a lost connection),
//! * executes the blocking backend call on `spawn_blocking` so sleeps and X11
//!   round-trips never stall the async runtime,
//! * serializes mouse/keyboard operations so concurrent calls cannot
//!   interleave keystrokes, and
//! * enforces a timeout so a wedged display server cannot hang a request.

use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use base64::Engine;
use mcp_core::prelude::*;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use tokio::sync::Mutex;
use tracing::{info, warn};

use crate::actions;
use crate::args::{self, *};
use crate::backend::{DesktopBackend, DesktopError, DesktopResult, SharedBackend};
use crate::imaging;
use crate::keys::{Key, parse_key};
use crate::output::{self, OutputConfig};
use crate::types::Rect;

/// Server version reported by `desktop_status`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Time allowed for connecting to the display.
const INIT_TIMEOUT: Duration = Duration::from_secs(10);
/// Base time allowed for any single operation (plus any requested delays).
const OP_TIMEOUT: Duration = Duration::from_secs(20);
/// Largest PNG returned inline (`return_image`); bigger images are only saved.
const MAX_INLINE_IMAGE_BYTES: usize = 5 * 1024 * 1024;

/// Creates a backend (the real platform backend, or a mock in tests).
pub type BackendFactory = Arc<dyn Fn() -> DesktopResult<SharedBackend> + Send + Sync>;

/// Why a tool call failed.
#[derive(Debug)]
enum Failure {
    /// Bad arguments: reported as a JSON-RPC `InvalidParameters` error.
    Invalid(String),
    /// Execution failure: reported as an `isError` tool result so the model
    /// can read the message and recover.
    Exec(String),
}

/// Result of a handler step.
type Outcome<T> = std::result::Result<T, Failure>;

impl From<DesktopError> for Failure {
    fn from(e: DesktopError) -> Self {
        Failure::Exec(e.to_string())
    }
}

/// Successful tool output: JSON plus an optional inline PNG (base64).
struct Reply {
    json: Value,
    image_b64: Option<String>,
}

impl From<Value> for Reply {
    fn from(json: Value) -> Self {
        Self {
            json,
            image_b64: None,
        }
    }
}

/// Shared server state.
pub struct Ctx {
    factory: BackendFactory,
    backend: Mutex<Option<SharedBackend>>,
    input_lock: Arc<Mutex<()>>,
    output: OutputConfig,
}

/// Whether an operation synthesizes input (and must be serialized).
#[derive(Clone, Copy, PartialEq, Eq)]
enum OpKind {
    Query,
    Input,
}

impl Ctx {
    /// Get (or lazily create) the backend.
    async fn backend(&self) -> Outcome<SharedBackend> {
        let mut slot = self.backend.lock().await;
        if let Some(b) = slot.as_ref() {
            return Ok(b.clone());
        }
        info!("Initializing desktop control backend");
        let factory = self.factory.clone();
        let created =
            tokio::time::timeout(INIT_TIMEOUT, tokio::task::spawn_blocking(move || factory()))
                .await;
        let result = match created {
            Ok(Ok(Ok(b))) => Ok(b),
            Ok(Ok(Err(e))) => Err(e.to_string()),
            Ok(Err(join)) => Err(format!("backend initialization panicked: {join}")),
            Err(_) => Err(format!(
                "timed out after {}s connecting to the display",
                INIT_TIMEOUT.as_secs()
            )),
        };
        match result {
            Ok(b) => {
                info!("Desktop backend ready: {}", b.platform_name());
                *slot = Some(b.clone());
                Ok(b)
            },
            Err(msg) => {
                warn!("Desktop backend unavailable: {msg}");
                Err(Failure::Exec(format!("Desktop backend unavailable: {msg}")))
            },
        }
    }

    /// Run a blocking backend operation with a timeout of `OP_TIMEOUT + extra`.
    async fn run<T, F>(&self, kind: OpKind, extra: Duration, f: F) -> Outcome<T>
    where
        T: Send + 'static,
        F: FnOnce(&dyn DesktopBackend) -> DesktopResult<T> + Send + 'static,
    {
        let budget = OP_TIMEOUT + extra;
        let work = async {
            let backend = self.backend().await?;
            // The guard moves into the blocking task, so the lock is held
            // until the input actually finishes, even if we time out waiting.
            let guard = match kind {
                OpKind::Input => Some(self.input_lock.clone().lock_owned().await),
                OpKind::Query => None,
            };
            let joined = tokio::task::spawn_blocking(move || {
                let _guard = guard;
                f(backend.as_ref())
            })
            .await;
            match joined {
                Ok(Ok(v)) => Ok(v),
                Ok(Err(DesktopError::Disconnected(msg))) => {
                    warn!("Display connection lost ({msg}); will reconnect on next call");
                    self.backend.lock().await.take();
                    Err(Failure::Exec(format!(
                        "Display connection lost: {msg}. The next call will reconnect."
                    )))
                },
                Ok(Err(e)) => Err(e.into()),
                Err(join) => Err(Failure::Exec(format!("Desktop operation panicked: {join}"))),
            }
        };
        tokio::time::timeout(budget, work)
            .await
            .unwrap_or_else(|_| {
                Err(Failure::Exec(format!(
                    "Desktop operation timed out after {}s",
                    budget.as_secs()
                )))
            })
    }
}

type ToolFuture = Pin<Box<dyn Future<Output = Outcome<Reply>> + Send>>;
type Handler = fn(Arc<Ctx>, Value) -> ToolFuture;

/// One MCP tool backed by a handler function.
struct DesktopTool {
    name: &'static str,
    description: &'static str,
    schema: fn() -> Value,
    handler: Handler,
    ctx: Arc<Ctx>,
}

#[async_trait]
impl Tool for DesktopTool {
    fn name(&self) -> &str {
        self.name
    }

    fn description(&self) -> &str {
        self.description
    }

    fn schema(&self) -> Value {
        (self.schema)()
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        match (self.handler)(self.ctx.clone(), args).await {
            Ok(Reply { json, image_b64 }) => {
                let mut content = vec![Content::json(&json)?];
                if let Some(data) = image_b64 {
                    content.push(Content::Image {
                        data,
                        mime_type: "image/png".to_string(),
                    });
                }
                Ok(ToolResult::with_content(content))
            },
            Err(Failure::Invalid(msg)) => Err(MCPError::InvalidParameters(msg)),
            Err(Failure::Exec(msg)) => {
                let body = json!({"success": false, "error": msg});
                let text = serde_json::to_string_pretty(&body).unwrap_or(msg);
                Ok(ToolResult::error(text))
            },
        }
    }
}

/// Parse arguments, mapping failures to [`Failure::Invalid`].
fn parse<T: DeserializeOwned>(args: Value) -> Outcome<T> {
    args::parse(args).map_err(Failure::Invalid)
}

/// Map a validation result to [`Failure::Invalid`].
fn check<T>(r: std::result::Result<T, String>) -> Outcome<T> {
    r.map_err(Failure::Invalid)
}

/// The desktop control server: builds the tool set around shared state.
pub struct DesktopControlServer {
    ctx: Arc<Ctx>,
}

impl DesktopControlServer {
    /// Server using the real platform backend.
    pub fn new(output: OutputConfig) -> Self {
        Self::with_factory(output, Arc::new(crate::backend::create_backend))
    }

    /// Server using a custom backend factory (used by tests).
    pub fn with_factory(output: OutputConfig, factory: BackendFactory) -> Self {
        Self {
            ctx: Arc::new(Ctx {
                factory,
                backend: Mutex::new(None),
                input_lock: Arc::new(Mutex::new(())),
                output,
            }),
        }
    }

    /// All tools, ready to register with the MCP server builder.
    pub fn tools(&self) -> Vec<BoxedTool> {
        macro_rules! tool {
            ($name:literal, $desc:expr, $schema:expr, $handler:ident) => {
                Arc::new(DesktopTool {
                    name: $name,
                    description: $desc,
                    schema: || $schema,
                    handler: |ctx, args| Box::pin($handler(ctx, args)),
                    ctx: self.ctx.clone(),
                }) as BoxedTool
            };
        }

        vec![
            tool!(
                "desktop_status",
                DESC_STATUS,
                empty_schema(),
                desktop_status
            ),
            // Windows
            tool!(
                "list_windows",
                DESC_LIST_WINDOWS,
                list_windows_schema(),
                list_windows
            ),
            tool!(
                "get_active_window",
                DESC_ACTIVE_WINDOW,
                empty_schema(),
                get_active_window
            ),
            tool!("focus_window", DESC_FOCUS, window_schema(), focus_window),
            tool!(
                "move_window",
                DESC_MOVE_WINDOW,
                move_window_schema(),
                move_window
            ),
            tool!(
                "resize_window",
                DESC_RESIZE_WINDOW,
                resize_window_schema(),
                resize_window
            ),
            tool!(
                "minimize_window",
                DESC_MINIMIZE,
                window_schema(),
                minimize_window
            ),
            tool!(
                "maximize_window",
                DESC_MAXIMIZE,
                window_schema(),
                maximize_window
            ),
            tool!(
                "restore_window",
                DESC_RESTORE,
                window_schema(),
                restore_window
            ),
            tool!("close_window", DESC_CLOSE, window_schema(), close_window),
            // Screens
            tool!(
                "list_screens",
                DESC_LIST_SCREENS,
                empty_schema(),
                list_screens
            ),
            tool!(
                "get_screen_size",
                DESC_SCREEN_SIZE,
                empty_schema(),
                get_screen_size
            ),
            // Screenshots
            tool!(
                "screenshot_screen",
                DESC_SHOT_SCREEN,
                screenshot_screen_schema(),
                screenshot_screen
            ),
            tool!(
                "screenshot_window",
                DESC_SHOT_WINDOW,
                screenshot_window_schema(),
                screenshot_window
            ),
            tool!(
                "screenshot_region",
                DESC_SHOT_REGION,
                screenshot_region_schema(),
                screenshot_region
            ),
            // Mouse
            tool!(
                "get_mouse_position",
                DESC_MOUSE_POS,
                empty_schema(),
                get_mouse_position
            ),
            tool!(
                "move_mouse",
                DESC_MOVE_MOUSE,
                move_mouse_schema(),
                move_mouse
            ),
            tool!("click_mouse", DESC_CLICK, click_schema(), click_mouse),
            tool!("drag_mouse", DESC_DRAG, drag_schema(), drag_mouse),
            tool!("scroll_mouse", DESC_SCROLL, scroll_schema(), scroll_mouse),
            // Keyboard
            tool!("type_text", DESC_TYPE, type_text_schema(), type_text),
            tool!("send_key", DESC_SEND_KEY, send_key_schema(), send_key),
            tool!("send_hotkey", DESC_HOTKEY, hotkey_schema(), send_hotkey),
        ]
    }
}

// ============================================================================
// Descriptions
// ============================================================================

const DESC_STATUS: &str = "Get desktop control server status: version, platform backend, whether \
a display is reachable (and why not), output directory and input limits. Connects to the display \
if not yet connected.";
const DESC_LIST_WINDOWS: &str = "List top-level application windows with id, title, process, \
absolute position, size and state. Use the returned id with the other window tools.";
const DESC_ACTIVE_WINDOW: &str = "Get the currently focused window (null if none).";
const DESC_FOCUS: &str = "Bring a window to the foreground and give it keyboard focus \
(restores it first if minimized).";
const DESC_MOVE_WINDOW: &str = "Move a window so its top-left corner is at (x, y) in absolute \
desktop coordinates.";
const DESC_RESIZE_WINDOW: &str = "Resize a window to width x height pixels.";
const DESC_MINIMIZE: &str = "Minimize (iconify) a window.";
const DESC_MAXIMIZE: &str = "Maximize a window.";
const DESC_RESTORE: &str = "Restore a minimized or maximized window to its normal state.";
const DESC_CLOSE: &str = "Ask a window to close, exactly like clicking its close button. The \
application may prompt about unsaved work; it is not force-killed.";
const DESC_LIST_SCREENS: &str = "List monitors with id, name, absolute position, resolution, \
primary flag and DPI scale.";
const DESC_SCREEN_SIZE: &str = "Get the primary screen resolution plus the bounding box of the \
whole virtual desktop (all monitors).";
const DESC_SHOT_SCREEN: &str = "Capture a monitor (default: the primary screen) as PNG. The \
file is saved under the server's output directory; set return_image=true to also receive the \
image inline, and max_dimension to downscale it.";
const DESC_SHOT_WINDOW: &str = "Capture a window as PNG. On X11 this captures the window's \
on-screen area (overlapping windows are included); on Windows the window content is rendered \
directly. The window must not be minimized.";
const DESC_SHOT_REGION: &str = "Capture a rectangle of the desktop as PNG. The region is \
clipped to the desktop; the response reports the area actually captured.";
const DESC_MOUSE_POS: &str = "Get the current mouse cursor position in absolute desktop \
coordinates.";
const DESC_MOVE_MOUSE: &str = "Move the mouse cursor to (x, y), or by (x, y) when \
relative=true.";
const DESC_CLICK: &str = "Click a mouse button, optionally moving to (x, y) first (give both \
or neither). Use clicks=2 for a double-click.";
const DESC_DRAG: &str = "Press a mouse button at the start point, move smoothly to the end \
point over duration_ms, and release. The button is always released, even on error.";
const DESC_SCROLL: &str = "Scroll the mouse wheel by amount notches (positive = down/right, \
negative = up/left), optionally at (x, y).";
const DESC_TYPE: &str = "Type literal text into the focused window. Newlines press Enter and \
tabs press Tab. Characters that cannot be typed on the current keyboard layout are reported in \
'skipped' rather than silently dropped.";
const DESC_SEND_KEY: &str = "Press a single key, optionally while holding modifiers.

Keys: a single character ('a', '5', '/') or a name: enter/return, tab, escape, backspace, \
delete, insert, home, end, pageup, pagedown, left, right, up, down, space, f1-f24, capslock, \
printscreen, menu, volumeup, volumedown, volumemute, playpause.
Examples: {\"key\": \"Return\"}; {\"key\": \"a\", \"modifiers\": [\"ctrl\"]} for Ctrl+A; \
{\"key\": \"s\", \"modifiers\": [\"ctrl\", \"shift\"]} for Ctrl+Shift+S.";
const DESC_HOTKEY: &str = "Press a key combination: keys are pressed in order and released in \
reverse. Letters are case-insensitive (add \"shift\" explicitly).

Examples: [\"ctrl\", \"c\"] (copy); [\"alt\", \"tab\"]; [\"super\", \"l\"]; \
[\"ctrl\", \"shift\", \"escape\"].";

// ============================================================================
// Schemas
// ============================================================================

fn empty_schema() -> Value {
    json!({"type": "object", "properties": {}})
}

fn window_id_prop() -> Value {
    json!({
        "type": "string",
        "description": "Window id from list_windows (decimal; 0x-prefixed hex also accepted)"
    })
}

fn window_schema() -> Value {
    json!({
        "type": "object",
        "properties": {"window_id": window_id_prop()},
        "required": ["window_id"]
    })
}

fn list_windows_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "title_filter": {
                "type": "string",
                "description": "Only windows whose title contains this text (case-insensitive)"
            },
            "visible_only": {
                "type": "boolean",
                "description": "Only return visible (mapped, non-minimized) windows (default: true)",
                "default": true
            }
        }
    })
}

fn move_window_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "window_id": window_id_prop(),
            "x": {"type": "integer", "description": "New X position (absolute desktop pixels)"},
            "y": {"type": "integer", "description": "New Y position (absolute desktop pixels)"}
        },
        "required": ["window_id", "x", "y"]
    })
}

fn resize_window_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "window_id": window_id_prop(),
            "width": {"type": "integer", "minimum": 1, "maximum": MAX_WINDOW_DIM, "description": "New width in pixels"},
            "height": {"type": "integer", "minimum": 1, "maximum": MAX_WINDOW_DIM, "description": "New height in pixels"}
        },
        "required": ["window_id", "width", "height"]
    })
}

fn screenshot_props() -> serde_json::Map<String, Value> {
    let v = json!({
        "output_path": {
            "type": "string",
            "description": "File name or relative path inside the output directory \
                (default: auto-generated). '.png' is appended if missing; paths outside \
                the output directory are rejected."
        },
        "return_image": {
            "type": "boolean",
            "description": "Also return the PNG inline as image content (default: false)",
            "default": false
        },
        "max_dimension": {
            "type": "integer",
            "minimum": MIN_MAX_DIMENSION,
            "description": "Downscale so neither side exceeds this many pixels (keeps aspect \
                ratio). Recommended (e.g. 1280) with return_image to keep responses small."
        }
    });
    match v {
        Value::Object(m) => m,
        _ => serde_json::Map::new(),
    }
}

fn with_screenshot_props(mut schema: Value) -> Value {
    if let Some(props) = schema.get_mut("properties").and_then(Value::as_object_mut) {
        props.extend(screenshot_props());
    }
    schema
}

fn screenshot_screen_schema() -> Value {
    with_screenshot_props(json!({
        "type": "object",
        "properties": {
            "screen_id": {
                "type": "integer",
                "minimum": 0,
                "description": "Screen id from list_screens (default: primary screen)"
            }
        }
    }))
}

fn screenshot_window_schema() -> Value {
    with_screenshot_props(json!({
        "type": "object",
        "properties": {"window_id": window_id_prop()},
        "required": ["window_id"]
    }))
}

fn screenshot_region_schema() -> Value {
    with_screenshot_props(json!({
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Left edge (absolute desktop pixels)"},
            "y": {"type": "integer", "description": "Top edge (absolute desktop pixels)"},
            "width": {"type": "integer", "minimum": 1, "description": "Region width"},
            "height": {"type": "integer", "minimum": 1, "description": "Region height"}
        },
        "required": ["x", "y", "width", "height"]
    }))
}

fn move_mouse_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate (or X offset when relative)"},
            "y": {"type": "integer", "description": "Y coordinate (or Y offset when relative)"},
            "relative": {
                "type": "boolean",
                "description": "Move relative to the current position (default: false)",
                "default": false
            }
        },
        "required": ["x", "y"]
    })
}

fn button_prop(what: &str) -> Value {
    json!({
        "type": "string",
        "enum": ["left", "right", "middle"],
        "description": format!("Mouse button {what} (default: left)"),
        "default": "left"
    })
}

fn click_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "button": button_prop("to click"),
            "x": {"type": "integer", "description": "X coordinate to click at (requires y; default: current position)"},
            "y": {"type": "integer", "description": "Y coordinate to click at (requires x; default: current position)"},
            "clicks": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_CLICKS,
                "description": "Number of clicks (default: 1; 2 = double-click)",
                "default": 1
            }
        }
    })
}

fn drag_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "start_x": {"type": "integer", "description": "Starting X coordinate"},
            "start_y": {"type": "integer", "description": "Starting Y coordinate"},
            "end_x": {"type": "integer", "description": "Ending X coordinate"},
            "end_y": {"type": "integer", "description": "Ending Y coordinate"},
            "button": button_prop("to hold during the drag"),
            "duration_ms": {
                "type": "integer",
                "minimum": 0,
                "maximum": MAX_DRAG_MS,
                "description": "Duration of the movement in milliseconds (default: 500)",
                "default": 500
            }
        },
        "required": ["start_x", "start_y", "end_x", "end_y"]
    })
}

fn scroll_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "amount": {
                "type": "integer",
                "minimum": -MAX_SCROLL,
                "maximum": MAX_SCROLL,
                "description": "Wheel notches (positive = down/right, negative = up/left)"
            },
            "direction": {
                "type": "string",
                "enum": ["vertical", "horizontal"],
                "description": "Scroll axis (default: vertical)",
                "default": "vertical"
            },
            "x": {"type": "integer", "description": "X coordinate to scroll at (requires y)"},
            "y": {"type": "integer", "description": "Y coordinate to scroll at (requires x)"}
        },
        "required": ["amount"]
    })
}

fn type_text_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "maxLength": MAX_TEXT_CHARS,
                "description": "Text to type"
            },
            "interval_ms": {
                "type": "integer",
                "minimum": 0,
                "maximum": MAX_INTERVAL_MS,
                "description": "Delay between characters in milliseconds (default: 50)",
                "default": 50
            }
        },
        "required": ["text"]
    })
}

fn send_key_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Key to press: a single character or a key name (e.g. 'a', 'Return', 'Escape', 'Tab', 'F5', 'Left')"
            },
            "modifiers": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["ctrl", "alt", "shift", "win", "super"]
                },
                "description": "Modifier keys to hold while pressing the key"
            }
        },
        "required": ["key"]
    })
}

fn hotkey_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": MAX_HOTKEY_KEYS,
                "description": "Keys to press together, modifiers first (e.g. ['ctrl', 'c'])"
            }
        },
        "required": ["keys"]
    })
}

// ============================================================================
// Handlers
// ============================================================================

async fn desktop_status(ctx: Arc<Ctx>, _args: Value) -> Outcome<Reply> {
    let backend = ctx.backend().await;
    let mut status = json!({
        "server": "desktop-control",
        "version": VERSION,
        "os": std::env::consts::OS,
        "available": backend.is_ok(),
        "output_dir": ctx.output.dir.to_string_lossy(),
        "limits": {
            "max_text_chars": MAX_TEXT_CHARS,
            "max_interval_ms": MAX_INTERVAL_MS,
            "max_drag_ms": MAX_DRAG_MS,
            "max_clicks": MAX_CLICKS,
            "max_scroll": MAX_SCROLL,
            "max_hotkey_keys": MAX_HOTKEY_KEYS,
            "operation_timeout_s": OP_TIMEOUT.as_secs()
        }
    });
    if let Some(host) = &ctx.output.host_dir {
        status["host_output_dir"] = json!(host);
    }
    if cfg!(target_os = "linux") {
        status["display"] = json!(std::env::var("DISPLAY").ok());
        if std::env::var_os("WAYLAND_DISPLAY").is_some() {
            status["warning"] = json!(
                "WAYLAND_DISPLAY is set: only XWayland windows are visible/controllable \
                 through the X11 backend"
            );
        }
    }
    match backend {
        Ok(b) => {
            status["initialized"] = json!(true);
            status["platform"] = json!(b.platform_name());
            let diag = b.diagnostics();
            if !diag.is_null() {
                status["diagnostics"] = diag;
            }
        },
        Err(Failure::Exec(msg) | Failure::Invalid(msg)) => {
            status["initialized"] = json!(false);
            status["error"] = json!(msg);
        },
    }
    Ok(status.into())
}

async fn list_windows(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: ListWindowsArgs = parse(args)?;
    let windows = ctx
        .run(OpKind::Query, Duration::ZERO, |b| b.list_windows())
        .await?;
    let windows = actions::filter_windows(windows, a.title_filter.as_deref(), a.visible_only());
    Ok(json!({"success": true, "count": windows.len(), "windows": windows}).into())
}

async fn get_active_window(ctx: Arc<Ctx>, _args: Value) -> Outcome<Reply> {
    let window = ctx
        .run(OpKind::Query, Duration::ZERO, |b| b.get_active_window())
        .await?;
    Ok(match window {
        Some(w) => json!({"success": true, "window": w}),
        None => json!({"success": true, "window": null, "message": "No active window"}),
    }
    .into())
}

/// Shared body of the single-window state tools.
async fn window_op(
    ctx: Arc<Ctx>,
    args: Value,
    op: fn(&dyn DesktopBackend, &str) -> DesktopResult<()>,
) -> Outcome<Reply> {
    let a: WindowArgs = parse(args)?;
    let id = a.window_id.clone();
    ctx.run(OpKind::Input, Duration::ZERO, move |b| op(b, &id))
        .await?;
    Ok(json!({"success": true, "window_id": a.window_id}).into())
}

async fn focus_window(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    window_op(ctx, args, |b, id| b.focus_window(id)).await
}

async fn minimize_window(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    window_op(ctx, args, |b, id| b.minimize_window(id)).await
}

async fn maximize_window(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    window_op(ctx, args, |b, id| b.maximize_window(id)).await
}

async fn restore_window(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    window_op(ctx, args, |b, id| b.restore_window(id)).await
}

async fn close_window(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    window_op(ctx, args, |b, id| b.close_window(id)).await
}

async fn move_window(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: MoveWindowArgs = parse(args)?;
    let (id, x, y) = (a.window_id.clone(), a.x, a.y);
    ctx.run(OpKind::Input, Duration::ZERO, move |b| {
        b.move_window(&id, x, y)
    })
    .await?;
    Ok(json!({"success": true, "window_id": a.window_id, "x": a.x, "y": a.y}).into())
}

async fn resize_window(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: ResizeWindowArgs = parse(args)?;
    check(a.validate())?;
    let (id, w, h) = (a.window_id.clone(), a.width, a.height);
    ctx.run(OpKind::Input, Duration::ZERO, move |b| {
        b.resize_window(&id, w, h)
    })
    .await?;
    Ok(json!({
        "success": true,
        "window_id": a.window_id,
        "width": a.width,
        "height": a.height
    })
    .into())
}

async fn list_screens(ctx: Arc<Ctx>, _args: Value) -> Outcome<Reply> {
    let screens = ctx
        .run(OpKind::Query, Duration::ZERO, |b| b.list_screens())
        .await?;
    Ok(json!({"success": true, "count": screens.len(), "screens": screens}).into())
}

async fn get_screen_size(ctx: Arc<Ctx>, _args: Value) -> Outcome<Reply> {
    let (screens, desktop) = ctx
        .run(OpKind::Query, Duration::ZERO, |b| {
            Ok((b.list_screens()?, b.virtual_screen()?))
        })
        .await?;
    let (width, height) = actions::primary_screen(&screens)
        .map(|s| (s.width, s.height))
        .unwrap_or((desktop.width, desktop.height));
    Ok(json!({
        "success": true,
        "width": width,
        "height": height,
        "screen_count": screens.len(),
        "virtual_screen": desktop
    })
    .into())
}

/// What to capture.
enum Target {
    Screen(Option<u32>),
    Window(String),
    Region(Rect),
}

/// Capture, post-process, save and (optionally) inline a screenshot.
async fn screenshot(
    ctx: Arc<Ctx>,
    target: Target,
    opts: ScreenshotOptions,
    prefix: &'static str,
) -> Outcome<Reply> {
    check(opts.validate())?;
    let path = check(output::resolve_output_path(
        &ctx.output.dir,
        opts.output_path.as_deref(),
        prefix,
        chrono::Utc::now(),
    ))?;
    let dir = ctx.output.dir.clone();
    let write_path = path.clone();
    let max_dimension = opts.max_dimension;

    let (png, width, height, captured) = ctx
        .run(OpKind::Query, Duration::ZERO, move |b| {
            let (img, captured) = match target {
                Target::Screen(id) => {
                    let rect = actions::screen_rect(&b.list_screens()?, id)?;
                    let rect = actions::clip_region(rect, b.virtual_screen()?)?;
                    (b.capture_region(rect)?, rect)
                },
                Target::Window(id) => b.capture_window(&id)?,
                Target::Region(requested) => {
                    let rect = actions::clip_region(requested, b.virtual_screen()?)?;
                    (b.capture_region(rect)?, rect)
                },
            };
            let img = match max_dimension {
                Some(max) => imaging::downscale(img, max),
                None => img,
            };
            let (w, h) = img.dimensions();
            let png = imaging::encode_png(&img).map_err(DesktopError::ScreenshotFailed)?;
            output::write_confined(&dir, &write_path, &png)
                .map_err(DesktopError::OperationFailed)?;
            Ok((png, w, h, captured))
        })
        .await?;

    let mut json = json!({
        "success": true,
        "output_path": path.to_string_lossy(),
        "format": "png",
        "size_bytes": png.len(),
        "width": width,
        "height": height,
        "captured_region": captured
    });
    if let Some(host) = ctx.output.host_path_for(&path) {
        json["host_path"] = json!(host);
    }
    let mut image_b64 = None;
    if opts.return_image() {
        if png.len() <= MAX_INLINE_IMAGE_BYTES {
            image_b64 = Some(base64::engine::general_purpose::STANDARD.encode(&png));
        } else {
            json["image_omitted"] = json!(format!(
                "PNG is {} bytes (> {} inline limit); pass max_dimension to shrink it",
                png.len(),
                MAX_INLINE_IMAGE_BYTES
            ));
        }
    }
    Ok(Reply { json, image_b64 })
}

async fn screenshot_screen(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: ScreenshotScreenArgs = parse(args)?;
    let mut reply = screenshot(ctx, Target::Screen(a.screen_id), a.opts, "screen").await?;
    if let Some(id) = a.screen_id {
        reply.json["screen_id"] = json!(id);
    }
    Ok(reply)
}

async fn screenshot_window(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: ScreenshotWindowArgs = parse(args)?;
    let id = a.window_id.clone();
    let mut reply = screenshot(ctx, Target::Window(id), a.opts, "window").await?;
    reply.json["window_id"] = json!(a.window_id);
    Ok(reply)
}

async fn screenshot_region(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: ScreenshotRegionArgs = parse(args)?;
    let requested = Rect::new(a.x, a.y, a.width, a.height);
    let mut reply = screenshot(ctx, Target::Region(requested), a.opts, "region").await?;
    reply.json["region"] = json!(requested);
    Ok(reply)
}

async fn get_mouse_position(ctx: Arc<Ctx>, _args: Value) -> Outcome<Reply> {
    let (x, y) = ctx
        .run(OpKind::Query, Duration::ZERO, |b| b.mouse_position())
        .await?;
    Ok(json!({"success": true, "x": x, "y": y}).into())
}

async fn move_mouse(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: MoveMouseArgs = parse(args)?;
    let (x, y, relative) = (a.x, a.y, a.relative());
    let (tx, ty) = ctx
        .run(OpKind::Input, Duration::ZERO, move |b| {
            actions::move_mouse(b, x, y, relative)
        })
        .await?;
    Ok(json!({
        "success": true,
        "x": x,
        "y": y,
        "relative": relative,
        "position": {"x": tx, "y": ty}
    })
    .into())
}

async fn click_mouse(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: ClickMouseArgs = parse(args)?;
    let at = check(a.validate())?;
    let (button, clicks) = (a.button, a.clicks);
    ctx.run(OpKind::Input, Duration::ZERO, move |b| {
        actions::click(b, button, at, clicks)
    })
    .await?;
    let mut json = json!({"success": true, "button": button, "clicks": clicks});
    if let Some((x, y)) = at {
        json["x"] = json!(x);
        json["y"] = json!(y);
    }
    Ok(json.into())
}

async fn drag_mouse(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: DragMouseArgs = parse(args)?;
    check(a.validate())?;
    let start = (a.start_x, a.start_y);
    let end = (a.end_x, a.end_y);
    let (button, duration) = (a.button, a.duration_ms);
    ctx.run(OpKind::Input, Duration::from_millis(duration), move |b| {
        actions::drag(b, start, end, button, duration)
    })
    .await?;
    Ok(json!({
        "success": true,
        "start": {"x": start.0, "y": start.1},
        "end": {"x": end.0, "y": end.1},
        "button": button,
        "duration_ms": duration
    })
    .into())
}

async fn scroll_mouse(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: ScrollMouseArgs = parse(args)?;
    let at = check(a.validate())?;
    let (direction, amount) = (a.direction, a.amount);
    ctx.run(OpKind::Input, Duration::ZERO, move |b| {
        actions::scroll(b, direction, amount, at)
    })
    .await?;
    Ok(json!({"success": true, "amount": amount, "direction": direction}).into())
}

async fn type_text(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: TypeTextArgs = parse(args)?;
    check(a.validate())?;
    let chars = a.text.chars().count();
    let interval = a.interval_ms;
    // Budget: requested delays plus a generous per-character allowance.
    let extra = Duration::from_millis((interval + 5).saturating_mul(chars as u64));
    let text = a.text;
    let report = ctx
        .run(OpKind::Input, extra, move |b| b.type_text(&text, interval))
        .await?;
    let mut json = json!({
        "success": report.skipped.is_empty(),
        "text_length": chars,
        "typed": report.typed
    });
    if !report.skipped.is_empty() {
        let skipped: String = report.skipped.iter().collect();
        json["skipped"] = json!(skipped);
        json["message"] = json!(format!(
            "{} character(s) could not be typed with the current keyboard layout",
            report.skipped.len()
        ));
    }
    Ok(json.into())
}

async fn send_key(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: SendKeyArgs = parse(args)?;
    let key = check(parse_key(&a.key))?;
    let modifiers = a.modifiers.unwrap_or_default();
    let mut chord: Vec<Key> = Vec::with_capacity(modifiers.len() + 1);
    for m in &modifiers {
        let k = Key::from(*m);
        if !chord.contains(&k) {
            chord.push(k);
        }
    }
    chord.push(key);
    ctx.run(OpKind::Input, Duration::ZERO, move |b| {
        actions::chord(b, &chord)
    })
    .await?;
    Ok(json!({"success": true, "key": a.key, "modifiers": modifiers}).into())
}

async fn send_hotkey(ctx: Arc<Ctx>, args: Value) -> Outcome<Reply> {
    let a: SendHotkeyArgs = parse(args)?;
    check(a.validate())?;
    let keys = a
        .keys
        .iter()
        .map(|k| parse_key(k))
        .collect::<std::result::Result<Vec<Key>, String>>()
        .map_err(Failure::Invalid)?;
    ctx.run(OpKind::Input, Duration::ZERO, move |b| {
        actions::chord(b, &keys)
    })
    .await?;
    Ok(json!({"success": true, "keys": a.keys}).into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::mock::{Event, MockBackend};
    use crate::keys::NamedKey;
    use crate::types::MouseButton;
    use std::collections::HashMap;
    use std::path::PathBuf;

    struct Harness {
        tools: HashMap<String, BoxedTool>,
        mock: Arc<MockBackend>,
        _dir: tempfile::TempDir,
        out: PathBuf,
    }

    fn harness() -> Harness {
        harness_with(MockBackend::new())
    }

    fn harness_with(mock: MockBackend) -> Harness {
        let dir = tempfile::tempdir().unwrap();
        let out = dir.path().join("shots");
        let mock = Arc::new(mock);
        let m2 = mock.clone();
        let server = DesktopControlServer::with_factory(
            OutputConfig {
                dir: out.clone(),
                host_dir: Some("outputs/desktop-control".to_string()),
            },
            Arc::new(move || Ok(m2.clone() as SharedBackend)),
        );
        let tools = server
            .tools()
            .into_iter()
            .map(|t| (t.name().to_string(), t))
            .collect();
        Harness {
            tools,
            mock,
            _dir: dir,
            out,
        }
    }

    impl Harness {
        async fn call(&self, name: &str, args: Value) -> Result<ToolResult> {
            self.tools[name].execute(args).await
        }

        async fn ok(&self, name: &str, args: Value) -> Value {
            let r = self.call(name, args).await.expect("tool call failed");
            assert!(!r.is_error, "{name} returned error: {:?}", r.content);
            match &r.content[0] {
                Content::Text { text } => serde_json::from_str(text).unwrap(),
                other => panic!("unexpected content {other:?}"),
            }
        }

        async fn exec_err(&self, name: &str, args: Value) -> String {
            let r = self
                .call(name, args)
                .await
                .expect("expected isError result");
            assert!(r.is_error, "{name} unexpectedly succeeded");
            match &r.content[0] {
                Content::Text { text } => text.clone(),
                other => panic!("unexpected content {other:?}"),
            }
        }

        async fn invalid(&self, name: &str, args: Value) -> String {
            match self.call(name, args).await {
                Err(MCPError::InvalidParameters(msg)) => msg,
                other => panic!("{name}: expected InvalidParameters, got {other:?}"),
            }
        }
    }

    const ALL_TOOLS: [&str; 23] = [
        "desktop_status",
        "list_windows",
        "get_active_window",
        "focus_window",
        "move_window",
        "resize_window",
        "minimize_window",
        "maximize_window",
        "restore_window",
        "close_window",
        "list_screens",
        "get_screen_size",
        "screenshot_screen",
        "screenshot_window",
        "screenshot_region",
        "get_mouse_position",
        "move_mouse",
        "click_mouse",
        "drag_mouse",
        "scroll_mouse",
        "type_text",
        "send_key",
        "send_hotkey",
    ];

    #[test]
    fn all_legacy_tools_are_registered() {
        let h = harness();
        assert_eq!(h.tools.len(), ALL_TOOLS.len());
        for name in ALL_TOOLS {
            assert!(h.tools.contains_key(name), "missing tool {name}");
        }
    }

    #[test]
    fn schemas_are_objects_and_required_fields_exist() {
        let h = harness();
        for (name, tool) in &h.tools {
            let schema = tool.schema();
            assert_eq!(schema["type"], "object", "{name}");
            let props = schema["properties"].as_object().expect(name);
            if let Some(req) = schema.get("required").and_then(Value::as_array) {
                for r in req {
                    let r = r.as_str().unwrap();
                    assert!(
                        props.contains_key(r),
                        "{name}: required '{r}' not in properties"
                    );
                }
            }
            assert!(!tool.description().is_empty(), "{name}");
        }
    }

    #[tokio::test]
    async fn required_params_in_schema_match_parser() {
        // Calling with {} must be rejected exactly when the schema has
        // required fields (keeps hand-written schemas and structs in sync).
        let h = harness();
        for (name, tool) in &h.tools {
            let has_required = tool
                .schema()
                .get("required")
                .and_then(Value::as_array)
                .is_some_and(|r| !r.is_empty());
            let result = tool.execute(json!({})).await;
            let rejected = matches!(result, Err(MCPError::InvalidParameters(_)));
            assert_eq!(has_required, rejected, "{name}: {result:?}");
        }
    }

    #[tokio::test]
    async fn status_reports_platform_and_output() {
        let h = harness();
        let v = h.ok("desktop_status", json!({})).await;
        assert_eq!(v["available"], true);
        assert_eq!(v["platform"], "mock");
        assert_eq!(v["version"], VERSION);
        assert_eq!(v["host_output_dir"], "outputs/desktop-control");
    }

    #[tokio::test]
    async fn status_reports_init_failure_and_tools_fail_cleanly() {
        let dir = tempfile::tempdir().unwrap();
        let server = DesktopControlServer::with_factory(
            OutputConfig {
                dir: dir.path().to_path_buf(),
                host_dir: None,
            },
            Arc::new(|| Err(DesktopError::NotAvailable("no DISPLAY".to_string()))),
        );
        let tools: HashMap<String, BoxedTool> = server
            .tools()
            .into_iter()
            .map(|t| (t.name().to_string(), t))
            .collect();
        let r = tools["desktop_status"].execute(json!({})).await.unwrap();
        let Content::Text { text } = &r.content[0] else {
            panic!()
        };
        let v: Value = serde_json::from_str(text).unwrap();
        assert_eq!(v["available"], false);
        assert!(v["error"].as_str().unwrap().contains("no DISPLAY"));

        let r = tools["list_windows"].execute(json!({})).await.unwrap();
        assert!(r.is_error);
    }

    #[tokio::test]
    async fn list_windows_filters() {
        let h = harness();
        let v = h.ok("list_windows", json!({})).await;
        assert_eq!(v["count"], 2);
        let v = h.ok("list_windows", json!({"visible_only": false})).await;
        assert_eq!(v["count"], 3);
        let v = h
            .ok("list_windows", json!({"title_filter": "terminal"}))
            .await;
        assert_eq!(v["count"], 1);
        assert_eq!(v["windows"][0]["id"], "100");
        assert_eq!(v["windows"][0]["process_name"], "app");
    }

    #[tokio::test]
    async fn window_ops_reach_backend_and_report_missing_windows() {
        let h = harness();
        h.ok("focus_window", json!({"window_id": "100"})).await;
        h.ok("move_window", json!({"window_id": 200, "x": -5, "y": 7}))
            .await;
        h.ok(
            "resize_window",
            json!({"window_id": "0xc8", "width": 640, "height": 480}),
        )
        .await;
        h.ok("close_window", json!({"window_id": "100"})).await;
        assert_eq!(
            h.mock.events(),
            vec![
                Event::Focus("100".into()),
                Event::MoveWindow("200".into(), -5, 7),
                Event::ResizeWindow("200".into(), 640, 480),
                Event::Close("100".into()),
            ]
        );
        let err = h
            .exec_err("minimize_window", json!({"window_id": "999"}))
            .await;
        assert!(err.contains("Window not found: 999"), "{err}");
        let msg = h
            .invalid(
                "resize_window",
                json!({"window_id": "1", "width": 0, "height": 1}),
            )
            .await;
        assert!(msg.contains("width"), "{msg}");
    }

    #[tokio::test]
    async fn screen_size_uses_primary_screen() {
        let h = harness();
        let v = h.ok("get_screen_size", json!({})).await;
        assert_eq!(v["width"], 1280);
        assert_eq!(v["height"], 1024);
        assert_eq!(v["screen_count"], 2);
        assert_eq!(v["virtual_screen"]["width"], 3200);
    }

    #[tokio::test]
    async fn screenshot_screen_saves_png_and_can_inline() {
        let h = harness();
        let v = h
            .ok(
                "screenshot_screen",
                json!({"screen_id": 0, "output_path": "a"}),
            )
            .await;
        let path = PathBuf::from(v["output_path"].as_str().unwrap());
        assert_eq!(path, h.out.join("a.png"));
        let png = std::fs::read(&path).unwrap();
        assert_eq!(v["size_bytes"], png.len());
        assert_eq!(v["width"], 1920);
        assert_eq!(v["host_path"], "outputs/desktop-control/a.png");

        let r = h
            .call(
                "screenshot_screen",
                json!({"return_image": true, "max_dimension": 320}),
            )
            .await
            .unwrap();
        assert_eq!(r.content.len(), 2);
        let Content::Image { data, mime_type } = &r.content[1] else {
            panic!("expected image content")
        };
        assert_eq!(mime_type, "image/png");
        let bytes = base64::engine::general_purpose::STANDARD
            .decode(data)
            .unwrap();
        let img = image::load_from_memory(&bytes).unwrap();
        // Primary screen is 1280x1024 -> 320x256.
        assert_eq!((img.width(), img.height()), (320, 256));
    }

    #[tokio::test]
    async fn screenshot_rejects_escaping_paths_and_bad_screens() {
        let h = harness();
        let msg = h
            .invalid("screenshot_screen", json!({"output_path": "../evil.png"}))
            .await;
        assert!(msg.contains(".."), "{msg}");
        let err = h
            .exec_err("screenshot_screen", json!({"screen_id": 9}))
            .await;
        assert!(err.contains("valid ids"), "{err}");
    }

    #[tokio::test]
    async fn screenshot_region_is_clipped() {
        let h = harness();
        let v = h
            .ok(
                "screenshot_region",
                json!({"x": 3100, "y": 1000, "width": 500, "height": 500}),
            )
            .await;
        assert_eq!(v["captured_region"]["width"], 100);
        assert_eq!(v["captured_region"]["height"], 80);
        assert_eq!(v["region"]["width"], 500);
        let err = h
            .exec_err(
                "screenshot_region",
                json!({"x": 5000, "y": 0, "width": 10, "height": 10}),
            )
            .await;
        assert!(err.contains("outside the desktop"), "{err}");
    }

    #[tokio::test]
    async fn screenshot_window_uses_window_rect() {
        let h = harness();
        let v = h.ok("screenshot_window", json!({"window_id": "100"})).await;
        assert_eq!(v["width"], 300);
        assert_eq!(v["window_id"], "100");
        assert!(v["output_path"].as_str().unwrap().contains("window_"));
    }

    #[tokio::test]
    async fn mouse_tools_drive_backend() {
        let h = harness();
        let v = h
            .ok("move_mouse", json!({"x": 10, "y": -2, "relative": true}))
            .await;
        assert_eq!(v["position"]["x"], 15);
        assert_eq!(v["position"]["y"], 3);
        h.ok(
            "click_mouse",
            json!({"button": "middle", "x": 1, "y": 2, "clicks": 1}),
        )
        .await;
        h.ok("scroll_mouse", json!({"amount": -3})).await;
        let ev = h.mock.events();
        assert_eq!(
            ev,
            vec![
                Event::MoveMouse(15, 3),
                Event::MoveMouse(1, 2),
                Event::Button(MouseButton::Middle, true),
                Event::Button(MouseButton::Middle, false),
                Event::Scroll(crate::types::ScrollDirection::Vertical, -3),
            ]
        );
        let v = h.ok("get_mouse_position", json!({})).await;
        assert_eq!((v["x"].as_i64(), v["y"].as_i64()), (Some(1), Some(2)));
        h.invalid("click_mouse", json!({"x": 1})).await;
        h.invalid("click_mouse", json!({"button": "side"})).await;
        h.invalid(
            "drag_mouse",
            json!({"start_x": 0, "start_y": 0, "end_x": 1, "end_y": 1, "duration_ms": 999999}),
        )
        .await;
    }

    #[tokio::test]
    async fn keyboard_tools_validate_and_chord() {
        let h = harness();
        h.ok(
            "send_key",
            json!({"key": "S", "modifiers": ["ctrl", "shift", "ctrl"]}),
        )
        .await;
        let ctrl = Key::Named(NamedKey::Ctrl);
        let shift = Key::Named(NamedKey::Shift);
        let s = Key::Char('s');
        assert_eq!(
            h.mock.events(),
            vec![
                Event::Key(ctrl, true),
                Event::Key(shift, true),
                Event::Key(s, true),
                Event::Key(s, false),
                Event::Key(shift, false),
                Event::Key(ctrl, false),
            ]
        );
        let msg = h.invalid("send_key", json!({"key": "nonsense"})).await;
        assert!(msg.contains("Unknown key"), "{msg}");
        let msg = h
            .invalid("send_key", json!({"key": "a", "modifiers": ["hyper"]}))
            .await;
        assert!(msg.contains("Invalid modifier"), "{msg}");
        h.invalid("send_hotkey", json!({"keys": []})).await;
        h.invalid("send_hotkey", json!({"keys": ["ctrl", "bogus"]}))
            .await;
        h.ok("send_hotkey", json!({"keys": ["alt", "F4"]})).await;
    }

    #[tokio::test]
    async fn type_text_reports_skipped_characters() {
        let h = harness();
        let v = h
            .ok("type_text", json!({"text": "hi\u{1}!", "interval_ms": 0}))
            .await;
        assert_eq!(v["success"], false);
        assert_eq!(v["typed"], 3);
        assert_eq!(v["skipped"], "\u{1}");
        let v = h.ok("type_text", json!({"text": "hello"})).await;
        assert_eq!(v["success"], true);
        assert_eq!(v["text_length"], 5);
        h.invalid("type_text", json!({"text": "x", "interval_ms": 5000}))
            .await;
    }

    #[tokio::test]
    async fn input_operations_are_serialized() {
        // Two concurrent chords must not interleave their key events.
        let h = harness();
        let a = h.call("send_hotkey", json!({"keys": ["ctrl", "a"]}));
        let b = h.call("send_hotkey", json!({"keys": ["alt", "b"]}));
        let (ra, rb) = tokio::join!(a, b);
        ra.unwrap();
        rb.unwrap();
        let ev = h.mock.events();
        assert_eq!(ev.len(), 8);
        // Each chord's 4 events are contiguous: press, press, release, release.
        for half in ev.chunks(4) {
            assert!(matches!(half[0], Event::Key(_, true)));
            assert!(matches!(half[1], Event::Key(_, true)));
            assert!(matches!(half[2], Event::Key(_, false)));
            assert!(matches!(half[3], Event::Key(_, false)));
        }
    }

    #[tokio::test]
    async fn backend_is_reconnected_after_disconnect() {
        use std::sync::atomic::{AtomicUsize, Ordering};

        struct Flaky;
        impl DesktopBackend for Flaky {
            fn platform_name(&self) -> &'static str {
                "flaky"
            }
            fn list_windows(&self) -> DesktopResult<Vec<crate::types::WindowInfo>> {
                Err(DesktopError::Disconnected("gone".into()))
            }
            fn get_active_window(&self) -> DesktopResult<Option<crate::types::WindowInfo>> {
                Ok(None)
            }
            fn focus_window(&self, _: &str) -> DesktopResult<()> {
                Ok(())
            }
            fn move_window(&self, _: &str, _: i32, _: i32) -> DesktopResult<()> {
                Ok(())
            }
            fn resize_window(&self, _: &str, _: u32, _: u32) -> DesktopResult<()> {
                Ok(())
            }
            fn minimize_window(&self, _: &str) -> DesktopResult<()> {
                Ok(())
            }
            fn maximize_window(&self, _: &str) -> DesktopResult<()> {
                Ok(())
            }
            fn restore_window(&self, _: &str) -> DesktopResult<()> {
                Ok(())
            }
            fn close_window(&self, _: &str) -> DesktopResult<()> {
                Ok(())
            }
            fn list_screens(&self) -> DesktopResult<Vec<crate::types::ScreenInfo>> {
                Ok(vec![])
            }
            fn virtual_screen(&self) -> DesktopResult<Rect> {
                Ok(Rect::new(0, 0, 1, 1))
            }
            fn capture_region(&self, _: Rect) -> DesktopResult<image::RgbaImage> {
                Err(DesktopError::ScreenshotFailed("n/a".into()))
            }
            fn capture_window(&self, _: &str) -> DesktopResult<(image::RgbaImage, Rect)> {
                Err(DesktopError::ScreenshotFailed("n/a".into()))
            }
            fn mouse_position(&self) -> DesktopResult<(i32, i32)> {
                Ok((0, 0))
            }
            fn move_mouse(&self, _: i32, _: i32) -> DesktopResult<()> {
                Ok(())
            }
            fn mouse_button(&self, _: MouseButton, _: bool) -> DesktopResult<()> {
                Ok(())
            }
            fn scroll(&self, _: crate::types::ScrollDirection, _: i32) -> DesktopResult<()> {
                Ok(())
            }
            fn key(&self, _: Key, _: bool) -> DesktopResult<()> {
                Ok(())
            }
            fn type_text(&self, _: &str, _: u64) -> DesktopResult<crate::types::TypeReport> {
                Ok(Default::default())
            }
        }

        let created = Arc::new(AtomicUsize::new(0));
        let c2 = created.clone();
        let dir = tempfile::tempdir().unwrap();
        let server = DesktopControlServer::with_factory(
            OutputConfig {
                dir: dir.path().to_path_buf(),
                host_dir: None,
            },
            Arc::new(move || {
                c2.fetch_add(1, Ordering::SeqCst);
                Ok(Arc::new(Flaky) as SharedBackend)
            }),
        );
        let tools = server.tools();
        let list = tools.iter().find(|t| t.name() == "list_windows").unwrap();
        let r = list.execute(json!({})).await.unwrap();
        assert!(r.is_error);
        let r = list.execute(json!({})).await.unwrap();
        assert!(r.is_error);
        assert_eq!(
            created.load(Ordering::SeqCst),
            2,
            "backend should be recreated"
        );
    }
}
