//! Windows-specific overlay functionality

use crate::{OverlayError, Result};
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};

use windows::Win32::Foundation::HWND;
use windows::Win32::UI::WindowsAndMessaging::{
    GetWindowLongW, SetWindowLongW, SetWindowPos, GWL_EXSTYLE, HWND_TOPMOST, SWP_NOMOVE,
    SWP_NOSIZE, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT,
};

/// Get the HWND from a winit window
fn get_hwnd(window: &winit::window::Window) -> Result<HWND> {
    match window.window_handle().map_err(|e| OverlayError::WindowCreation(e.to_string()))?.as_raw()
    {
        RawWindowHandle::Win32(handle) => Ok(HWND(handle.hwnd.get() as *mut _)),
        _ => Err(OverlayError::UnsupportedPlatform(
            "Expected Win32 window handle".into(),
        )),
    }
}

pub fn set_click_through_impl(window: &winit::window::Window, enabled: bool) -> Result<()> {
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

pub fn set_always_on_top_impl(window: &winit::window::Window, enabled: bool) -> Result<()> {
    let hwnd = get_hwnd(window)?;

    unsafe {
        let insert_after = if enabled {
            HWND_TOPMOST
        } else {
            windows::Win32::UI::WindowsAndMessaging::HWND_NOTOPMOST
        };

        SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            .map_err(|e| OverlayError::WindowCreation(e.to_string()))?;
    }

    Ok(())
}

pub fn set_transparent_impl(window: &winit::window::Window) -> Result<()> {
    let hwnd = get_hwnd(window)?;

    unsafe {
        let mut ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE) as u32;
        ex_style |= WS_EX_LAYERED.0 | WS_EX_TOOLWINDOW.0;
        SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style as i32);
    }

    Ok(())
}
