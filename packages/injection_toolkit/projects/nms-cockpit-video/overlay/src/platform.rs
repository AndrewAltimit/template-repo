//! Platform-specific overlay functionality for NMS overlay
//!
//! This module handles Windows-specific window attributes for overlay behavior.

use anyhow::{anyhow, Result};
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};

#[cfg(windows)]
use windows::Win32::Foundation::HWND;
#[cfg(windows)]
use windows::Win32::UI::WindowsAndMessaging::{
    GetWindowLongW, SetWindowLongW, SetWindowPos, GWL_EXSTYLE, HWND_TOPMOST,
    SWP_NOMOVE, SWP_NOSIZE, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT,
};

/// Get the HWND from a winit window
#[cfg(windows)]
fn get_hwnd(window: &winit::window::Window) -> Result<HWND> {
    match window
        .window_handle()
        .map_err(|e| anyhow!("Failed to get window handle: {}", e))?
        .as_raw()
    {
        RawWindowHandle::Win32(handle) => Ok(HWND(handle.hwnd.get() as *mut _)),
        _ => Err(anyhow!("Expected Win32 window handle")),
    }
}

/// Set click-through mode for a window
///
/// When enabled, mouse input passes through the window to the one behind it.
#[cfg(windows)]
pub fn set_click_through(window: &winit::window::Window, enabled: bool) -> Result<()> {
    let hwnd = get_hwnd(window)?;

    unsafe {
        let mut ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE) as u32;

        if enabled {
            // Enable click-through
            ex_style |= WS_EX_TRANSPARENT.0 | WS_EX_LAYERED.0 | WS_EX_NOACTIVATE.0;
        } else {
            // Disable click-through
            ex_style &= !(WS_EX_TRANSPARENT.0 | WS_EX_NOACTIVATE.0);
        }

        SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style as i32);
    }

    Ok(())
}

/// Set always-on-top for a window
#[cfg(windows)]
pub fn set_always_on_top(window: &winit::window::Window, enabled: bool) -> Result<()> {
    let hwnd = get_hwnd(window)?;

    unsafe {
        let insert_after = if enabled {
            HWND_TOPMOST
        } else {
            windows::Win32::UI::WindowsAndMessaging::HWND_NOTOPMOST
        };

        SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            .map_err(|e| anyhow!("SetWindowPos failed: {}", e))?;
    }

    Ok(())
}

/// Make window transparent (for compositor)
#[cfg(windows)]
pub fn set_transparent(window: &winit::window::Window) -> Result<()> {
    let hwnd = get_hwnd(window)?;

    unsafe {
        let mut ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE) as u32;
        ex_style |= WS_EX_LAYERED.0 | WS_EX_TOOLWINDOW.0;
        SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style as i32);
    }

    Ok(())
}

// Stub implementations for non-Windows platforms
#[cfg(not(windows))]
pub fn set_click_through(_window: &winit::window::Window, _enabled: bool) -> Result<()> {
    Ok(())
}

#[cfg(not(windows))]
pub fn set_always_on_top(_window: &winit::window::Window, _enabled: bool) -> Result<()> {
    Ok(())
}

#[cfg(not(windows))]
pub fn set_transparent(_window: &winit::window::Window) -> Result<()> {
    Ok(())
}
