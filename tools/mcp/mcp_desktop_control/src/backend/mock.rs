//! In-memory backend for tests. Records every input event instead of
//! touching the real mouse/keyboard, and serves canned windows/screens.

use std::sync::Mutex;

use image::{Rgba, RgbaImage};

use super::{DesktopBackend, DesktopError, DesktopResult};
use crate::keys::Key;
use crate::types::{MouseButton, Rect, ScreenInfo, ScrollDirection, TypeReport, WindowInfo};

/// A recorded side effect.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    MoveMouse(i32, i32),
    Button(MouseButton, bool),
    Scroll(ScrollDirection, i32),
    Key(Key, bool),
    Type(String, u64),
    Focus(String),
    MoveWindow(String, i32, i32),
    ResizeWindow(String, u32, u32),
    Minimize(String),
    Maximize(String),
    Restore(String),
    Close(String),
    Capture(Rect),
}

/// Test double for [`DesktopBackend`].
pub struct MockBackend {
    pub windows: Vec<WindowInfo>,
    pub screens: Vec<ScreenInfo>,
    pub events: Mutex<Vec<Event>>,
    pub pointer: Mutex<(i32, i32)>,
    /// Key that fails when pressed (to exercise cleanup paths).
    pub failing_key: Option<Key>,
}

impl MockBackend {
    /// Two screens side by side and three windows.
    pub fn new() -> Self {
        let win = |id: &str, title: &str, visible: bool| WindowInfo {
            id: id.to_string(),
            title: title.to_string(),
            process_name: Some("app".to_string()),
            pid: Some(42),
            x: 10,
            y: 20,
            width: 300,
            height: 200,
            visible,
            minimized: !visible,
            maximized: false,
        };
        Self {
            windows: vec![
                win("100", "Terminal - bash", true),
                win("200", "Firefox", true),
                win("300", "Hidden Notes", false),
            ],
            screens: vec![
                ScreenInfo {
                    id: 0,
                    name: "left".to_string(),
                    x: 0,
                    y: 0,
                    width: 1920,
                    height: 1080,
                    is_primary: false,
                    scale: 1.0,
                },
                ScreenInfo {
                    id: 1,
                    name: "right".to_string(),
                    x: 1920,
                    y: 0,
                    width: 1280,
                    height: 1024,
                    is_primary: true,
                    scale: 1.0,
                },
            ],
            events: Mutex::new(Vec::new()),
            pointer: Mutex::new((5, 5)),
            failing_key: None,
        }
    }

    /// Snapshot of recorded events.
    pub fn events(&self) -> Vec<Event> {
        self.events.lock().map(|e| e.clone()).unwrap_or_default()
    }

    fn record(&self, e: Event) {
        if let Ok(mut events) = self.events.lock() {
            events.push(e);
        }
    }

    fn window(&self, id: &str) -> DesktopResult<&WindowInfo> {
        self.windows
            .iter()
            .find(|w| w.id == id)
            .ok_or_else(|| DesktopError::WindowNotFound(id.to_string()))
    }
}

impl DesktopBackend for MockBackend {
    fn platform_name(&self) -> &'static str {
        "mock"
    }

    fn list_windows(&self) -> DesktopResult<Vec<WindowInfo>> {
        Ok(self.windows.clone())
    }

    fn get_active_window(&self) -> DesktopResult<Option<WindowInfo>> {
        Ok(self.windows.first().cloned())
    }

    fn focus_window(&self, id: &str) -> DesktopResult<()> {
        self.window(id)?;
        self.record(Event::Focus(id.to_string()));
        Ok(())
    }

    fn move_window(&self, id: &str, x: i32, y: i32) -> DesktopResult<()> {
        self.window(id)?;
        self.record(Event::MoveWindow(id.to_string(), x, y));
        Ok(())
    }

    fn resize_window(&self, id: &str, width: u32, height: u32) -> DesktopResult<()> {
        self.window(id)?;
        self.record(Event::ResizeWindow(id.to_string(), width, height));
        Ok(())
    }

    fn minimize_window(&self, id: &str) -> DesktopResult<()> {
        self.window(id)?;
        self.record(Event::Minimize(id.to_string()));
        Ok(())
    }

    fn maximize_window(&self, id: &str) -> DesktopResult<()> {
        self.window(id)?;
        self.record(Event::Maximize(id.to_string()));
        Ok(())
    }

    fn restore_window(&self, id: &str) -> DesktopResult<()> {
        self.window(id)?;
        self.record(Event::Restore(id.to_string()));
        Ok(())
    }

    fn close_window(&self, id: &str) -> DesktopResult<()> {
        self.window(id)?;
        self.record(Event::Close(id.to_string()));
        Ok(())
    }

    fn list_screens(&self) -> DesktopResult<Vec<ScreenInfo>> {
        Ok(self.screens.clone())
    }

    fn virtual_screen(&self) -> DesktopResult<Rect> {
        Ok(Rect::new(0, 0, 3200, 1080))
    }

    fn capture_region(&self, rect: Rect) -> DesktopResult<RgbaImage> {
        self.record(Event::Capture(rect));
        Ok(RgbaImage::from_pixel(
            rect.width,
            rect.height,
            Rgba([10, 20, 30, 255]),
        ))
    }

    fn capture_window(&self, id: &str) -> DesktopResult<(RgbaImage, Rect)> {
        let w = self.window(id)?;
        let rect = Rect::new(w.x, w.y, w.width, w.height);
        Ok((self.capture_region(rect)?, rect))
    }

    fn mouse_position(&self) -> DesktopResult<(i32, i32)> {
        Ok(self.pointer.lock().map(|p| *p).unwrap_or_default())
    }

    fn move_mouse(&self, x: i32, y: i32) -> DesktopResult<()> {
        if let Ok(mut p) = self.pointer.lock() {
            *p = (x, y);
        }
        self.record(Event::MoveMouse(x, y));
        Ok(())
    }

    fn mouse_button(&self, button: MouseButton, down: bool) -> DesktopResult<()> {
        self.record(Event::Button(button, down));
        Ok(())
    }

    fn scroll(&self, direction: ScrollDirection, amount: i32) -> DesktopResult<()> {
        self.record(Event::Scroll(direction, amount));
        Ok(())
    }

    fn key(&self, key: Key, down: bool) -> DesktopResult<()> {
        if down && self.failing_key == Some(key) {
            return Err(DesktopError::InvalidInput(format!(
                "mock failure on {key:?}"
            )));
        }
        self.record(Event::Key(key, down));
        Ok(())
    }

    fn type_text(&self, text: &str, interval_ms: u64) -> DesktopResult<TypeReport> {
        self.record(Event::Type(text.to_string(), interval_ms));
        Ok(TypeReport {
            typed: text.chars().filter(|c| *c != '\u{1}').count(),
            skipped: text.chars().filter(|c| *c == '\u{1}').collect(),
        })
    }
}
