//! Platform-specific desktop control backends.

mod linux;

pub use linux::LinuxBackend;

use thiserror::Error;

use crate::types::{KeyModifier, MouseButton, ScreenInfo, ScrollDirection, WindowInfo};

/// Errors that can occur during desktop operations
#[derive(Error, Debug)]
pub enum DesktopError {
    #[error("Desktop control not available: {0}")]
    NotAvailable(String),

    #[error("Window not found: {0}")]
    WindowNotFound(String),

    #[error("Screen not found: {0}")]
    ScreenNotFound(String),

    #[error("Screenshot failed: {0}")]
    ScreenshotFailed(String),

    #[error("Operation failed: {0}")]
    OperationFailed(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

/// Result type for desktop operations
pub type DesktopResult<T> = Result<T, DesktopError>;

/// Trait for platform-specific desktop control backends
pub trait DesktopBackend: Send + Sync {
    /// Get the platform name
    fn platform_name(&self) -> &str;

    /// Check if the backend is available
    fn is_available(&self) -> bool;

    // Window management
    fn list_windows(
        &self,
        title_filter: Option<&str>,
        visible_only: bool,
    ) -> DesktopResult<Vec<WindowInfo>>;
    fn get_active_window(&self) -> DesktopResult<Option<WindowInfo>>;
    fn focus_window(&self, window_id: &str) -> DesktopResult<bool>;
    fn move_window(&self, window_id: &str, x: i32, y: i32) -> DesktopResult<bool>;
    fn resize_window(&self, window_id: &str, width: u32, height: u32) -> DesktopResult<bool>;
    fn minimize_window(&self, window_id: &str) -> DesktopResult<bool>;
    fn maximize_window(&self, window_id: &str) -> DesktopResult<bool>;
    fn restore_window(&self, window_id: &str) -> DesktopResult<bool>;
    fn close_window(&self, window_id: &str) -> DesktopResult<bool>;

    // Screen information
    fn list_screens(&self) -> DesktopResult<Vec<ScreenInfo>>;
    fn get_screen_size(&self) -> DesktopResult<(u32, u32)>;

    // Screenshots
    fn screenshot_screen(&self, screen_id: Option<u32>) -> DesktopResult<Vec<u8>>;
    fn screenshot_window(&self, window_id: &str) -> DesktopResult<Vec<u8>>;
    fn screenshot_region(&self, x: i32, y: i32, width: u32, height: u32) -> DesktopResult<Vec<u8>>;

    // Mouse control
    fn get_mouse_position(&self) -> DesktopResult<(i32, i32)>;
    fn move_mouse(&self, x: i32, y: i32, relative: bool) -> DesktopResult<bool>;
    fn click_mouse(
        &self,
        button: MouseButton,
        x: Option<i32>,
        y: Option<i32>,
        clicks: u32,
    ) -> DesktopResult<bool>;
    fn drag_mouse(
        &self,
        start_x: i32,
        start_y: i32,
        end_x: i32,
        end_y: i32,
        button: MouseButton,
        duration_ms: u64,
    ) -> DesktopResult<bool>;
    fn scroll_mouse(
        &self,
        amount: i32,
        direction: ScrollDirection,
        x: Option<i32>,
        y: Option<i32>,
    ) -> DesktopResult<bool>;

    // Keyboard control
    fn type_text(&self, text: &str, interval_ms: u64) -> DesktopResult<bool>;
    fn send_key(&self, key: &str, modifiers: &[KeyModifier]) -> DesktopResult<bool>;
    fn send_hotkey(&self, keys: &[String]) -> DesktopResult<bool>;
}

/// Create the appropriate backend for the current platform
pub fn create_backend() -> DesktopResult<Box<dyn DesktopBackend>> {
    #[cfg(target_os = "linux")]
    {
        LinuxBackend::new().map(|b| Box::new(b) as Box<dyn DesktopBackend>)
    }

    #[cfg(not(target_os = "linux"))]
    {
        Err(DesktopError::NotAvailable(
            "Unsupported platform".to_string(),
        ))
    }
}
