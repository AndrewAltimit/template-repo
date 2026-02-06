//! Linux-specific overlay functionality (X11)
//!
//! All X11 operations use the safe x11rb crate instead of raw xlib bindings.
//!
//! # Platform Support
//!
//! - **X11**: Full support for overlays, click-through, always-on-top
//! - **Wayland**: Not currently supported (requires layer-shell protocol)
//! - **Headless**: Not supported (requires a display server)

use crate::{OverlayError, Result};
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};
use x11rb::connection::Connection;
use x11rb::protocol::shape::{self, ConnectionExt as ShapeConnectionExt, SK};
use x11rb::protocol::xproto::{
    AtomEnum, CLIENT_MESSAGE_EVENT, ClientMessageData, ClientMessageEvent, ConnectionExt,
    EventMask, PropMode,
};
use x11rb::rust_connection::RustConnection;
use x11rb::wrapper::ConnectionExt as WrapperConnectionExt;

// Constants for _NET_WM_STATE actions
const NET_WM_STATE_REMOVE: u32 = 0;
const NET_WM_STATE_ADD: u32 = 1;

/// Check if running in a headless environment (no display available)
fn is_headless() -> bool {
    std::env::var("DISPLAY").is_err() && std::env::var("WAYLAND_DISPLAY").is_err()
}

/// Helper to create a new x11rb connection with better error messages
fn connect_x11() -> Result<(RustConnection, usize)> {
    // Check for headless environment first
    if is_headless() {
        return Err(OverlayError::UnsupportedPlatform(
            "No display server available. Overlay requires X11 or Wayland. \
             Set DISPLAY environment variable or run with a display server."
                .into(),
        ));
    }

    RustConnection::connect(None).map_err(|e| {
        // Provide more helpful error messages based on common failure modes
        let error_str = e.to_string();
        if error_str.contains("Connection refused") || error_str.contains("No such file") {
            OverlayError::WindowCreation(format!(
                "X11 connection failed: {}. Is the X server running? \
                 Check that DISPLAY is set correctly (current: {:?})",
                e,
                std::env::var("DISPLAY").ok()
            ))
        } else {
            OverlayError::WindowCreation(format!("X11 connection failed: {}", e))
        }
    })
}

/// Set click-through mode using X11 shape extension
///
/// On X11, we use the SHAPE extension to set an empty input region,
/// making all input pass through to the window below.
pub fn set_click_through_impl(window: &winit::window::Window, enabled: bool) -> Result<()> {
    let handle = window
        .window_handle()
        .map_err(|e| OverlayError::WindowCreation(e.to_string()))?;

    match handle.as_raw() {
        RawWindowHandle::Xlib(xlib_handle) => {
            let window_id = xlib_handle.window as u32;
            let (conn, _screen_num) = connect_x11()?;

            // Check if shape extension is available
            let shape_ext = conn
                .query_extension(shape::X11_EXTENSION_NAME.as_bytes())
                .map_err(|e| OverlayError::WindowCreation(format!("Shape query failed: {}", e)))?
                .reply()
                .map_err(|e| OverlayError::WindowCreation(format!("Shape reply failed: {}", e)))?;

            if !shape_ext.present {
                return Err(OverlayError::UnsupportedPlatform(
                    "X11 SHAPE extension not available".into(),
                ));
            }

            if enabled {
                // Set empty input shape - all input passes through
                // Using ShapeInput (SK::INPUT) with an empty rectangle list
                conn.shape_rectangles(
                    shape::SO::SET,
                    SK::INPUT,
                    x11rb::protocol::xproto::ClipOrdering::UNSORTED,
                    window_id,
                    0,
                    0,
                    &[], // Empty rectangle list = no input region
                )
                .map_err(|e| {
                    OverlayError::WindowCreation(format!("Shape rectangles failed: {}", e))
                })?;
            } else {
                // Reset input shape to default (full window receives input)
                conn.shape_mask(shape::SO::SET, SK::INPUT, window_id, 0, 0, x11rb::NONE)
                    .map_err(|e| {
                        OverlayError::WindowCreation(format!("Shape mask failed: {}", e))
                    })?;
            }

            conn.flush()
                .map_err(|e| OverlayError::WindowCreation(format!("X11 flush failed: {}", e)))?;

            tracing::debug!(
                "Click-through {} for window {}",
                if enabled { "enabled" } else { "disabled" },
                window_id
            );
            Ok(())
        },
        RawWindowHandle::Xcb(_) => {
            // XCB support could be added here using the same x11rb connection
            Err(OverlayError::UnsupportedPlatform(
                "XCB not yet supported, use Xlib".into(),
            ))
        },
        RawWindowHandle::Wayland(_) => {
            // Wayland doesn't support click-through in the same way
            // Layer-shell protocol would be needed
            Err(OverlayError::UnsupportedPlatform(
                "Wayland is not yet supported for overlay windows. \
                 Click-through requires the layer-shell protocol which is compositor-specific. \
                 Consider running under XWayland (set GDK_BACKEND=x11 or QT_QPA_PLATFORM=xcb) \
                 or use an X11 session."
                    .into(),
            ))
        },
        _ => Err(OverlayError::UnsupportedPlatform(
            "Unknown window handle type".into(),
        )),
    }
}

/// Set always-on-top using _NET_WM_STATE
///
/// Sends a client message to the window manager to add/remove the
/// _NET_WM_STATE_ABOVE property.
pub fn set_always_on_top_impl(window: &winit::window::Window, enabled: bool) -> Result<()> {
    let handle = window
        .window_handle()
        .map_err(|e| OverlayError::WindowCreation(e.to_string()))?;

    match handle.as_raw() {
        RawWindowHandle::Xlib(xlib_handle) => {
            let window_id = xlib_handle.window as u32;
            let (conn, screen_num) = connect_x11()?;

            // Get the root window
            let screen = &conn.setup().roots[screen_num];
            let root = screen.root;

            // Intern atoms for _NET_WM_STATE protocol
            let wm_state = conn
                .intern_atom(false, b"_NET_WM_STATE")
                .map_err(|e| OverlayError::WindowCreation(format!("Intern atom failed: {}", e)))?
                .reply()
                .map_err(|e| OverlayError::WindowCreation(format!("Atom reply failed: {}", e)))?
                .atom;

            let wm_state_above = conn
                .intern_atom(false, b"_NET_WM_STATE_ABOVE")
                .map_err(|e| OverlayError::WindowCreation(format!("Intern atom failed: {}", e)))?
                .reply()
                .map_err(|e| OverlayError::WindowCreation(format!("Atom reply failed: {}", e)))?
                .atom;

            // Build client message data:
            // data[0] = action (ADD/REMOVE)
            // data[1] = first property atom
            // data[2] = second property atom (0 if none)
            // data[3] = source indication (1 = normal application)
            let action = if enabled {
                NET_WM_STATE_ADD
            } else {
                NET_WM_STATE_REMOVE
            };
            let data = ClientMessageData::from([action, wm_state_above, 0u32, 1u32, 0u32]);

            // Create client message event
            let event = ClientMessageEvent {
                response_type: CLIENT_MESSAGE_EVENT,
                format: 32,
                sequence: 0,
                window: window_id,
                type_: wm_state,
                data,
            };

            // Send to root window with substructure masks
            conn.send_event(
                false,
                root,
                EventMask::SUBSTRUCTURE_REDIRECT | EventMask::SUBSTRUCTURE_NOTIFY,
                event,
            )
            .map_err(|e| OverlayError::WindowCreation(format!("Send event failed: {}", e)))?;

            conn.flush()
                .map_err(|e| OverlayError::WindowCreation(format!("X11 flush failed: {}", e)))?;

            tracing::debug!(
                "Always-on-top {} for window {}",
                if enabled { "enabled" } else { "disabled" },
                window_id
            );
            Ok(())
        },
        _ => Err(OverlayError::UnsupportedPlatform(
            "Only Xlib supported for always-on-top".into(),
        )),
    }
}

/// Set window type hint for overlay behavior
///
/// Sets _NET_WM_WINDOW_TYPE to DOCK, which tells the window manager
/// this is an overlay/dock window that should be treated specially.
pub fn set_transparent_impl(window: &winit::window::Window) -> Result<()> {
    let handle = window
        .window_handle()
        .map_err(|e| OverlayError::WindowCreation(e.to_string()))?;

    match handle.as_raw() {
        RawWindowHandle::Xlib(xlib_handle) => {
            let window_id = xlib_handle.window as u32;
            let (conn, _screen_num) = connect_x11()?;

            // Intern atoms for window type
            let wm_window_type = conn
                .intern_atom(false, b"_NET_WM_WINDOW_TYPE")
                .map_err(|e| OverlayError::WindowCreation(format!("Intern atom failed: {}", e)))?
                .reply()
                .map_err(|e| OverlayError::WindowCreation(format!("Atom reply failed: {}", e)))?
                .atom;

            let wm_window_type_dock = conn
                .intern_atom(false, b"_NET_WM_WINDOW_TYPE_DOCK")
                .map_err(|e| OverlayError::WindowCreation(format!("Intern atom failed: {}", e)))?
                .reply()
                .map_err(|e| OverlayError::WindowCreation(format!("Atom reply failed: {}", e)))?
                .atom;

            // Set window type property
            // Property format is 32-bit atoms
            conn.change_property32(
                PropMode::REPLACE,
                window_id,
                wm_window_type,
                AtomEnum::ATOM,
                &[wm_window_type_dock],
            )
            .map_err(|e| OverlayError::WindowCreation(format!("Change property failed: {}", e)))?;

            conn.flush()
                .map_err(|e| OverlayError::WindowCreation(format!("X11 flush failed: {}", e)))?;

            tracing::debug!("Set window type to DOCK for window {}", window_id);
            Ok(())
        },
        _ => Ok(()), // Ignore for other platforms
    }
}
