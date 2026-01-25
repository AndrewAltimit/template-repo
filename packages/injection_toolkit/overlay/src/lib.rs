//! # ITK Overlay
//!
//! Cross-platform overlay window for the Injection Toolkit.
//!
//! This library provides:
//! - Transparent, always-on-top overlay window
//! - Click-through mode (input passes to underlying window)
//! - Interactive mode (captures input for UI)
//! - wgpu-based rendering
//!
//! ## Platform Support
//!
//! - **Windows**: Uses `WS_EX_TRANSPARENT` and `WS_EX_NOACTIVATE` for click-through
//! - **Linux**: Uses X11 hints (Wayland support planned)

pub mod platform;
pub mod render;
pub mod video;

use itk_protocol::ScreenRect;
use thiserror::Error;

/// Overlay errors
#[derive(Error, Debug)]
pub enum OverlayError {
    #[error("failed to create window: {0}")]
    WindowCreation(String),

    #[error("failed to initialize renderer: {0}")]
    RendererInit(String),

    #[error("platform not supported: {0}")]
    UnsupportedPlatform(String),

    #[error("lost GPU device")]
    DeviceLost,

    #[error("IPC error: {0}")]
    Ipc(#[from] itk_ipc::IpcError),
}

/// Result type for overlay operations
pub type Result<T> = std::result::Result<T, OverlayError>;

/// Overlay configuration
#[derive(Debug, Clone)]
pub struct OverlayConfig {
    /// Window title (usually not visible)
    pub title: String,

    /// Initial width
    pub width: u32,

    /// Initial height
    pub height: u32,

    /// Start in click-through mode
    pub click_through: bool,

    /// Daemon IPC channel name
    pub daemon_channel: String,
}

impl Default for OverlayConfig {
    fn default() -> Self {
        Self {
            title: "ITK Overlay".to_string(),
            width: 1920,
            height: 1080,
            click_through: true,
            daemon_channel: "itk_client".to_string(),
        }
    }
}

/// Overlay state
#[derive(Debug)]
pub struct OverlayState {
    /// Current screen rect for rendering
    pub screen_rect: Option<ScreenRect>,

    /// Whether in click-through mode
    pub click_through: bool,

    /// Whether overlay should be visible
    pub visible: bool,
}

impl Default for OverlayState {
    fn default() -> Self {
        Self {
            screen_rect: None,
            click_through: true,
            visible: true,
        }
    }
}

/// Toggle key for switching between click-through and interactive mode
pub const TOGGLE_KEY: &str = "F9";
