//! Windows desktop backend (Win32 API via the `windows` crate).
//!
//! * Windows: `EnumWindows` filtered to Alt-Tab style application windows;
//!   geometry uses DWM extended frame bounds (the visible frame, without the
//!   invisible resize borders), and move/resize compensate for those borders
//!   so the coordinates round-trip with `list_windows`.
//! * Screens: `EnumDisplayMonitors` + per-monitor DPI.
//! * Capture: GDI `BitBlt` from the screen DC; windows are rendered with
//!   `PrintWindow(PW_RENDERFULLCONTENT)` so occluded windows capture
//!   correctly, falling back to a screen-area capture.
//! * Input: `SendInput`. Text is typed as Unicode (`KEYEVENTF_UNICODE`), so
//!   any character works regardless of keyboard layout.
//!
//! The process opts into per-monitor DPI awareness so every coordinate is in
//! physical pixels, consistent across screenshots and input.

use std::collections::HashMap;
use std::ffi::c_void;
use std::mem::size_of;
use std::path::Path;
use std::thread::sleep;
use std::time::Duration;

use image::RgbaImage;
use windows::Win32::Foundation::{BOOL, CloseHandle, HWND, LPARAM, POINT, RECT, WPARAM};
use windows::Win32::Graphics::Dwm::{
    DWMWA_CLOAKED, DWMWA_EXTENDED_FRAME_BOUNDS, DwmGetWindowAttribute,
};
use windows::Win32::Graphics::Gdi::{
    BI_RGB, BITMAPINFO, BITMAPINFOHEADER, BitBlt, CAPTUREBLT, CreateCompatibleBitmap,
    CreateCompatibleDC, DIB_RGB_COLORS, DeleteDC, DeleteObject, EnumDisplayMonitors, GetDC,
    GetDIBits, GetMonitorInfoW, HBITMAP, HDC, HGDIOBJ, HMONITOR, MONITORINFO, MONITORINFOEXW,
    ReleaseDC, SRCCOPY, SelectObject,
};
use windows::Win32::Storage::Xps::{PRINT_WINDOW_FLAGS, PrintWindow};
use windows::Win32::System::Threading::{
    AttachThreadInput, GetCurrentThreadId, OpenProcess, PROCESS_NAME_WIN32,
    PROCESS_QUERY_LIMITED_INFORMATION, QueryFullProcessImageNameW,
};
use windows::Win32::UI::HiDpi::{
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2, GetDpiForMonitor, MDT_EFFECTIVE_DPI,
    SetProcessDpiAwarenessContext,
};
use windows::Win32::UI::Input::KeyboardAndMouse::{
    INPUT, INPUT_0, INPUT_KEYBOARD, INPUT_MOUSE, KEYBD_EVENT_FLAGS, KEYBDINPUT,
    KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, MAPVK_VK_TO_VSC, MOUSE_EVENT_FLAGS,
    MOUSEEVENTF_HWHEEL, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_MIDDLEDOWN,
    MOUSEEVENTF_MIDDLEUP, MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP, MOUSEEVENTF_WHEEL,
    MOUSEINPUT, MapVirtualKeyW, SendInput, VIRTUAL_KEY, VkKeyScanW,
};
use windows::Win32::UI::WindowsAndMessaging::{
    BringWindowToTop, EnumWindows, GW_OWNER, GWL_EXSTYLE, GetCursorPos, GetForegroundWindow,
    GetSystemMetrics, GetWindow, GetWindowLongW, GetWindowRect, GetWindowTextLengthW,
    GetWindowTextW, GetWindowThreadProcessId, IsIconic, IsWindow, IsWindowVisible, IsZoomed,
    MONITORINFOF_PRIMARY, PW_RENDERFULLCONTENT, PostMessageW, SM_CXVIRTUALSCREEN,
    SM_CYVIRTUALSCREEN, SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SW_MAXIMIZE, SW_MINIMIZE, SW_RESTORE,
    SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, SetCursorPos, SetForegroundWindow,
    SetWindowPos, ShowWindow, WM_CLOSE, WS_EX_TOOLWINDOW,
};
use windows::core::PWSTR;

use super::{DesktopBackend, DesktopError, DesktopResult};
use crate::imaging::{PixelLayout, framebuffer_to_rgba};
use crate::keys::{Key, NamedKey, is_extended_vk, named_to_vk};
use crate::types::{MouseButton, Rect, ScreenInfo, ScrollDirection, TypeReport, WindowInfo};

/// Wheel delta for one notch.
const WHEEL_DELTA: i32 = 120;
/// Time allowed for a window to become foreground after focusing.
const FOCUS_SETTLE: Duration = Duration::from_millis(60);

/// Win32 backend. Stateless: every call queries the live desktop.
pub struct WindowsBackend {
    dpi_aware: bool,
}

fn op_err(context: &str, e: impl std::fmt::Display) -> DesktopError {
    DesktopError::OperationFailed(format!("{context}: {e}"))
}

fn null_hwnd() -> HWND {
    HWND(std::ptr::null_mut())
}

fn hwnd_id(hwnd: HWND) -> String {
    (hwnd.0 as usize).to_string()
}

/// Parse a window id and check that it names a live window.
fn hwnd_from_id(id: &str) -> DesktopResult<HWND> {
    let raw: usize = id
        .parse()
        .map_err(|_| DesktopError::WindowNotFound(id.to_string()))?;
    let hwnd = HWND(raw as *mut c_void);
    // SAFETY: IsWindow accepts any value and only reports whether it is a
    // valid window handle.
    if unsafe { IsWindow(hwnd) }.as_bool() {
        Ok(hwnd)
    } else {
        Err(DesktopError::WindowNotFound(id.to_string()))
    }
}

fn rect_from(r: &RECT) -> Rect {
    Rect::new(
        r.left,
        r.top,
        u32::try_from(r.right.saturating_sub(r.left)).unwrap_or(0),
        u32::try_from(r.bottom.saturating_sub(r.top)).unwrap_or(0),
    )
}

/// Full window rectangle including invisible resize borders.
fn window_rect(hwnd: HWND) -> DesktopResult<RECT> {
    let mut r = RECT::default();
    // SAFETY: `r` is a valid out-pointer for the duration of the call.
    unsafe { GetWindowRect(hwnd, &mut r) }.map_err(|e| op_err("GetWindowRect", e))?;
    Ok(r)
}

/// Visible frame (DWM extended frame bounds), falling back to the window rect.
fn frame_rect(hwnd: HWND) -> DesktopResult<RECT> {
    let mut r = RECT::default();
    // SAFETY: `r` is a RECT-sized out buffer, as DWMWA_EXTENDED_FRAME_BOUNDS requires.
    let ok = unsafe {
        DwmGetWindowAttribute(
            hwnd,
            DWMWA_EXTENDED_FRAME_BOUNDS,
            (&mut r as *mut RECT).cast::<c_void>(),
            size_of::<RECT>() as u32,
        )
    }
    .is_ok();
    if ok && r.right > r.left && r.bottom > r.top {
        Ok(r)
    } else {
        window_rect(hwnd)
    }
}

fn is_cloaked(hwnd: HWND) -> bool {
    let mut cloaked: u32 = 0;
    // SAFETY: DWMWA_CLOAKED writes a DWORD into `cloaked`.
    unsafe {
        DwmGetWindowAttribute(
            hwnd,
            DWMWA_CLOAKED,
            (&mut cloaked as *mut u32).cast::<c_void>(),
            size_of::<u32>() as u32,
        )
    }
    .is_ok()
        && cloaked != 0
}

fn window_title(hwnd: HWND) -> String {
    // SAFETY: plain query on a window handle.
    let len = unsafe { GetWindowTextLengthW(hwnd) };
    let Ok(len) = usize::try_from(len) else {
        return String::new();
    };
    if len == 0 {
        return String::new();
    }
    let mut buf = vec![0u16; len + 1];
    // SAFETY: `buf` is writable for its full length.
    let n = unsafe { GetWindowTextW(hwnd, &mut buf) };
    let n = usize::try_from(n).unwrap_or(0).min(buf.len());
    String::from_utf16_lossy(&buf[..n])
}

fn window_pid(hwnd: HWND) -> Option<u32> {
    let mut pid = 0u32;
    // SAFETY: `pid` is a valid out-pointer.
    unsafe { GetWindowThreadProcessId(hwnd, Some(&mut pid)) };
    (pid != 0).then_some(pid)
}

fn process_name(pid: u32) -> Option<String> {
    // SAFETY: the handle is closed below; buffers outlive the calls.
    unsafe {
        let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid).ok()?;
        let mut buf = [0u16; 1024];
        let mut size = buf.len() as u32;
        let res = QueryFullProcessImageNameW(
            handle,
            PROCESS_NAME_WIN32,
            PWSTR(buf.as_mut_ptr()),
            &mut size,
        );
        let _ = CloseHandle(handle);
        res.ok()?;
        let path = String::from_utf16_lossy(&buf[..(size as usize).min(buf.len())]);
        Path::new(&path)
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
    }
}

/// Alt-Tab style filter: unowned, not a tool window, has a title.
fn is_app_window(hwnd: HWND) -> bool {
    // SAFETY: plain queries on a window handle.
    unsafe {
        let owned = GetWindow(hwnd, GW_OWNER).is_ok_and(|o| !o.is_invalid());
        let ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE) as u32;
        !owned && ex_style & WS_EX_TOOLWINDOW.0 == 0 && GetWindowTextLengthW(hwnd) > 0
    }
}

fn window_info(hwnd: HWND, names: &mut HashMap<u32, Option<String>>) -> DesktopResult<WindowInfo> {
    let frame = rect_from(&frame_rect(hwnd)?);
    // SAFETY: plain queries on a window handle.
    let (visible_flag, minimized, maximized) = unsafe {
        (
            IsWindowVisible(hwnd).as_bool(),
            IsIconic(hwnd).as_bool(),
            IsZoomed(hwnd).as_bool(),
        )
    };
    let pid = window_pid(hwnd);
    let process_name = pid.and_then(|p| names.entry(p).or_insert_with(|| process_name(p)).clone());
    Ok(WindowInfo {
        id: hwnd_id(hwnd),
        title: window_title(hwnd),
        process_name,
        pid,
        x: frame.x,
        y: frame.y,
        width: frame.width,
        height: frame.height,
        visible: visible_flag && !minimized && !is_cloaked(hwnd),
        minimized,
        maximized,
    })
}

unsafe extern "system" fn collect_hwnd(hwnd: HWND, lparam: LPARAM) -> BOOL {
    // SAFETY: lparam is the `&mut Vec<usize>` passed by `enum_windows`, which
    // outlives the synchronous EnumWindows call.
    let out = unsafe { &mut *(lparam.0 as *mut Vec<usize>) };
    out.push(hwnd.0 as usize);
    BOOL(1)
}

fn enum_windows() -> DesktopResult<Vec<HWND>> {
    let mut raw: Vec<usize> = Vec::new();
    // SAFETY: the callback only touches `raw` through lparam during the call.
    unsafe {
        EnumWindows(
            Some(collect_hwnd),
            LPARAM(&mut raw as *mut Vec<usize> as isize),
        )
    }
    .map_err(|e| op_err("EnumWindows", e))?;
    Ok(raw.into_iter().map(|h| HWND(h as *mut c_void)).collect())
}

unsafe extern "system" fn collect_monitor(
    hmon: HMONITOR,
    _hdc: HDC,
    _rect: *mut RECT,
    lparam: LPARAM,
) -> BOOL {
    // SAFETY: lparam is the `&mut Vec<usize>` passed by `list_screens`.
    let out = unsafe { &mut *(lparam.0 as *mut Vec<usize>) };
    out.push(hmon.0 as usize);
    BOOL(1)
}

fn key_input(vk: u16, scan: u16, flags: KEYBD_EVENT_FLAGS) -> INPUT {
    INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT {
                wVk: VIRTUAL_KEY(vk),
                wScan: scan,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: 0,
            },
        },
    }
}

fn mouse_input(flags: MOUSE_EVENT_FLAGS, data: i32) -> INPUT {
    INPUT {
        r#type: INPUT_MOUSE,
        Anonymous: INPUT_0 {
            mi: MOUSEINPUT {
                dx: 0,
                dy: 0,
                // Wheel deltas are signed values carried in a DWORD.
                mouseData: data as u32,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: 0,
            },
        },
    }
}

/// Inject events, failing if Windows dropped any (UIPI / secure desktop).
fn send(inputs: &[INPUT]) -> DesktopResult<()> {
    if inputs.is_empty() {
        return Ok(());
    }
    // SAFETY: `inputs` is a valid slice of initialized INPUT structs.
    let sent = unsafe { SendInput(inputs, size_of::<INPUT>() as i32) };
    if sent as usize == inputs.len() {
        Ok(())
    } else {
        Err(DesktopError::OperationFailed(format!(
            "SendInput injected {sent}/{} events; input is blocked (elevated target window \
             under UIPI, locked workstation or secure desktop)",
            inputs.len()
        )))
    }
}

/// Virtual-key event for a VK code, with scan code and extended flag.
fn vk_event(vk: u16, down: bool) -> INPUT {
    // SAFETY: pure table lookup.
    let scan = unsafe { MapVirtualKeyW(u32::from(vk), MAPVK_VK_TO_VSC) } as u16;
    let mut flags = KEYBD_EVENT_FLAGS(0);
    if is_extended_vk(vk) {
        flags |= KEYEVENTF_EXTENDEDKEY;
    }
    if !down {
        flags |= KEYEVENTF_KEYUP;
    }
    key_input(vk, scan, flags)
}

const VK_SHIFT: u16 = 0x10;

/// Virtual key for a character on the active layout, and whether Shift is
/// needed.
fn char_vk(c: char) -> DesktopResult<(u16, bool)> {
    let mut units = [0u16; 2];
    let encoded = c.encode_utf16(&mut units);
    if encoded.len() != 1 {
        return Err(DesktopError::InvalidInput(format!(
            "'{c}' cannot be sent as a key press; use type_text instead"
        )));
    }
    // SAFETY: pure layout lookup.
    let res = unsafe { VkKeyScanW(units[0]) };
    if res == -1 {
        return Err(DesktopError::InvalidInput(format!(
            "'{c}' has no key on the current keyboard layout; use type_text instead"
        )));
    }
    let res = res as u16;
    Ok((res & 0xff, res & 0x100 != 0))
}

impl WindowsBackend {
    /// Create the backend and enable per-monitor DPI awareness.
    pub fn new() -> DesktopResult<Self> {
        // SAFETY: process-wide setting; fails harmlessly if already set.
        let dpi_aware =
            unsafe { SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2) }
                .is_ok();
        // SAFETY: plain metric query.
        let width = unsafe { GetSystemMetrics(SM_CXVIRTUALSCREEN) };
        if width <= 0 {
            return Err(DesktopError::NotAvailable(
                "no interactive desktop (running as a service or in session 0?)".to_string(),
            ));
        }
        Ok(Self { dpi_aware })
    }

    fn set_foreground(hwnd: HWND) -> bool {
        // SAFETY: standard focus APIs on a validated handle; the thread
        // input attachment is always undone.
        unsafe {
            let fg = GetForegroundWindow();
            let fg_thread = GetWindowThreadProcessId(fg, None);
            let this_thread = GetCurrentThreadId();
            let attach = fg_thread != 0 && fg_thread != this_thread;
            if attach {
                let _ = AttachThreadInput(this_thread, fg_thread, true);
            }
            let _ = BringWindowToTop(hwnd);
            let ok = SetForegroundWindow(hwnd).as_bool();
            if attach {
                let _ = AttachThreadInput(this_thread, fg_thread, false);
            }
            ok
        }
    }

    /// Capture a screen rectangle via GDI.
    fn blit_screen(rect: Rect) -> DesktopResult<RgbaImage> {
        let (w, h) = dims(rect)?;
        let screen = ScreenDc::get()?;
        let mem = MemDc::new(screen.0, w, h)?;
        // SAFETY: both DCs are valid for the duration of the call.
        unsafe {
            BitBlt(
                mem.dc,
                0,
                0,
                w,
                h,
                screen.0,
                rect.x,
                rect.y,
                SRCCOPY | CAPTUREBLT,
            )
        }
        .map_err(|e| DesktopError::ScreenshotFailed(format!("BitBlt: {e}")))?;
        mem.read_pixels(screen.0)
    }
}

fn dims(rect: Rect) -> DesktopResult<(i32, i32)> {
    let w = i32::try_from(rect.width).ok().filter(|w| *w > 0);
    let h = i32::try_from(rect.height).ok().filter(|h| *h > 0);
    match (w, h) {
        (Some(w), Some(h)) => Ok((w, h)),
        _ => Err(DesktopError::ScreenshotFailed(format!(
            "invalid capture size {}x{}",
            rect.width, rect.height
        ))),
    }
}

/// Screen device context, released on drop.
struct ScreenDc(HDC);

impl ScreenDc {
    fn get() -> DesktopResult<Self> {
        // SAFETY: GetDC(NULL) returns the screen DC or null on failure.
        let dc = unsafe { GetDC(null_hwnd()) };
        if dc.is_invalid() {
            return Err(DesktopError::ScreenshotFailed(
                "GetDC failed (no interactive desktop?)".to_string(),
            ));
        }
        Ok(Self(dc))
    }
}

impl Drop for ScreenDc {
    fn drop(&mut self) {
        // SAFETY: releases the DC obtained in `get`.
        unsafe { ReleaseDC(null_hwnd(), self.0) };
    }
}

/// Memory DC with a selected compatible bitmap, cleaned up on drop.
struct MemDc {
    dc: HDC,
    bitmap: HBITMAP,
    previous: HGDIOBJ,
    width: i32,
    height: i32,
}

impl MemDc {
    fn new(screen: HDC, width: i32, height: i32) -> DesktopResult<Self> {
        // SAFETY: creates GDI objects owned by the returned guard.
        unsafe {
            let dc = CreateCompatibleDC(screen);
            if dc.is_invalid() {
                return Err(DesktopError::ScreenshotFailed(
                    "CreateCompatibleDC failed".to_string(),
                ));
            }
            let bitmap = CreateCompatibleBitmap(screen, width, height);
            if bitmap.is_invalid() {
                let _ = DeleteDC(dc);
                return Err(DesktopError::ScreenshotFailed(format!(
                    "CreateCompatibleBitmap({width}x{height}) failed"
                )));
            }
            let previous = SelectObject(dc, bitmap);
            Ok(Self {
                dc,
                bitmap,
                previous,
                width,
                height,
            })
        }
    }

    /// Deselect the bitmap and read it as top-down BGRA.
    fn read_pixels(self, screen: HDC) -> DesktopResult<RgbaImage> {
        let mut info = BITMAPINFO {
            bmiHeader: BITMAPINFOHEADER {
                biSize: size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: self.width,
                // Negative height = top-down rows.
                biHeight: -self.height,
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB.0,
                ..Default::default()
            },
            ..Default::default()
        };
        let (w, h) = (self.width as usize, self.height as usize);
        let mut buf = vec![0u8; w * h * 4];
        // SAFETY: the bitmap must not be selected into a DC for GetDIBits;
        // `buf` holds exactly width*height 32-bit pixels.
        let lines = unsafe {
            SelectObject(self.dc, self.previous);
            GetDIBits(
                screen,
                self.bitmap,
                0,
                self.height as u32,
                Some(buf.as_mut_ptr().cast::<c_void>()),
                &mut info,
                DIB_RGB_COLORS,
            )
        };
        if lines != self.height {
            return Err(DesktopError::ScreenshotFailed(format!(
                "GetDIBits returned {lines} of {} rows",
                self.height
            )));
        }
        framebuffer_to_rgba(&buf, w as u32, h as u32, w * 4, PixelLayout::Bgrx)
            .map_err(DesktopError::ScreenshotFailed)
    }
}

impl Drop for MemDc {
    fn drop(&mut self) {
        // SAFETY: restores the original object and frees what `new` created.
        unsafe {
            SelectObject(self.dc, self.previous);
            let _ = DeleteObject(self.bitmap);
            let _ = DeleteDC(self.dc);
        }
    }
}

impl DesktopBackend for WindowsBackend {
    fn platform_name(&self) -> &'static str {
        "windows"
    }

    fn diagnostics(&self) -> serde_json::Value {
        serde_json::json!({
            "dpi_awareness": if self.dpi_aware { "per-monitor-v2" } else { "inherited" },
            "text_input": "unicode",
        })
    }

    fn list_windows(&self) -> DesktopResult<Vec<WindowInfo>> {
        let mut names = HashMap::new();
        Ok(enum_windows()?
            .into_iter()
            .filter(|&h| is_app_window(h))
            .filter_map(|h| window_info(h, &mut names).ok())
            .collect())
    }

    fn get_active_window(&self) -> DesktopResult<Option<WindowInfo>> {
        // SAFETY: plain query.
        let hwnd = unsafe { GetForegroundWindow() };
        if hwnd.is_invalid() {
            return Ok(None);
        }
        Ok(window_info(hwnd, &mut HashMap::new()).ok())
    }

    fn focus_window(&self, id: &str) -> DesktopResult<()> {
        let hwnd = hwnd_from_id(id)?;
        // SAFETY: validated handle.
        if unsafe { IsIconic(hwnd) }.as_bool() {
            let _ = unsafe { ShowWindow(hwnd, SW_RESTORE) };
        }
        if !Self::set_foreground(hwnd) {
            // Foreground lock: a synthetic Alt tap grants this process the
            // right to change the foreground window.
            send(&[vk_event(0x12, true), vk_event(0x12, false)])?;
            Self::set_foreground(hwnd);
        }
        sleep(FOCUS_SETTLE);
        // SAFETY: plain query.
        if unsafe { GetForegroundWindow() } == hwnd {
            Ok(())
        } else {
            Err(DesktopError::OperationFailed(format!(
                "Windows refused to bring window {id} to the foreground \
                 (focus-stealing prevention); it may be flashing in the taskbar instead"
            )))
        }
    }

    fn move_window(&self, id: &str, x: i32, y: i32) -> DesktopResult<()> {
        let hwnd = hwnd_from_id(id)?;
        // SAFETY: validated handle.
        if unsafe { IsZoomed(hwnd) }.as_bool() || unsafe { IsIconic(hwnd) }.as_bool() {
            let _ = unsafe { ShowWindow(hwnd, SW_RESTORE) };
        }
        let outer = window_rect(hwnd)?;
        let frame = frame_rect(hwnd)?;
        // Offset so the *visible* frame lands at (x, y).
        let nx = x.saturating_sub(frame.left - outer.left);
        let ny = y.saturating_sub(frame.top - outer.top);
        // SAFETY: validated handle.
        unsafe {
            SetWindowPos(
                hwnd,
                null_hwnd(),
                nx,
                ny,
                0,
                0,
                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
            )
        }
        .map_err(|e| op_err("SetWindowPos", e))
    }

    fn resize_window(&self, id: &str, width: u32, height: u32) -> DesktopResult<()> {
        let hwnd = hwnd_from_id(id)?;
        // SAFETY: validated handle.
        if unsafe { IsZoomed(hwnd) }.as_bool() {
            let _ = unsafe { ShowWindow(hwnd, SW_RESTORE) };
        }
        let outer = rect_from(&window_rect(hwnd)?);
        let frame = rect_from(&frame_rect(hwnd)?);
        let extra_w = outer.width.saturating_sub(frame.width);
        let extra_h = outer.height.saturating_sub(frame.height);
        let w = i32::try_from(width.saturating_add(extra_w)).unwrap_or(i32::MAX);
        let h = i32::try_from(height.saturating_add(extra_h)).unwrap_or(i32::MAX);
        // SAFETY: validated handle.
        unsafe {
            SetWindowPos(
                hwnd,
                null_hwnd(),
                0,
                0,
                w,
                h,
                SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE,
            )
        }
        .map_err(|e| op_err("SetWindowPos", e))
    }

    fn minimize_window(&self, id: &str) -> DesktopResult<()> {
        let hwnd = hwnd_from_id(id)?;
        // SAFETY: validated handle; the return value is the previous
        // visibility, not an error indicator.
        let _ = unsafe { ShowWindow(hwnd, SW_MINIMIZE) };
        Ok(())
    }

    fn maximize_window(&self, id: &str) -> DesktopResult<()> {
        let hwnd = hwnd_from_id(id)?;
        // SAFETY: see minimize_window.
        let _ = unsafe { ShowWindow(hwnd, SW_MAXIMIZE) };
        Ok(())
    }

    fn restore_window(&self, id: &str) -> DesktopResult<()> {
        let hwnd = hwnd_from_id(id)?;
        // SAFETY: see minimize_window.
        let _ = unsafe { ShowWindow(hwnd, SW_RESTORE) };
        Ok(())
    }

    fn close_window(&self, id: &str) -> DesktopResult<()> {
        let hwnd = hwnd_from_id(id)?;
        // SAFETY: posting WM_CLOSE is the same as clicking the close button.
        unsafe { PostMessageW(hwnd, WM_CLOSE, WPARAM(0), LPARAM(0)) }
            .map_err(|e| op_err("PostMessageW(WM_CLOSE)", e))
    }

    fn list_screens(&self) -> DesktopResult<Vec<ScreenInfo>> {
        let mut raw: Vec<usize> = Vec::new();
        // SAFETY: the callback only touches `raw` during the call.
        let ok = unsafe {
            EnumDisplayMonitors(
                HDC(std::ptr::null_mut()),
                None,
                Some(collect_monitor),
                LPARAM(&mut raw as *mut Vec<usize> as isize),
            )
        };
        if !ok.as_bool() {
            return Err(DesktopError::OperationFailed(
                "EnumDisplayMonitors failed".to_string(),
            ));
        }
        let mut screens = Vec::with_capacity(raw.len());
        for (idx, h) in raw.into_iter().enumerate() {
            let hmon = HMONITOR(h as *mut c_void);
            let mut info = MONITORINFOEXW {
                monitorInfo: MONITORINFO {
                    cbSize: size_of::<MONITORINFOEXW>() as u32,
                    ..Default::default()
                },
                ..Default::default()
            };
            // SAFETY: `info` is a MONITORINFOEXW with cbSize set accordingly.
            let ok = unsafe {
                GetMonitorInfoW(
                    hmon,
                    (&mut info as *mut MONITORINFOEXW).cast::<MONITORINFO>(),
                )
            };
            if !ok.as_bool() {
                continue;
            }
            let (mut dpi_x, mut dpi_y) = (96u32, 96u32);
            // SAFETY: valid out-pointers.
            let _ = unsafe { GetDpiForMonitor(hmon, MDT_EFFECTIVE_DPI, &mut dpi_x, &mut dpi_y) };
            let name_len = info
                .szDevice
                .iter()
                .position(|&c| c == 0)
                .unwrap_or(info.szDevice.len());
            let r = rect_from(&info.monitorInfo.rcMonitor);
            screens.push(ScreenInfo {
                id: u32::try_from(idx).unwrap_or(u32::MAX),
                name: String::from_utf16_lossy(&info.szDevice[..name_len]),
                x: r.x,
                y: r.y,
                width: r.width,
                height: r.height,
                is_primary: info.monitorInfo.dwFlags & MONITORINFOF_PRIMARY != 0,
                scale: f64::from(dpi_x) / 96.0,
            });
        }
        Ok(screens)
    }

    fn virtual_screen(&self) -> DesktopResult<Rect> {
        // SAFETY: plain metric queries.
        let (x, y, w, h) = unsafe {
            (
                GetSystemMetrics(SM_XVIRTUALSCREEN),
                GetSystemMetrics(SM_YVIRTUALSCREEN),
                GetSystemMetrics(SM_CXVIRTUALSCREEN),
                GetSystemMetrics(SM_CYVIRTUALSCREEN),
            )
        };
        Ok(Rect::new(
            x,
            y,
            u32::try_from(w).unwrap_or(0),
            u32::try_from(h).unwrap_or(0),
        ))
    }

    fn capture_region(&self, rect: Rect) -> DesktopResult<RgbaImage> {
        Self::blit_screen(rect)
    }

    fn capture_window(&self, id: &str) -> DesktopResult<(RgbaImage, Rect)> {
        let hwnd = hwnd_from_id(id)?;
        // SAFETY: validated handle.
        if unsafe { IsIconic(hwnd) }.as_bool() {
            return Err(DesktopError::ScreenshotFailed(format!(
                "window {id} is minimized; restore it first"
            )));
        }
        let outer = rect_from(&window_rect(hwnd)?);
        let frame = rect_from(&frame_rect(hwnd)?);
        let (w, h) = dims(outer)?;

        let rendered = (|| {
            let screen = ScreenDc::get()?;
            let mem = MemDc::new(screen.0, w, h)?;
            // SAFETY: valid window handle and memory DC.
            let ok = unsafe { PrintWindow(hwnd, mem.dc, PRINT_WINDOW_FLAGS(PW_RENDERFULLCONTENT)) };
            if !ok.as_bool() {
                return Err(DesktopError::ScreenshotFailed(
                    "PrintWindow failed".to_string(),
                ));
            }
            mem.read_pixels(screen.0)
        })();

        match rendered {
            Ok(img) => {
                // Crop the invisible resize borders to the visible frame.
                let off_x = u32::try_from(frame.x - outer.x).unwrap_or(0);
                let off_y = u32::try_from(frame.y - outer.y).unwrap_or(0);
                let cw = frame.width.min(img.width().saturating_sub(off_x));
                let ch = frame.height.min(img.height().saturating_sub(off_y));
                if cw == 0 || ch == 0 {
                    return Ok((img, outer));
                }
                let cropped = image::imageops::crop_imm(&img, off_x, off_y, cw, ch).to_image();
                Ok((cropped, Rect::new(frame.x, frame.y, cw, ch)))
            },
            Err(_) => {
                // Fall back to the on-screen pixels of the frame.
                let desktop = self.virtual_screen()?;
                let area = frame.intersect(&desktop).ok_or_else(|| {
                    DesktopError::ScreenshotFailed(format!("window {id} is off-screen"))
                })?;
                Ok((Self::blit_screen(area)?, area))
            },
        }
    }

    fn mouse_position(&self) -> DesktopResult<(i32, i32)> {
        let mut p = POINT::default();
        // SAFETY: valid out-pointer.
        unsafe { GetCursorPos(&mut p) }.map_err(|e| op_err("GetCursorPos", e))?;
        Ok((p.x, p.y))
    }

    fn move_mouse(&self, x: i32, y: i32) -> DesktopResult<()> {
        // SAFETY: plain API call.
        unsafe { SetCursorPos(x, y) }.map_err(|e| op_err("SetCursorPos", e))
    }

    fn mouse_button(&self, button: MouseButton, down: bool) -> DesktopResult<()> {
        let flags = match (button, down) {
            (MouseButton::Left, true) => MOUSEEVENTF_LEFTDOWN,
            (MouseButton::Left, false) => MOUSEEVENTF_LEFTUP,
            (MouseButton::Right, true) => MOUSEEVENTF_RIGHTDOWN,
            (MouseButton::Right, false) => MOUSEEVENTF_RIGHTUP,
            (MouseButton::Middle, true) => MOUSEEVENTF_MIDDLEDOWN,
            (MouseButton::Middle, false) => MOUSEEVENTF_MIDDLEUP,
        };
        send(&[mouse_input(flags, 0)])
    }

    fn scroll(&self, direction: ScrollDirection, amount: i32) -> DesktopResult<()> {
        let (flags, notch) = match direction {
            // Positive amount scrolls down, which is a negative wheel delta.
            ScrollDirection::Vertical => (MOUSEEVENTF_WHEEL, -WHEEL_DELTA * amount.signum()),
            ScrollDirection::Horizontal => (MOUSEEVENTF_HWHEEL, WHEEL_DELTA * amount.signum()),
        };
        let events: Vec<INPUT> = (0..amount.unsigned_abs())
            .map(|_| mouse_input(flags, notch))
            .collect();
        send(&events)
    }

    fn key(&self, key: Key, down: bool) -> DesktopResult<()> {
        match key {
            Key::Named(n) => send(&[vk_event(named_to_vk(n), down)]),
            Key::Char(c) => {
                let (vk, shift) = char_vk(c)?;
                let events: Vec<INPUT> = match (shift, down) {
                    (true, true) => vec![vk_event(VK_SHIFT, true), vk_event(vk, true)],
                    (true, false) => vec![vk_event(vk, false), vk_event(VK_SHIFT, false)],
                    (false, d) => vec![vk_event(vk, d)],
                };
                send(&events)
            },
        }
    }

    fn type_text(&self, text: &str, interval_ms: u64) -> DesktopResult<TypeReport> {
        let mut report = TypeReport::default();
        let delay = Duration::from_millis(interval_ms);
        let mut chars = text.chars().peekable();
        while let Some(c) = chars.next() {
            let events: Vec<INPUT> = match c {
                // "\r\n" is one Enter.
                '\r' if chars.peek() == Some(&'\n') => continue,
                '\n' | '\r' => {
                    let vk = named_to_vk(NamedKey::Enter);
                    vec![vk_event(vk, true), vk_event(vk, false)]
                },
                '\t' => {
                    let vk = named_to_vk(NamedKey::Tab);
                    vec![vk_event(vk, true), vk_event(vk, false)]
                },
                c if c.is_control() => {
                    report.skipped.push(c);
                    continue;
                },
                c => {
                    let mut units = [0u16; 2];
                    c.encode_utf16(&mut units)
                        .iter()
                        .flat_map(|&u| {
                            [
                                key_input(0, u, KEYEVENTF_UNICODE),
                                key_input(0, u, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
                            ]
                        })
                        .collect()
                },
            };
            send(&events)?;
            report.typed += 1;
            if interval_ms > 0 && chars.peek().is_some() {
                sleep(delay);
            }
        }
        Ok(report)
    }
}
