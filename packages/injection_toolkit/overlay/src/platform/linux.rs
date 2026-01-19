//! Linux-specific overlay functionality (X11)

use crate::{OverlayError, Result};
use winit::raw_window_handle::{
    HasDisplayHandle, HasWindowHandle, RawDisplayHandle, RawWindowHandle,
};

/// Get the X11 display pointer from a window
fn get_x11_display(window: &winit::window::Window) -> Result<*mut x11::xlib::Display> {
    let display_handle = window
        .display_handle()
        .map_err(|e| OverlayError::WindowCreation(e.to_string()))?;

    match display_handle.as_raw() {
        RawDisplayHandle::Xlib(xlib_display) => xlib_display
            .display
            .map(|d| d.as_ptr() as *mut x11::xlib::Display)
            .ok_or_else(|| OverlayError::WindowCreation("No X11 display".into())),
        _ => Err(OverlayError::WindowCreation("Not an Xlib display".into())),
    }
}

/// Set click-through mode using X11 shape extension
///
/// On X11, we use the SHAPE extension to set an empty input region,
/// making all input pass through to the window below.
///
/// NOTE: This currently requires x11rb with the "shape" feature for proper
/// shape extension support. The x11 crate doesn't include libXext bindings.
/// This is a stub implementation that logs a warning.
pub fn set_click_through_impl(window: &winit::window::Window, enabled: bool) -> Result<()> {
    let handle = window
        .window_handle()
        .map_err(|e| OverlayError::WindowCreation(e.to_string()))?;

    match handle.as_raw() {
        RawWindowHandle::Xlib(_xlib_handle) => {
            // TODO: Implement proper click-through using x11rb with shape extension
            // The x11 crate doesn't include libXext/shape extension bindings.
            // For now, we log a warning about this limitation.
            tracing::warn!(
                "Click-through {} requested but X11 shape extension not available. \
                 Add x11rb with 'shape' feature for full support.",
                if enabled { "enable" } else { "disable" }
            );
            Ok(())
        }
        RawWindowHandle::Xcb(_) => {
            // XCB support could be added here
            Err(OverlayError::UnsupportedPlatform(
                "XCB not yet supported, use Xlib".into(),
            ))
        }
        RawWindowHandle::Wayland(_) => {
            // Wayland doesn't support click-through in the same way
            // Layer-shell protocol would be needed
            Err(OverlayError::UnsupportedPlatform(
                "Wayland click-through requires layer-shell protocol".into(),
            ))
        }
        _ => Err(OverlayError::UnsupportedPlatform(
            "Unknown window handle type".into(),
        )),
    }
}

/// Set always-on-top using _NET_WM_STATE
pub fn set_always_on_top_impl(window: &winit::window::Window, enabled: bool) -> Result<()> {
    let handle = window
        .window_handle()
        .map_err(|e| OverlayError::WindowCreation(e.to_string()))?;

    match handle.as_raw() {
        RawWindowHandle::Xlib(xlib_handle) => {
            unsafe {
                let display = get_x11_display(window)?;
                let window_id = xlib_handle.window as x11::xlib::Window;

                // Get atoms
                let wm_state = x11::xlib::XInternAtom(
                    display,
                    b"_NET_WM_STATE\0".as_ptr() as *const _,
                    x11::xlib::False,
                );
                let wm_state_above = x11::xlib::XInternAtom(
                    display,
                    b"_NET_WM_STATE_ABOVE\0".as_ptr() as *const _,
                    x11::xlib::False,
                );

                // Send client message to window manager
                let mut event: x11::xlib::XClientMessageEvent = std::mem::zeroed();
                event.type_ = x11::xlib::ClientMessage;
                event.window = window_id;
                event.message_type = wm_state;
                event.format = 32;
                event.data.set_long(0, if enabled { 1 } else { 0 }); // _NET_WM_STATE_ADD or _REMOVE
                event.data.set_long(1, wm_state_above as i64);
                event.data.set_long(2, 0);

                let root = x11::xlib::XDefaultRootWindow(display);
                x11::xlib::XSendEvent(
                    display,
                    root,
                    x11::xlib::False,
                    x11::xlib::SubstructureRedirectMask | x11::xlib::SubstructureNotifyMask,
                    &mut event as *mut _ as *mut x11::xlib::XEvent,
                );

                x11::xlib::XFlush(display);
            }
            Ok(())
        }
        _ => Err(OverlayError::UnsupportedPlatform(
            "Only Xlib supported for always-on-top".into(),
        )),
    }
}

/// Set window type hint for overlay behavior
pub fn set_transparent_impl(window: &winit::window::Window) -> Result<()> {
    let handle = window
        .window_handle()
        .map_err(|e| OverlayError::WindowCreation(e.to_string()))?;

    match handle.as_raw() {
        RawWindowHandle::Xlib(xlib_handle) => {
            unsafe {
                let display = get_x11_display(window)?;
                let window_id = xlib_handle.window as x11::xlib::Window;

                // Set window type to dock/overlay
                let wm_window_type = x11::xlib::XInternAtom(
                    display,
                    b"_NET_WM_WINDOW_TYPE\0".as_ptr() as *const _,
                    x11::xlib::False,
                );
                let wm_window_type_dock = x11::xlib::XInternAtom(
                    display,
                    b"_NET_WM_WINDOW_TYPE_DOCK\0".as_ptr() as *const _,
                    x11::xlib::False,
                );

                x11::xlib::XChangeProperty(
                    display,
                    window_id,
                    wm_window_type,
                    x11::xlib::XA_ATOM,
                    32,
                    x11::xlib::PropModeReplace,
                    &wm_window_type_dock as *const _ as *const _,
                    1,
                );

                x11::xlib::XFlush(display);
            }
            Ok(())
        }
        _ => Ok(()), // Ignore for other platforms
    }
}
