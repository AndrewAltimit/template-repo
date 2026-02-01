//! MCP server implementation for desktop control.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::backend::{DesktopBackend, DesktopError, create_backend};
use crate::types::{KeyModifier, MouseButton, ScrollDirection};

/// Desktop control MCP server
pub struct DesktopControlServer {
    backend: Arc<RwLock<Option<Box<dyn DesktopBackend>>>>,
    initialized: Arc<RwLock<bool>>,
    screenshots_dir: Arc<RwLock<String>>,
}

impl DesktopControlServer {
    /// Create a new desktop control server
    pub fn new() -> Self {
        // Default screenshots directory
        let screenshots_dir = dirs::home_dir()
            .map(|p| p.join(".local/share/mcp-desktop-control/screenshots"))
            .unwrap_or_else(|| std::path::PathBuf::from("/tmp/mcp-desktop-control/screenshots"))
            .to_string_lossy()
            .to_string();

        Self {
            backend: Arc::new(RwLock::new(None)),
            initialized: Arc::new(RwLock::new(false)),
            screenshots_dir: Arc::new(RwLock::new(screenshots_dir)),
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            // Status
            Arc::new(DesktopStatusTool {
                server: self.clone_refs(),
            }),
            // Window management
            Arc::new(ListWindowsTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetActiveWindowTool {
                server: self.clone_refs(),
            }),
            Arc::new(FocusWindowTool {
                server: self.clone_refs(),
            }),
            Arc::new(MoveWindowTool {
                server: self.clone_refs(),
            }),
            Arc::new(ResizeWindowTool {
                server: self.clone_refs(),
            }),
            Arc::new(MinimizeWindowTool {
                server: self.clone_refs(),
            }),
            Arc::new(MaximizeWindowTool {
                server: self.clone_refs(),
            }),
            Arc::new(RestoreWindowTool {
                server: self.clone_refs(),
            }),
            Arc::new(CloseWindowTool {
                server: self.clone_refs(),
            }),
            // Screen
            Arc::new(ListScreensTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetScreenSizeTool {
                server: self.clone_refs(),
            }),
            // Screenshots
            Arc::new(ScreenshotScreenTool {
                server: self.clone_refs(),
            }),
            Arc::new(ScreenshotWindowTool {
                server: self.clone_refs(),
            }),
            Arc::new(ScreenshotRegionTool {
                server: self.clone_refs(),
            }),
            // Mouse
            Arc::new(GetMousePositionTool {
                server: self.clone_refs(),
            }),
            Arc::new(MoveMouseTool {
                server: self.clone_refs(),
            }),
            Arc::new(ClickMouseTool {
                server: self.clone_refs(),
            }),
            Arc::new(DragMouseTool {
                server: self.clone_refs(),
            }),
            Arc::new(ScrollMouseTool {
                server: self.clone_refs(),
            }),
            // Keyboard
            Arc::new(TypeTextTool {
                server: self.clone_refs(),
            }),
            Arc::new(SendKeyTool {
                server: self.clone_refs(),
            }),
            Arc::new(SendHotkeyTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone the Arc references for tools
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            backend: self.backend.clone(),
            initialized: self.initialized.clone(),
            screenshots_dir: self.screenshots_dir.clone(),
        }
    }
}

impl Default for DesktopControlServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Shared references for tools
#[derive(Clone)]
struct ServerRefs {
    backend: Arc<RwLock<Option<Box<dyn DesktopBackend>>>>,
    initialized: Arc<RwLock<bool>>,
    screenshots_dir: Arc<RwLock<String>>,
}

impl ServerRefs {
    async fn ensure_initialized(&self) -> Result<()> {
        let mut initialized = self.initialized.write().await;
        if *initialized {
            return Ok(());
        }

        info!("Initializing desktop control backend...");

        let backend = create_backend()
            .map_err(|e| MCPError::Internal(format!("Failed to create backend: {}", e)))?;

        info!("Backend created: {}", backend.platform_name());

        // Ensure screenshots directory exists
        let screenshots_dir = self.screenshots_dir.read().await;
        std::fs::create_dir_all(screenshots_dir.as_str())
            .map_err(|e| MCPError::Internal(format!("Failed to create screenshots dir: {}", e)))?;

        let mut backend_lock = self.backend.write().await;
        *backend_lock = Some(backend);
        *initialized = true;

        info!("Desktop control backend initialized");
        Ok(())
    }

    async fn with_backend<F, R>(&self, f: F) -> Result<R>
    where
        F: FnOnce(&dyn DesktopBackend) -> std::result::Result<R, DesktopError>,
    {
        self.ensure_initialized().await?;
        let backend_lock = self.backend.read().await;
        let backend = backend_lock
            .as_ref()
            .ok_or_else(|| MCPError::Internal("Backend not initialized".to_string()))?;
        f(backend.as_ref()).map_err(|e| MCPError::Internal(e.to_string()))
    }
}

// ============================================================================
// Tool: desktop_status
// ============================================================================

struct DesktopStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for DesktopStatusTool {
    fn name(&self) -> &str {
        "desktop_status"
    }

    fn description(&self) -> &str {
        r#"Get desktop control server status.

Returns information about the backend, platform, and availability."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let initialized = *self.server.initialized.read().await;
        let screenshots_dir = self.server.screenshots_dir.read().await.clone();

        let mut response = json!({
            "server": "desktop-control",
            "version": "1.0.0",
            "initialized": initialized,
            "screenshots_dir": screenshots_dir
        });

        if initialized {
            let backend = self.server.backend.read().await;
            if let Some(ref b) = *backend {
                response["platform"] = json!(b.platform_name());
                response["available"] = json!(b.is_available());
            }
        }

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: list_windows
// ============================================================================

struct ListWindowsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListWindowsTool {
    fn name(&self) -> &str {
        "list_windows"
    }

    fn description(&self) -> &str {
        r#"List all windows on the desktop.

Returns window ID, title, position, size, and state for each window."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "title_filter": {
                    "type": "string",
                    "description": "Filter windows by title (case-insensitive substring match)"
                },
                "visible_only": {
                    "type": "boolean",
                    "description": "Only return visible windows (default: true)",
                    "default": true
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let title_filter = args.get("title_filter").and_then(|v| v.as_str());
        let visible_only = args
            .get("visible_only")
            .and_then(|v| v.as_bool())
            .unwrap_or(true);

        let windows = self
            .server
            .with_backend(|b| b.list_windows(title_filter, visible_only))
            .await?;

        let response = json!({
            "success": true,
            "count": windows.len(),
            "windows": windows
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_active_window
// ============================================================================

struct GetActiveWindowTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetActiveWindowTool {
    fn name(&self) -> &str {
        "get_active_window"
    }

    fn description(&self) -> &str {
        r#"Get the currently active/focused window."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let window = self.server.with_backend(|b| b.get_active_window()).await?;

        let response = match window {
            Some(w) => json!({
                "success": true,
                "window": w
            }),
            None => json!({
                "success": true,
                "window": null,
                "message": "No active window"
            }),
        };

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: focus_window
// ============================================================================

struct FocusWindowTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for FocusWindowTool {
    fn name(&self) -> &str {
        "focus_window"
    }

    fn description(&self) -> &str {
        r#"Focus a window by its ID."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "window_id": {
                    "type": "string",
                    "description": "Window identifier"
                }
            },
            "required": ["window_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let window_id = args
            .get("window_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'window_id' parameter".to_string())
            })?;

        let success = self
            .server
            .with_backend(|b| b.focus_window(window_id))
            .await?;

        let response = json!({
            "success": success,
            "window_id": window_id
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: move_window
// ============================================================================

struct MoveWindowTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for MoveWindowTool {
    fn name(&self) -> &str {
        "move_window"
    }

    fn description(&self) -> &str {
        r#"Move a window to a new position."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "window_id": {
                    "type": "string",
                    "description": "Window identifier"
                },
                "x": {
                    "type": "integer",
                    "description": "New X position"
                },
                "y": {
                    "type": "integer",
                    "description": "New Y position"
                }
            },
            "required": ["window_id", "x", "y"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let window_id = args
            .get("window_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'window_id' parameter".to_string())
            })?;

        let x = args
            .get("x")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'x' parameter".to_string()))?
            as i32;

        let y = args
            .get("y")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'y' parameter".to_string()))?
            as i32;

        let success = self
            .server
            .with_backend(|b| b.move_window(window_id, x, y))
            .await?;

        let response = json!({
            "success": success,
            "window_id": window_id,
            "x": x,
            "y": y
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: resize_window
// ============================================================================

struct ResizeWindowTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ResizeWindowTool {
    fn name(&self) -> &str {
        "resize_window"
    }

    fn description(&self) -> &str {
        r#"Resize a window."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "window_id": {
                    "type": "string",
                    "description": "Window identifier"
                },
                "width": {
                    "type": "integer",
                    "description": "New width in pixels"
                },
                "height": {
                    "type": "integer",
                    "description": "New height in pixels"
                }
            },
            "required": ["window_id", "width", "height"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let window_id = args
            .get("window_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'window_id' parameter".to_string())
            })?;

        let width =
            args.get("width").and_then(|v| v.as_u64()).ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'width' parameter".to_string())
            })? as u32;

        let height =
            args.get("height").and_then(|v| v.as_u64()).ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'height' parameter".to_string())
            })? as u32;

        let success = self
            .server
            .with_backend(|b| b.resize_window(window_id, width, height))
            .await?;

        let response = json!({
            "success": success,
            "window_id": window_id,
            "width": width,
            "height": height
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: minimize_window
// ============================================================================

struct MinimizeWindowTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for MinimizeWindowTool {
    fn name(&self) -> &str {
        "minimize_window"
    }

    fn description(&self) -> &str {
        r#"Minimize a window."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "window_id": {
                    "type": "string",
                    "description": "Window identifier"
                }
            },
            "required": ["window_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let window_id = args
            .get("window_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'window_id' parameter".to_string())
            })?;

        let success = self
            .server
            .with_backend(|b| b.minimize_window(window_id))
            .await?;

        let response = json!({
            "success": success,
            "window_id": window_id
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: maximize_window
// ============================================================================

struct MaximizeWindowTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for MaximizeWindowTool {
    fn name(&self) -> &str {
        "maximize_window"
    }

    fn description(&self) -> &str {
        r#"Maximize a window."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "window_id": {
                    "type": "string",
                    "description": "Window identifier"
                }
            },
            "required": ["window_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let window_id = args
            .get("window_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'window_id' parameter".to_string())
            })?;

        let success = self
            .server
            .with_backend(|b| b.maximize_window(window_id))
            .await?;

        let response = json!({
            "success": success,
            "window_id": window_id
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: restore_window
// ============================================================================

struct RestoreWindowTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for RestoreWindowTool {
    fn name(&self) -> &str {
        "restore_window"
    }

    fn description(&self) -> &str {
        r#"Restore a minimized or maximized window to normal state."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "window_id": {
                    "type": "string",
                    "description": "Window identifier"
                }
            },
            "required": ["window_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let window_id = args
            .get("window_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'window_id' parameter".to_string())
            })?;

        let success = self
            .server
            .with_backend(|b| b.restore_window(window_id))
            .await?;

        let response = json!({
            "success": success,
            "window_id": window_id
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: close_window
// ============================================================================

struct CloseWindowTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for CloseWindowTool {
    fn name(&self) -> &str {
        "close_window"
    }

    fn description(&self) -> &str {
        r#"Close a window.

Warning: This will close the window without saving any unsaved work."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "window_id": {
                    "type": "string",
                    "description": "Window identifier"
                }
            },
            "required": ["window_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let window_id = args
            .get("window_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'window_id' parameter".to_string())
            })?;

        let success = self
            .server
            .with_backend(|b| b.close_window(window_id))
            .await?;

        let response = json!({
            "success": success,
            "window_id": window_id
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: list_screens
// ============================================================================

struct ListScreensTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListScreensTool {
    fn name(&self) -> &str {
        "list_screens"
    }

    fn description(&self) -> &str {
        r#"List all screens/monitors.

Returns screen ID, name, position, resolution, and primary status."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let screens = self.server.with_backend(|b| b.list_screens()).await?;

        let response = json!({
            "success": true,
            "count": screens.len(),
            "screens": screens
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_screen_size
// ============================================================================

struct GetScreenSizeTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetScreenSizeTool {
    fn name(&self) -> &str {
        "get_screen_size"
    }

    fn description(&self) -> &str {
        r#"Get the primary screen resolution."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let (width, height) = self.server.with_backend(|b| b.get_screen_size()).await?;

        let response = json!({
            "success": true,
            "width": width,
            "height": height
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: screenshot_screen
// ============================================================================

struct ScreenshotScreenTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ScreenshotScreenTool {
    fn name(&self) -> &str {
        "screenshot_screen"
    }

    fn description(&self) -> &str {
        r#"Capture a screenshot of the entire screen or a specific monitor."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "screen_id": {
                    "type": "integer",
                    "description": "Screen ID to capture (default: primary screen)"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output file path (default: auto-generated in screenshots dir)"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let screen_id = args
            .get("screen_id")
            .and_then(|v| v.as_u64())
            .map(|v| v as u32);

        let png_data = self
            .server
            .with_backend(|b| b.screenshot_screen(screen_id))
            .await?;

        let output_path = if let Some(path) = args.get("output_path").and_then(|v| v.as_str()) {
            path.to_string()
        } else {
            let screenshots_dir = self.server.screenshots_dir.read().await;
            let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
            format!("{}/screen_{}.png", screenshots_dir, timestamp)
        };

        std::fs::write(&output_path, &png_data)
            .map_err(|e| MCPError::Internal(format!("Failed to write screenshot: {}", e)))?;

        let response = json!({
            "success": true,
            "output_path": output_path,
            "format": "png",
            "size_bytes": png_data.len()
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: screenshot_window
// ============================================================================

struct ScreenshotWindowTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ScreenshotWindowTool {
    fn name(&self) -> &str {
        "screenshot_window"
    }

    fn description(&self) -> &str {
        r#"Capture a screenshot of a specific window."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "window_id": {
                    "type": "string",
                    "description": "Window identifier"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output file path (default: auto-generated in screenshots dir)"
                }
            },
            "required": ["window_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let window_id = args
            .get("window_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'window_id' parameter".to_string())
            })?;

        let png_data = self
            .server
            .with_backend(|b| b.screenshot_window(window_id))
            .await?;

        let output_path = if let Some(path) = args.get("output_path").and_then(|v| v.as_str()) {
            path.to_string()
        } else {
            let screenshots_dir = self.server.screenshots_dir.read().await;
            let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
            format!("{}/window_{}.png", screenshots_dir, timestamp)
        };

        std::fs::write(&output_path, &png_data)
            .map_err(|e| MCPError::Internal(format!("Failed to write screenshot: {}", e)))?;

        let response = json!({
            "success": true,
            "output_path": output_path,
            "format": "png",
            "size_bytes": png_data.len(),
            "window_id": window_id
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: screenshot_region
// ============================================================================

struct ScreenshotRegionTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ScreenshotRegionTool {
    fn name(&self) -> &str {
        "screenshot_region"
    }

    fn description(&self) -> &str {
        r#"Capture a screenshot of a specific region of the screen."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "X coordinate of the region"
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate of the region"
                },
                "width": {
                    "type": "integer",
                    "description": "Width of the region"
                },
                "height": {
                    "type": "integer",
                    "description": "Height of the region"
                },
                "output_path": {
                    "type": "string",
                    "description": "Output file path (default: auto-generated in screenshots dir)"
                }
            },
            "required": ["x", "y", "width", "height"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let x = args
            .get("x")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'x' parameter".to_string()))?
            as i32;

        let y = args
            .get("y")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'y' parameter".to_string()))?
            as i32;

        let width =
            args.get("width").and_then(|v| v.as_u64()).ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'width' parameter".to_string())
            })? as u32;

        let height =
            args.get("height").and_then(|v| v.as_u64()).ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'height' parameter".to_string())
            })? as u32;

        let png_data = self
            .server
            .with_backend(|b| b.screenshot_region(x, y, width, height))
            .await?;

        let output_path = if let Some(path) = args.get("output_path").and_then(|v| v.as_str()) {
            path.to_string()
        } else {
            let screenshots_dir = self.server.screenshots_dir.read().await;
            let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
            format!("{}/region_{}.png", screenshots_dir, timestamp)
        };

        std::fs::write(&output_path, &png_data)
            .map_err(|e| MCPError::Internal(format!("Failed to write screenshot: {}", e)))?;

        let response = json!({
            "success": true,
            "output_path": output_path,
            "format": "png",
            "size_bytes": png_data.len(),
            "region": {
                "x": x,
                "y": y,
                "width": width,
                "height": height
            }
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_mouse_position
// ============================================================================

struct GetMousePositionTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetMousePositionTool {
    fn name(&self) -> &str {
        "get_mouse_position"
    }

    fn description(&self) -> &str {
        r#"Get the current mouse cursor position."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let (x, y) = self.server.with_backend(|b| b.get_mouse_position()).await?;

        let response = json!({
            "success": true,
            "x": x,
            "y": y
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: move_mouse
// ============================================================================

struct MoveMouseTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for MoveMouseTool {
    fn name(&self) -> &str {
        "move_mouse"
    }

    fn description(&self) -> &str {
        r#"Move the mouse cursor to a position."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "X coordinate"
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate"
                },
                "relative": {
                    "type": "boolean",
                    "description": "If true, move relative to current position (default: false)",
                    "default": false
                }
            },
            "required": ["x", "y"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let x = args
            .get("x")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'x' parameter".to_string()))?
            as i32;

        let y = args
            .get("y")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'y' parameter".to_string()))?
            as i32;

        let relative = args
            .get("relative")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let success = self
            .server
            .with_backend(|b| b.move_mouse(x, y, relative))
            .await?;

        let response = json!({
            "success": success,
            "x": x,
            "y": y,
            "relative": relative
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: click_mouse
// ============================================================================

struct ClickMouseTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ClickMouseTool {
    fn name(&self) -> &str {
        "click_mouse"
    }

    fn description(&self) -> &str {
        r#"Click a mouse button.

Optionally move to a position before clicking."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "description": "Mouse button to click (default: left)",
                    "default": "left"
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate to click at (optional, uses current position if not specified)"
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate to click at (optional, uses current position if not specified)"
                },
                "clicks": {
                    "type": "integer",
                    "description": "Number of clicks (default: 1, use 2 for double-click)",
                    "default": 1
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let button_str = args
            .get("button")
            .and_then(|v| v.as_str())
            .unwrap_or("left");

        let button: MouseButton = button_str
            .parse()
            .map_err(|e: String| MCPError::InvalidParameters(e))?;

        let x = args.get("x").and_then(|v| v.as_i64()).map(|v| v as i32);
        let y = args.get("y").and_then(|v| v.as_i64()).map(|v| v as i32);
        let clicks = args.get("clicks").and_then(|v| v.as_u64()).unwrap_or(1) as u32;

        let success = self
            .server
            .with_backend(|b| b.click_mouse(button, x, y, clicks))
            .await?;

        let response = json!({
            "success": success,
            "button": button_str,
            "clicks": clicks
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: drag_mouse
// ============================================================================

struct DragMouseTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for DragMouseTool {
    fn name(&self) -> &str {
        "drag_mouse"
    }

    fn description(&self) -> &str {
        r#"Drag the mouse from one position to another."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "start_x": {
                    "type": "integer",
                    "description": "Starting X coordinate"
                },
                "start_y": {
                    "type": "integer",
                    "description": "Starting Y coordinate"
                },
                "end_x": {
                    "type": "integer",
                    "description": "Ending X coordinate"
                },
                "end_y": {
                    "type": "integer",
                    "description": "Ending Y coordinate"
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "description": "Mouse button to hold during drag (default: left)",
                    "default": "left"
                },
                "duration_ms": {
                    "type": "integer",
                    "description": "Duration of drag in milliseconds (default: 500)",
                    "default": 500
                }
            },
            "required": ["start_x", "start_y", "end_x", "end_y"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let start_x = args
            .get("start_x")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'start_x' parameter".to_string()))?
            as i32;

        let start_y = args
            .get("start_y")
            .and_then(|v| v.as_i64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'start_y' parameter".to_string()))?
            as i32;

        let end_x =
            args.get("end_x").and_then(|v| v.as_i64()).ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'end_x' parameter".to_string())
            })? as i32;

        let end_y =
            args.get("end_y").and_then(|v| v.as_i64()).ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'end_y' parameter".to_string())
            })? as i32;

        let button_str = args
            .get("button")
            .and_then(|v| v.as_str())
            .unwrap_or("left");

        let button: MouseButton = button_str
            .parse()
            .map_err(|e: String| MCPError::InvalidParameters(e))?;

        let duration_ms = args
            .get("duration_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(500);

        let success = self
            .server
            .with_backend(|b| b.drag_mouse(start_x, start_y, end_x, end_y, button, duration_ms))
            .await?;

        let response = json!({
            "success": success,
            "start": {"x": start_x, "y": start_y},
            "end": {"x": end_x, "y": end_y},
            "button": button_str,
            "duration_ms": duration_ms
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: scroll_mouse
// ============================================================================

struct ScrollMouseTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ScrollMouseTool {
    fn name(&self) -> &str {
        "scroll_mouse"
    }

    fn description(&self) -> &str {
        r#"Scroll the mouse wheel."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "amount": {
                    "type": "integer",
                    "description": "Scroll amount (positive = down/right, negative = up/left)"
                },
                "direction": {
                    "type": "string",
                    "enum": ["vertical", "horizontal"],
                    "description": "Scroll direction (default: vertical)",
                    "default": "vertical"
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate to scroll at (optional)"
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate to scroll at (optional)"
                }
            },
            "required": ["amount"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let amount =
            args.get("amount").and_then(|v| v.as_i64()).ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'amount' parameter".to_string())
            })? as i32;

        let direction_str = args
            .get("direction")
            .and_then(|v| v.as_str())
            .unwrap_or("vertical");

        let direction: ScrollDirection = direction_str
            .parse()
            .map_err(|e: String| MCPError::InvalidParameters(e))?;

        let x = args.get("x").and_then(|v| v.as_i64()).map(|v| v as i32);
        let y = args.get("y").and_then(|v| v.as_i64()).map(|v| v as i32);

        let success = self
            .server
            .with_backend(|b| b.scroll_mouse(amount, direction, x, y))
            .await?;

        let response = json!({
            "success": success,
            "amount": amount,
            "direction": direction_str
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: type_text
// ============================================================================

struct TypeTextTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for TypeTextTool {
    fn name(&self) -> &str {
        "type_text"
    }

    fn description(&self) -> &str {
        r#"Type text using keyboard simulation.

Simulates keyboard input to type the specified text."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type"
                },
                "interval_ms": {
                    "type": "integer",
                    "description": "Interval between keystrokes in milliseconds (default: 50)",
                    "default": 50
                }
            },
            "required": ["text"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let text = args
            .get("text")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'text' parameter".to_string()))?;

        let interval_ms = args
            .get("interval_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(50);

        let success = self
            .server
            .with_backend(|b| b.type_text(text, interval_ms))
            .await?;

        let response = json!({
            "success": success,
            "text_length": text.len()
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: send_key
// ============================================================================

struct SendKeyTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SendKeyTool {
    fn name(&self) -> &str {
        "send_key"
    }

    fn description(&self) -> &str {
        r#"Send a single key with optional modifiers.

Examples:
- send_key("Return")
- send_key("a", ["ctrl"]) for Ctrl+A
- send_key("s", ["ctrl", "shift"]) for Ctrl+Shift+S"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key to send (e.g., 'a', 'Return', 'Escape', 'Tab')"
                },
                "modifiers": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["ctrl", "alt", "shift", "win", "super"]
                    },
                    "description": "Modifier keys to hold"
                }
            },
            "required": ["key"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let key = args
            .get("key")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'key' parameter".to_string()))?;

        let modifiers: Vec<KeyModifier> = args
            .get("modifiers")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str())
                    .filter_map(|s| s.parse().ok())
                    .collect()
            })
            .unwrap_or_default();

        let success = self
            .server
            .with_backend(|b| b.send_key(key, &modifiers))
            .await?;

        let response = json!({
            "success": success,
            "key": key,
            "modifiers": modifiers.iter().map(|m| format!("{:?}", m).to_lowercase()).collect::<Vec<_>>()
        });

        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: send_hotkey
// ============================================================================

struct SendHotkeyTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for SendHotkeyTool {
    fn name(&self) -> &str {
        "send_hotkey"
    }

    fn description(&self) -> &str {
        r#"Send a hotkey combination.

Examples:
- send_hotkey(["ctrl", "c"]) for copy
- send_hotkey(["ctrl", "alt", "delete"])
- send_hotkey(["super", "l"]) for lock screen"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keys to press together (e.g., ['ctrl', 'c'])"
                }
            },
            "required": ["keys"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let keys: Vec<String> = args
            .get("keys")
            .and_then(|v| v.as_array())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'keys' parameter".to_string()))?
            .iter()
            .filter_map(|v| v.as_str().map(String::from))
            .collect();

        if keys.is_empty() {
            return Err(MCPError::InvalidParameters(
                "'keys' array is empty".to_string(),
            ));
        }

        let success = self.server.with_backend(|b| b.send_hotkey(&keys)).await?;

        let response = json!({
            "success": success,
            "keys": keys
        });

        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = DesktopControlServer::new();
        let tools = server.tools();
        assert_eq!(tools.len(), 23);
    }

    #[test]
    fn test_tool_names() {
        let server = DesktopControlServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"desktop_status"));
        assert!(names.contains(&"list_windows"));
        assert!(names.contains(&"get_active_window"));
        assert!(names.contains(&"focus_window"));
        assert!(names.contains(&"move_window"));
        assert!(names.contains(&"resize_window"));
        assert!(names.contains(&"minimize_window"));
        assert!(names.contains(&"maximize_window"));
        assert!(names.contains(&"restore_window"));
        assert!(names.contains(&"close_window"));
        assert!(names.contains(&"list_screens"));
        assert!(names.contains(&"get_screen_size"));
        assert!(names.contains(&"screenshot_screen"));
        assert!(names.contains(&"screenshot_window"));
        assert!(names.contains(&"screenshot_region"));
        assert!(names.contains(&"get_mouse_position"));
        assert!(names.contains(&"move_mouse"));
        assert!(names.contains(&"click_mouse"));
        assert!(names.contains(&"drag_mouse"));
        assert!(names.contains(&"scroll_mouse"));
        assert!(names.contains(&"type_text"));
        assert!(names.contains(&"send_key"));
        assert!(names.contains(&"send_hotkey"));
    }
}
