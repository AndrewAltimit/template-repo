//! Platform-specific overlay functionality

cfg_if::cfg_if! {
    if #[cfg(windows)] {
        mod windows;
        pub use windows::*;
    } else if #[cfg(target_os = "linux")] {
        mod linux;
        pub use linux::*;
    } else {
        compile_error!("Unsupported platform for overlay");
    }
}

/// Set click-through mode for a window
///
/// When enabled, mouse input passes through the window to the one behind it.
pub fn set_click_through(window: &winit::window::Window, enabled: bool) -> crate::Result<()> {
    set_click_through_impl(window, enabled)
}

/// Set always-on-top for a window
pub fn set_always_on_top(window: &winit::window::Window, enabled: bool) -> crate::Result<()> {
    set_always_on_top_impl(window, enabled)
}

/// Make window transparent (for compositor)
pub fn set_transparent(window: &winit::window::Window) -> crate::Result<()> {
    set_transparent_impl(window)
}
