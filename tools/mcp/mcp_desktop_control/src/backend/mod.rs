//! Platform-specific desktop control backends.
//!
//! A backend exposes small, synchronous primitives (list windows, press a
//! key, capture a rectangle, ...). Composite behaviour such as multi-clicks,
//! drags, chords and screenshot post-processing lives in
//! [`crate::actions`] so it is shared by every platform and unit-tested
//! against [`mock::MockBackend`].
//!
//! Backends are blocking; the server always calls them from
//! `tokio::task::spawn_blocking` with a timeout.

#[cfg(target_os = "linux")]
mod linux;
#[cfg(test)]
pub mod mock;
#[cfg(windows)]
mod win32;

use std::sync::Arc;

use image::RgbaImage;
use thiserror::Error;

use crate::keys::Key;
use crate::types::{MouseButton, Rect, ScreenInfo, ScrollDirection, TypeReport, WindowInfo};

/// Errors that can occur during desktop operations.
#[derive(Error, Debug)]
pub enum DesktopError {
    /// No usable display / desktop session.
    #[error("Desktop control not available: {0}")]
    NotAvailable(String),

    /// The connection to the display server was lost. The server drops the
    /// backend and reconnects on the next call.
    #[cfg_attr(not(target_os = "linux"), allow(dead_code))]
    #[error("Display connection lost: {0}")]
    Disconnected(String),

    /// The window id does not name an existing window.
    #[error("Window not found: {0}")]
    WindowNotFound(String),

    /// The requested screen index does not exist.
    #[error("Screen not found: {0}")]
    ScreenNotFound(String),

    /// Caller-supplied input that cannot be acted upon (unknown key, ...).
    #[error("{0}")]
    InvalidInput(String),

    /// The operation is not possible in this environment (e.g. maximizing
    /// without a window manager).
    #[cfg_attr(not(target_os = "linux"), allow(dead_code))]
    #[error("Not supported: {0}")]
    Unsupported(String),

    /// Screen capture failed.
    #[error("Screenshot failed: {0}")]
    ScreenshotFailed(String),

    /// Any other platform failure.
    #[error("Operation failed: {0}")]
    OperationFailed(String),
}

/// Result type for desktop operations.
pub type DesktopResult<T> = Result<T, DesktopError>;

/// Shared, thread-safe backend handle.
pub type SharedBackend = Arc<dyn DesktopBackend>;

/// Platform primitives. All coordinates are absolute desktop pixels.
pub trait DesktopBackend: Send + Sync {
    /// Short platform identifier (`x11`, `windows`, ...).
    fn platform_name(&self) -> &'static str;

    /// Extra platform diagnostics for `desktop_status`.
    fn diagnostics(&self) -> serde_json::Value {
        serde_json::Value::Null
    }

    // -- Windows ----------------------------------------------------------

    /// All top-level application windows (unfiltered).
    fn list_windows(&self) -> DesktopResult<Vec<WindowInfo>>;
    /// The focused window, if any.
    fn get_active_window(&self) -> DesktopResult<Option<WindowInfo>>;
    /// Raise and focus a window.
    fn focus_window(&self, id: &str) -> DesktopResult<()>;
    /// Move a window's top-left corner.
    fn move_window(&self, id: &str, x: i32, y: i32) -> DesktopResult<()>;
    /// Resize a window.
    fn resize_window(&self, id: &str, width: u32, height: u32) -> DesktopResult<()>;
    /// Minimize (iconify) a window.
    fn minimize_window(&self, id: &str) -> DesktopResult<()>;
    /// Maximize a window.
    fn maximize_window(&self, id: &str) -> DesktopResult<()>;
    /// Restore a minimized or maximized window.
    fn restore_window(&self, id: &str) -> DesktopResult<()>;
    /// Ask a window to close (the application may prompt to save).
    fn close_window(&self, id: &str) -> DesktopResult<()>;

    // -- Screens ----------------------------------------------------------

    /// Physical monitors, ids sequential from 0.
    fn list_screens(&self) -> DesktopResult<Vec<ScreenInfo>>;
    /// Bounding box of all monitors.
    fn virtual_screen(&self) -> DesktopResult<Rect>;

    // -- Capture ----------------------------------------------------------

    /// Capture a rectangle that lies within [`Self::virtual_screen`].
    fn capture_region(&self, rect: Rect) -> DesktopResult<RgbaImage>;
    /// Capture a window; returns the image and the rectangle it covers.
    fn capture_window(&self, id: &str) -> DesktopResult<(RgbaImage, Rect)>;

    // -- Input ------------------------------------------------------------

    /// Current pointer position.
    fn mouse_position(&self) -> DesktopResult<(i32, i32)>;
    /// Move the pointer to an absolute position.
    fn move_mouse(&self, x: i32, y: i32) -> DesktopResult<()>;
    /// Press (`down = true`) or release a mouse button at the pointer.
    fn mouse_button(&self, button: MouseButton, down: bool) -> DesktopResult<()>;
    /// Scroll by `amount` notches (positive = down / right).
    fn scroll(&self, direction: ScrollDirection, amount: i32) -> DesktopResult<()>;
    /// Press (`down = true`) or release a single key. Character keys that
    /// need Shift on the active layout get Shift added automatically.
    fn key(&self, key: Key, down: bool) -> DesktopResult<()>;
    /// Type literal text, one character every `interval_ms`.
    fn type_text(&self, text: &str, interval_ms: u64) -> DesktopResult<TypeReport>;
}

/// Create the backend for the current platform.
pub fn create_backend() -> DesktopResult<SharedBackend> {
    #[cfg(target_os = "linux")]
    {
        linux::X11Backend::connect().map(|b| Arc::new(b) as SharedBackend)
    }

    #[cfg(windows)]
    {
        win32::WindowsBackend::new().map(|b| Arc::new(b) as SharedBackend)
    }

    #[cfg(not(any(target_os = "linux", windows)))]
    {
        Err(DesktopError::NotAvailable(format!(
            "no desktop backend for platform '{}' (supported: Linux/X11, Windows)",
            std::env::consts::OS
        )))
    }
}
