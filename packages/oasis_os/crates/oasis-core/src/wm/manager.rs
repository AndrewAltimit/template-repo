//! Window manager: lifecycle, drag/resize, focus, and input dispatch.
//!
//! The WM creates and manipulates groups of SDI objects to simulate windowed
//! interfaces. It is a consumer of the SDI API -- SDI remains a flat scene
//! graph with no concept of grouping or hierarchy.

use crate::backend::SdiBackend;
use crate::error::{OasisError, Result};
use crate::input::InputEvent;
use crate::sdi::SdiRegistry;

use super::hit_test::{ButtonKind, HitRegion, ResizeEdge, hit_test};
use super::window::{Geometry, Window, WindowConfig, WindowId, WindowState, WmTheme};

/// Events produced by the WM in response to input.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WmEvent {
    /// A window was brought to front.
    WindowFocused(WindowId),
    /// A window was moved.
    WindowMoved(WindowId),
    /// A window was resized.
    WindowResized(WindowId),
    /// A window was closed.
    WindowClosed(WindowId),
    /// A window was minimized.
    WindowMinimized(WindowId),
    /// A window was maximized.
    WindowMaximized(WindowId),
    /// A window was restored from minimized or maximized.
    WindowRestored(WindowId),
    /// Content area was clicked (coordinates are content-local).
    ContentClick(WindowId, i32, i32),
    /// Desktop background was clicked.
    DesktopClick(i32, i32),
    /// Nothing happened.
    None,
}

/// Active drag/resize operation.
#[derive(Debug, Clone)]
enum DragState {
    /// Dragging a window by its titlebar.
    Moving {
        window_id: WindowId,
        /// Cursor position at drag start.
        start_cursor_x: i32,
        start_cursor_y: i32,
        /// Window position at drag start.
        start_win_x: i32,
        start_win_y: i32,
    },
    /// Resizing a window by a handle.
    Resizing {
        window_id: WindowId,
        edge: ResizeEdge,
        start_cursor_x: i32,
        start_cursor_y: i32,
        start_geometry: Geometry,
    },
}

/// Minimum window content size during resize.
const MIN_WINDOW_SIZE: u32 = 40;

/// Cascade offset between newly created windows.
const CASCADE_OFFSET: i32 = 24;

/// The window manager.
///
/// Manages a list of windows ordered by z-depth (last = topmost).
/// Processes input events through hit testing and a drag/resize state machine.
pub struct WindowManager {
    /// Windows in z-order (last = topmost).
    windows: Vec<Window>,
    /// Visual theme.
    theme: WmTheme,
    /// Cascade position for the next window.
    next_cascade_x: i32,
    next_cascade_y: i32,
    /// Screen dimensions (for maximize and cascade wrapping).
    screen_w: u32,
    screen_h: u32,
    /// Active window id (receives keyboard input).
    active_window: Option<WindowId>,
    /// Current drag/resize operation.
    drag: Option<DragState>,
}

impl WindowManager {
    /// Create a new window manager for the given screen size.
    pub fn new(screen_w: u32, screen_h: u32) -> Self {
        Self {
            windows: Vec::new(),
            theme: WmTheme::default(),
            next_cascade_x: CASCADE_OFFSET,
            next_cascade_y: CASCADE_OFFSET,
            screen_w,
            screen_h,
            active_window: None,
            drag: None,
        }
    }

    /// Create a new window manager with a custom theme.
    pub fn with_theme(screen_w: u32, screen_h: u32, theme: WmTheme) -> Self {
        Self {
            theme,
            ..Self::new(screen_w, screen_h)
        }
    }

    /// Get a reference to the current theme.
    pub fn theme(&self) -> &WmTheme {
        &self.theme
    }

    /// Get the number of open windows.
    pub fn window_count(&self) -> usize {
        self.windows.len()
    }

    /// Get the active (focused) window id.
    pub fn active_window(&self) -> Option<&str> {
        self.active_window.as_deref()
    }

    /// Get a reference to a window by id.
    pub fn get_window(&self, id: &str) -> Option<&Window> {
        self.windows.iter().find(|w| w.id == id)
    }

    /// Create a new window and register its SDI objects.
    pub fn create_window(
        &mut self,
        config: &WindowConfig,
        sdi: &mut SdiRegistry,
    ) -> Result<WindowId> {
        // Check for duplicate id.
        if self.windows.iter().any(|w| w.id == config.id) {
            return Err(OasisError::Wm(format!(
                "window already exists: {}",
                config.id
            )));
        }

        // Determine initial position.
        let (x, y) = match (config.x, config.y) {
            (Some(x), Some(y)) => (x, y),
            _ => {
                let pos = (self.next_cascade_x, self.next_cascade_y);
                self.advance_cascade();
                pos
            },
        };

        let window = Window::new(config, x, y, &self.theme);

        // Create SDI objects for each component.
        self.create_sdi_objects(&window, sdi);

        let id = window.id.clone();
        self.windows.push(window);

        // Focus the new window.
        self.focus_window_internal(&id, sdi);

        Ok(id)
    }

    /// Close a window, destroying all its SDI objects.
    pub fn close_window(&mut self, id: &str, sdi: &mut SdiRegistry) -> Result<()> {
        let idx = self
            .windows
            .iter()
            .position(|w| w.id == id)
            .ok_or_else(|| OasisError::Wm(format!("window not found: {id}")))?;

        let window = &self.windows[idx];
        self.destroy_sdi_objects(window, sdi);
        self.windows.remove(idx);

        // Cancel any drag on this window.
        if let Some(ref drag) = self.drag {
            let drag_id = match drag {
                DragState::Moving { window_id, .. } => window_id.clone(),
                DragState::Resizing { window_id, .. } => window_id.clone(),
            };
            if drag_id == id {
                self.drag = None;
            }
        }

        // Update active window.
        if self.active_window.as_deref() == Some(id) {
            self.active_window = self.windows.last().map(|w| w.id.clone());
        }

        Ok(())
    }

    /// Move a window by a delta. Updates all SDI object positions.
    pub fn move_window(&mut self, id: &str, dx: i32, dy: i32, sdi: &mut SdiRegistry) -> Result<()> {
        let window = self
            .windows
            .iter_mut()
            .find(|w| w.id == id)
            .ok_or_else(|| OasisError::Wm(format!("window not found: {id}")))?;

        window.x += dx;
        window.y += dy;

        // Update all SDI objects.
        for suffix in window.sdi_suffixes() {
            let name = window.sdi_name(suffix);
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.x += dx;
                obj.y += dy;
            }
        }

        Ok(())
    }

    /// Resize a window to new outer dimensions. Repositions all SDI objects.
    pub fn resize_window(
        &mut self,
        id: &str,
        new_outer_w: u32,
        new_outer_h: u32,
        sdi: &mut SdiRegistry,
    ) -> Result<()> {
        let window = self
            .windows
            .iter_mut()
            .find(|w| w.id == id)
            .ok_or_else(|| OasisError::Wm(format!("window not found: {id}")))?;

        window.outer_w = new_outer_w;
        window.outer_h = new_outer_h;

        // Reposition all SDI objects based on new geometry.
        let win_id = id.to_string();
        self.update_sdi_positions(win_id, sdi);

        Ok(())
    }

    /// Bring a window to the front (topmost z-order).
    pub fn focus_window(&mut self, id: &str, sdi: &mut SdiRegistry) -> Result<()> {
        if !self.windows.iter().any(|w| w.id == id) {
            return Err(OasisError::Wm(format!("window not found: {id}")));
        }
        self.focus_window_internal(id, sdi);
        Ok(())
    }

    /// Minimize a window (hide all SDI objects).
    pub fn minimize_window(&mut self, id: &str, sdi: &mut SdiRegistry) -> Result<()> {
        let window = self
            .windows
            .iter_mut()
            .find(|w| w.id == id)
            .ok_or_else(|| OasisError::Wm(format!("window not found: {id}")))?;

        if !window.has_minimize_button() {
            return Err(OasisError::Wm(format!(
                "window type does not support minimize: {id}"
            )));
        }

        if window.state == WindowState::Normal {
            window.saved_geometry = Some(Geometry {
                x: window.x,
                y: window.y,
                w: window.outer_w,
                h: window.outer_h,
            });
        }
        window.state = WindowState::Minimized;

        // Hide all SDI objects.
        for suffix in window.sdi_suffixes() {
            let name = window.sdi_name(suffix);
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.visible = false;
            }
        }

        // Move focus to next topmost visible window.
        let new_active = self
            .windows
            .iter()
            .rev()
            .find(|w| w.state != WindowState::Minimized && w.id != id)
            .map(|w| w.id.clone());
        self.active_window = new_active;

        Ok(())
    }

    /// Maximize a window to fill the screen.
    pub fn maximize_window(&mut self, id: &str, sdi: &mut SdiRegistry) -> Result<()> {
        let window = self
            .windows
            .iter_mut()
            .find(|w| w.id == id)
            .ok_or_else(|| OasisError::Wm(format!("window not found: {id}")))?;

        if !window.has_maximize_button() {
            return Err(OasisError::Wm(format!(
                "window type does not support maximize: {id}"
            )));
        }

        // Save geometry for restore.
        window.saved_geometry = Some(Geometry {
            x: window.x,
            y: window.y,
            w: window.outer_w,
            h: window.outer_h,
        });

        window.x = 0;
        window.y = 0;
        window.outer_w = self.screen_w;
        window.outer_h = self.screen_h;
        window.state = WindowState::Maximized;

        self.update_sdi_positions(id.to_string(), sdi);

        Ok(())
    }

    /// Restore a window from minimized or maximized state.
    pub fn restore_window(&mut self, id: &str, sdi: &mut SdiRegistry) -> Result<()> {
        let window = self
            .windows
            .iter_mut()
            .find(|w| w.id == id)
            .ok_or_else(|| OasisError::Wm(format!("window not found: {id}")))?;

        let was_minimized = window.state == WindowState::Minimized;

        if let Some(geom) = window.saved_geometry.take() {
            window.x = geom.x;
            window.y = geom.y;
            window.outer_w = geom.w;
            window.outer_h = geom.h;
        }
        window.state = WindowState::Normal;

        if was_minimized {
            // Show all SDI objects.
            for suffix in window.sdi_suffixes() {
                let name = window.sdi_name(suffix);
                if let Ok(obj) = sdi.get_mut(&name) {
                    obj.visible = true;
                }
            }
        }

        self.update_sdi_positions(id.to_string(), sdi);

        Ok(())
    }

    /// Process an input event through the WM. Returns what happened.
    pub fn handle_input(&mut self, event: &InputEvent, sdi: &mut SdiRegistry) -> WmEvent {
        match event {
            InputEvent::PointerClick { x, y } => self.handle_click(*x, *y, sdi),
            InputEvent::CursorMove { x, y } => self.handle_cursor_move(*x, *y, sdi),
            InputEvent::PointerRelease { .. } => self.handle_release(),
            _ => WmEvent::None,
        }
    }

    /// Draw window content with clipping. The caller provides a draw callback
    /// for each window's content. The WM sets up clip rects before each call
    /// and resets them after.
    pub fn draw_with_clips<F>(
        &self,
        sdi: &SdiRegistry,
        backend: &mut dyn SdiBackend,
        mut draw_content: F,
    ) -> Result<()>
    where
        F: FnMut(&str, i32, i32, u32, u32, &mut dyn SdiBackend) -> Result<()>,
    {
        // First draw all SDI objects (frames, titlebars, etc.).
        sdi.draw(backend)?;

        // Then draw clipped content for each visible window.
        for window in &self.windows {
            if window.state == WindowState::Minimized {
                continue;
            }
            let (cx, cy, cw, ch) = window.content_rect(&self.theme);
            if cw == 0 || ch == 0 {
                continue;
            }
            backend.set_clip_rect(cx, cy, cw, ch)?;
            draw_content(&window.id, cx, cy, cw, ch, backend)?;
            backend.reset_clip_rect()?;
        }

        Ok(())
    }

    // -- Internal methods --

    fn handle_click(&mut self, x: i32, y: i32, sdi: &mut SdiRegistry) -> WmEvent {
        let region = hit_test(&self.windows, x, y, &self.theme);

        match region {
            HitRegion::TitlebarButton(id, ButtonKind::Close) => {
                let _ = self.close_window(&id, sdi);
                WmEvent::WindowClosed(id)
            },
            HitRegion::TitlebarButton(id, ButtonKind::Minimize) => {
                let _ = self.minimize_window(&id, sdi);
                WmEvent::WindowMinimized(id)
            },
            HitRegion::TitlebarButton(id, ButtonKind::Maximize) => {
                // Toggle: if maximized, restore; otherwise maximize.
                let is_maximized = self
                    .windows
                    .iter()
                    .find(|w| w.id == id)
                    .map(|w| w.state == WindowState::Maximized)
                    .unwrap_or(false);

                if is_maximized {
                    let _ = self.restore_window(&id, sdi);
                    WmEvent::WindowRestored(id)
                } else {
                    self.focus_window_internal(&id, sdi);
                    let _ = self.maximize_window(&id, sdi);
                    WmEvent::WindowMaximized(id)
                }
            },
            HitRegion::Titlebar(id) => {
                self.focus_window_internal(&id, sdi);
                // Start drag if the window is draggable.
                if let Some(window) = self.windows.iter().find(|w| w.id == id) {
                    if window.is_draggable() {
                        self.drag = Some(DragState::Moving {
                            window_id: id.clone(),
                            start_cursor_x: x,
                            start_cursor_y: y,
                            start_win_x: window.x,
                            start_win_y: window.y,
                        });
                    }
                }
                WmEvent::WindowFocused(id)
            },
            HitRegion::ResizeHandle(id, edge) => {
                self.focus_window_internal(&id, sdi);
                if let Some(window) = self.windows.iter().find(|w| w.id == id) {
                    self.drag = Some(DragState::Resizing {
                        window_id: id.clone(),
                        edge,
                        start_cursor_x: x,
                        start_cursor_y: y,
                        start_geometry: Geometry {
                            x: window.x,
                            y: window.y,
                            w: window.outer_w,
                            h: window.outer_h,
                        },
                    });
                }
                WmEvent::WindowFocused(id)
            },
            HitRegion::Content(id, lx, ly) => {
                self.focus_window_internal(&id, sdi);
                WmEvent::ContentClick(id, lx, ly)
            },
            HitRegion::Desktop => {
                self.active_window = None;
                WmEvent::DesktopClick(x, y)
            },
        }
    }

    fn handle_cursor_move(&mut self, x: i32, y: i32, sdi: &mut SdiRegistry) -> WmEvent {
        let drag = match self.drag.clone() {
            Some(d) => d,
            None => return WmEvent::None,
        };

        match drag {
            DragState::Moving {
                ref window_id,
                start_cursor_x,
                start_cursor_y,
                start_win_x,
                start_win_y,
            } => {
                let new_x = start_win_x + (x - start_cursor_x);
                let new_y = start_win_y + (y - start_cursor_y);

                if let Some(window) = self.windows.iter_mut().find(|w| w.id == *window_id) {
                    let dx = new_x - window.x;
                    let dy = new_y - window.y;
                    window.x = new_x;
                    window.y = new_y;

                    for suffix in window.sdi_suffixes() {
                        let name = window.sdi_name(suffix);
                        if let Ok(obj) = sdi.get_mut(&name) {
                            obj.x += dx;
                            obj.y += dy;
                        }
                    }
                }
                WmEvent::WindowMoved(window_id.clone())
            },
            DragState::Resizing {
                ref window_id,
                edge,
                start_cursor_x,
                start_cursor_y,
                start_geometry,
            } => {
                let dx = x - start_cursor_x;
                let dy = y - start_cursor_y;

                let (new_x, new_y, new_w, new_h) =
                    compute_resize(start_geometry, edge, dx, dy, &self.theme);

                if let Some(window) = self.windows.iter_mut().find(|w| w.id == *window_id) {
                    window.x = new_x;
                    window.y = new_y;
                    window.outer_w = new_w;
                    window.outer_h = new_h;
                }

                self.update_sdi_positions(window_id.clone(), sdi);
                WmEvent::WindowResized(window_id.clone())
            },
        }
    }

    fn handle_release(&mut self) -> WmEvent {
        if let Some(drag) = self.drag.take() {
            let id = match drag {
                DragState::Moving { window_id, .. } => window_id,
                DragState::Resizing { window_id, .. } => window_id,
            };
            return WmEvent::WindowMoved(id);
        }
        WmEvent::None
    }

    /// Move a window to the top of the z-order list and update SDI z-ordering.
    fn focus_window_internal(&mut self, id: &str, sdi: &mut SdiRegistry) {
        if let Some(idx) = self.windows.iter().position(|w| w.id == id) {
            let window = self.windows.remove(idx);
            self.windows.push(window);
        }

        // Update SDI z-ordering: move all objects of this window to top.
        if let Some(window) = self.windows.last() {
            for suffix in window.sdi_suffixes() {
                let name = window.sdi_name(suffix);
                let _ = sdi.move_to_top(&name);
            }
        }

        // Update titlebar colors for all windows.
        for (i, window) in self.windows.iter().enumerate() {
            let is_active = i == self.windows.len() - 1;
            let color = if is_active {
                self.theme.titlebar_active_color
            } else {
                self.theme.titlebar_inactive_color
            };
            let tb_name = window.sdi_name("titlebar");
            if let Ok(obj) = sdi.get_mut(&tb_name) {
                obj.color = color;
            }
        }

        self.active_window = Some(id.to_string());
    }

    /// Create all SDI objects for a window.
    fn create_sdi_objects(&self, window: &Window, sdi: &mut SdiRegistry) {
        let theme = &self.theme;

        // Frame (background).
        if window.sdi_suffixes().contains(&"frame") {
            let obj = sdi.create(window.sdi_name("frame"));
            obj.x = window.x;
            obj.y = window.y;
            obj.w = window.outer_w;
            obj.h = window.outer_h;
            obj.color = theme.frame_color;
        }

        // Titlebar.
        if let Some((tx, ty, tw, th)) = window.titlebar_rect(theme) {
            if window.sdi_suffixes().contains(&"titlebar") {
                let obj = sdi.create(window.sdi_name("titlebar"));
                obj.x = tx;
                obj.y = ty;
                obj.w = tw;
                obj.h = th;
                obj.color = theme.titlebar_active_color;
            }

            // Title text.
            if window.sdi_suffixes().contains(&"title_text") {
                let obj = sdi.create(window.sdi_name("title_text"));
                obj.x = tx + 4;
                obj.y = ty + 2;
                obj.w = tw.saturating_sub(8);
                obj.h = th;
                obj.text = Some(window.title.clone());
                obj.font_size = theme.titlebar_font_size;
                obj.text_color = theme.titlebar_text_color;
                obj.color = Color::rgba(0, 0, 0, 0); // Transparent bg.
            }
        }

        // Close button.
        if let Some((bx, by, bw, bh)) = window.close_btn_rect(theme) {
            let obj = sdi.create(window.sdi_name("btn_close"));
            obj.x = bx;
            obj.y = by;
            obj.w = bw;
            obj.h = bh;
            obj.color = theme.btn_close_color;
        }

        // Minimize button.
        if let Some((bx, by, bw, bh)) = window.minimize_btn_rect(theme) {
            let obj = sdi.create(window.sdi_name("btn_minimize"));
            obj.x = bx;
            obj.y = by;
            obj.w = bw;
            obj.h = bh;
            obj.color = theme.btn_minimize_color;
        }

        // Maximize button.
        if let Some((bx, by, bw, bh)) = window.maximize_btn_rect(theme) {
            let obj = sdi.create(window.sdi_name("btn_maximize"));
            obj.x = bx;
            obj.y = by;
            obj.w = bw;
            obj.h = bh;
            obj.color = theme.btn_maximize_color;
        }

        // Content area.
        {
            let (cx, cy, cw, ch) = window.content_rect(theme);
            let obj = sdi.create(window.sdi_name("content"));
            obj.x = cx;
            obj.y = cy;
            obj.w = cw;
            obj.h = ch;
            obj.color = theme.content_bg_color;
        }
    }

    /// Destroy all SDI objects for a window.
    fn destroy_sdi_objects(&self, window: &Window, sdi: &mut SdiRegistry) {
        for suffix in window.sdi_suffixes() {
            let name = window.sdi_name(suffix);
            let _ = sdi.destroy(&name);
        }
    }

    /// Reposition all SDI objects based on window's current geometry.
    fn update_sdi_positions(&self, id: WindowId, sdi: &mut SdiRegistry) {
        let window = match self.windows.iter().find(|w| w.id == id) {
            Some(w) => w,
            None => return,
        };

        let theme = &self.theme;

        // Frame.
        if let Ok(obj) = sdi.get_mut(&window.sdi_name("frame")) {
            obj.x = window.x;
            obj.y = window.y;
            obj.w = window.outer_w;
            obj.h = window.outer_h;
        }

        // Titlebar.
        if let Some((tx, ty, tw, th)) = window.titlebar_rect(theme) {
            if let Ok(obj) = sdi.get_mut(&window.sdi_name("titlebar")) {
                obj.x = tx;
                obj.y = ty;
                obj.w = tw;
                obj.h = th;
            }
            if let Ok(obj) = sdi.get_mut(&window.sdi_name("title_text")) {
                obj.x = tx + 4;
                obj.y = ty + 2;
                obj.w = tw.saturating_sub(8);
                obj.h = th;
            }
        }

        // Buttons.
        if let Some((bx, by, bw, bh)) = window.close_btn_rect(theme) {
            if let Ok(obj) = sdi.get_mut(&window.sdi_name("btn_close")) {
                obj.x = bx;
                obj.y = by;
                obj.w = bw;
                obj.h = bh;
            }
        }
        if let Some((bx, by, bw, bh)) = window.minimize_btn_rect(theme) {
            if let Ok(obj) = sdi.get_mut(&window.sdi_name("btn_minimize")) {
                obj.x = bx;
                obj.y = by;
                obj.w = bw;
                obj.h = bh;
            }
        }
        if let Some((bx, by, bw, bh)) = window.maximize_btn_rect(theme) {
            if let Ok(obj) = sdi.get_mut(&window.sdi_name("btn_maximize")) {
                obj.x = bx;
                obj.y = by;
                obj.w = bw;
                obj.h = bh;
            }
        }

        // Content.
        let (cx, cy, cw, ch) = window.content_rect(theme);
        if let Ok(obj) = sdi.get_mut(&window.sdi_name("content")) {
            obj.x = cx;
            obj.y = cy;
            obj.w = cw;
            obj.h = ch;
        }
    }

    /// Advance the cascade position for the next window.
    fn advance_cascade(&mut self) {
        self.next_cascade_x += CASCADE_OFFSET;
        self.next_cascade_y += CASCADE_OFFSET;

        // Wrap when we get close to the screen edge.
        if self.next_cascade_x > self.screen_w as i32 / 2 {
            self.next_cascade_x = CASCADE_OFFSET;
        }
        if self.next_cascade_y > self.screen_h as i32 / 2 {
            self.next_cascade_y = CASCADE_OFFSET;
        }
    }
}

/// Compute new geometry after a resize drag.
fn compute_resize(
    start: Geometry,
    edge: ResizeEdge,
    dx: i32,
    dy: i32,
    theme: &WmTheme,
) -> (i32, i32, u32, u32) {
    let min_w = MIN_WINDOW_SIZE + theme.border_width * 2;
    let min_h = MIN_WINDOW_SIZE + theme.titlebar_height + theme.border_width * 2;

    let mut x = start.x;
    let mut y = start.y;
    let mut w = start.w;
    let mut h = start.h;

    match edge {
        ResizeEdge::East => {
            w = (start.w as i32 + dx).max(min_w as i32) as u32;
        },
        ResizeEdge::West => {
            let new_w = (start.w as i32 - dx).max(min_w as i32) as u32;
            x = start.x + (start.w as i32 - new_w as i32);
            w = new_w;
        },
        ResizeEdge::South => {
            h = (start.h as i32 + dy).max(min_h as i32) as u32;
        },
        ResizeEdge::North => {
            let new_h = (start.h as i32 - dy).max(min_h as i32) as u32;
            y = start.y + (start.h as i32 - new_h as i32);
            h = new_h;
        },
        ResizeEdge::SouthEast => {
            w = (start.w as i32 + dx).max(min_w as i32) as u32;
            h = (start.h as i32 + dy).max(min_h as i32) as u32;
        },
        ResizeEdge::SouthWest => {
            let new_w = (start.w as i32 - dx).max(min_w as i32) as u32;
            x = start.x + (start.w as i32 - new_w as i32);
            w = new_w;
            h = (start.h as i32 + dy).max(min_h as i32) as u32;
        },
        ResizeEdge::NorthEast => {
            w = (start.w as i32 + dx).max(min_w as i32) as u32;
            let new_h = (start.h as i32 - dy).max(min_h as i32) as u32;
            y = start.y + (start.h as i32 - new_h as i32);
            h = new_h;
        },
        ResizeEdge::NorthWest => {
            let new_w = (start.w as i32 - dx).max(min_w as i32) as u32;
            x = start.x + (start.w as i32 - new_w as i32);
            w = new_w;
            let new_h = (start.h as i32 - dy).max(min_h as i32) as u32;
            y = start.y + (start.h as i32 - new_h as i32);
            h = new_h;
        },
    }

    (x, y, w, h)
}

use crate::backend::Color;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::wm::window::WindowType;

    fn app_config(id: &str) -> WindowConfig {
        WindowConfig {
            id: id.to_string(),
            title: id.to_string(),
            x: Some(10),
            y: Some(10),
            width: 200,
            height: 150,
            window_type: WindowType::AppWindow,
        }
    }

    fn dialog_config(id: &str) -> WindowConfig {
        WindowConfig {
            id: id.to_string(),
            title: id.to_string(),
            x: Some(50),
            y: Some(50),
            width: 200,
            height: 100,
            window_type: WindowType::Dialog,
        }
    }

    #[test]
    fn create_window_adds_sdi_objects() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        assert!(sdi.contains("w1.frame"));
        assert!(sdi.contains("w1.titlebar"));
        assert!(sdi.contains("w1.title_text"));
        assert!(sdi.contains("w1.btn_close"));
        assert!(sdi.contains("w1.btn_minimize"));
        assert!(sdi.contains("w1.btn_maximize"));
        assert!(sdi.contains("w1.content"));
        assert_eq!(wm.window_count(), 1);
    }

    #[test]
    fn create_duplicate_id_fails() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();
        assert!(wm.create_window(&app_config("w1"), &mut sdi).is_err());
    }

    #[test]
    fn close_window_removes_sdi_objects() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();
        wm.close_window("w1", &mut sdi).unwrap();

        assert!(!sdi.contains("w1.frame"));
        assert!(!sdi.contains("w1.titlebar"));
        assert!(!sdi.contains("w1.content"));
        assert_eq!(wm.window_count(), 0);
    }

    #[test]
    fn close_nonexistent_fails() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        assert!(wm.close_window("nope", &mut sdi).is_err());
    }

    #[test]
    fn move_window_updates_positions() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        let orig_x = sdi.get("w1.frame").unwrap().x;
        let orig_y = sdi.get("w1.frame").unwrap().y;

        wm.move_window("w1", 50, 30, &mut sdi).unwrap();

        assert_eq!(sdi.get("w1.frame").unwrap().x, orig_x + 50);
        assert_eq!(sdi.get("w1.frame").unwrap().y, orig_y + 30);
        assert_eq!(
            sdi.get("w1.content").unwrap().x - 50,
            sdi.get("w1.content").unwrap().x - 50
        );
    }

    #[test]
    fn focus_reorders_windows() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();
        wm.create_window(&app_config("w2"), &mut sdi).unwrap();

        // w2 is on top after creation.
        assert_eq!(wm.active_window(), Some("w2"));

        // Focus w1.
        wm.focus_window("w1", &mut sdi).unwrap();
        assert_eq!(wm.active_window(), Some("w1"));
    }

    #[test]
    fn minimize_hides_objects() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        wm.minimize_window("w1", &mut sdi).unwrap();

        assert!(!sdi.get("w1.frame").unwrap().visible);
        assert!(!sdi.get("w1.content").unwrap().visible);
        assert_eq!(wm.get_window("w1").unwrap().state, WindowState::Minimized);
    }

    #[test]
    fn maximize_fills_screen() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        wm.maximize_window("w1", &mut sdi).unwrap();

        let win = wm.get_window("w1").unwrap();
        assert_eq!(win.outer_w, 800);
        assert_eq!(win.outer_h, 600);
        assert_eq!(win.x, 0);
        assert_eq!(win.y, 0);
        assert_eq!(win.state, WindowState::Maximized);
    }

    #[test]
    fn restore_from_maximized() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        let orig = wm.get_window("w1").unwrap();
        let orig_x = orig.x;
        let orig_w = orig.outer_w;

        wm.maximize_window("w1", &mut sdi).unwrap();
        wm.restore_window("w1", &mut sdi).unwrap();

        let restored = wm.get_window("w1").unwrap();
        assert_eq!(restored.x, orig_x);
        assert_eq!(restored.outer_w, orig_w);
        assert_eq!(restored.state, WindowState::Normal);
    }

    #[test]
    fn restore_from_minimized_shows_objects() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        wm.minimize_window("w1", &mut sdi).unwrap();
        assert!(!sdi.get("w1.frame").unwrap().visible);

        wm.restore_window("w1", &mut sdi).unwrap();
        assert!(sdi.get("w1.frame").unwrap().visible);
        assert!(sdi.get("w1.content").unwrap().visible);
    }

    #[test]
    fn click_content_returns_local_coords() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        let (cx, cy, _cw, _ch) = wm.get_window("w1").unwrap().content_rect(&wm.theme);
        let event = InputEvent::PointerClick {
            x: cx + 10,
            y: cy + 20,
        };
        let result = wm.handle_input(&event, &mut sdi);
        assert_eq!(result, WmEvent::ContentClick("w1".to_string(), 10, 20));
    }

    #[test]
    fn click_desktop_returns_desktop_event() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        let event = InputEvent::PointerClick { x: 700, y: 500 };
        let result = wm.handle_input(&event, &mut sdi);
        assert_eq!(result, WmEvent::DesktopClick(700, 500));
    }

    #[test]
    fn click_close_button_closes_window() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        let win = wm.get_window("w1").unwrap();
        let (bx, by, bw, bh) = win.close_btn_rect(&wm.theme).unwrap();
        let event = InputEvent::PointerClick {
            x: bx + bw as i32 / 2,
            y: by + bh as i32 / 2,
        };
        let result = wm.handle_input(&event, &mut sdi);
        assert_eq!(result, WmEvent::WindowClosed("w1".to_string()));
        assert_eq!(wm.window_count(), 0);
    }

    #[test]
    fn drag_moves_window() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        let win = wm.get_window("w1").unwrap();
        let (tx, ty, _tw, th) = win.titlebar_rect(&wm.theme).unwrap();
        let orig_x = win.x;
        let orig_y = win.y;

        // Click on titlebar.
        wm.handle_input(
            &InputEvent::PointerClick {
                x: tx + 5,
                y: ty + th as i32 / 2,
            },
            &mut sdi,
        );

        // Drag.
        wm.handle_input(
            &InputEvent::CursorMove {
                x: tx + 55,
                y: ty + th as i32 / 2 + 30,
            },
            &mut sdi,
        );

        let win = wm.get_window("w1").unwrap();
        assert_eq!(win.x, orig_x + 50);
        assert_eq!(win.y, orig_y + 30);

        // Release.
        wm.handle_input(&InputEvent::PointerRelease { x: 0, y: 0 }, &mut sdi);
        assert!(wm.drag.is_none());
    }

    #[test]
    fn resize_east() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();

        let win = wm.get_window("w1").unwrap();
        let orig_w = win.outer_w;
        let right_edge = win.x + win.outer_w as i32 - 2;
        let mid_y = win.y + win.outer_h as i32 / 2;

        // Click on east resize handle.
        wm.handle_input(
            &InputEvent::PointerClick {
                x: right_edge,
                y: mid_y,
            },
            &mut sdi,
        );

        // Drag east by 40px.
        wm.handle_input(
            &InputEvent::CursorMove {
                x: right_edge + 40,
                y: mid_y,
            },
            &mut sdi,
        );

        let win = wm.get_window("w1").unwrap();
        assert_eq!(win.outer_w, orig_w + 40);

        wm.handle_input(&InputEvent::PointerRelease { x: 0, y: 0 }, &mut sdi);
    }

    #[test]
    fn cascade_positions_offset() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);

        let config1 = WindowConfig {
            id: "a".to_string(),
            title: "A".to_string(),
            x: None,
            y: None,
            width: 100,
            height: 80,
            window_type: WindowType::AppWindow,
        };
        let config2 = WindowConfig {
            id: "b".to_string(),
            title: "B".to_string(),
            x: None,
            y: None,
            width: 100,
            height: 80,
            window_type: WindowType::AppWindow,
        };

        wm.create_window(&config1, &mut sdi).unwrap();
        wm.create_window(&config2, &mut sdi).unwrap();

        let a = wm.get_window("a").unwrap();
        let b = wm.get_window("b").unwrap();
        assert_eq!(b.x - a.x, CASCADE_OFFSET);
        assert_eq!(b.y - a.y, CASCADE_OFFSET);
    }

    #[test]
    fn dialog_cannot_minimize() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&dialog_config("dlg"), &mut sdi).unwrap();
        assert!(wm.minimize_window("dlg", &mut sdi).is_err());
    }

    #[test]
    fn dialog_cannot_maximize() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&dialog_config("dlg"), &mut sdi).unwrap();
        assert!(wm.maximize_window("dlg", &mut sdi).is_err());
    }

    #[test]
    fn titlebar_active_inactive_colors() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();
        wm.create_window(&app_config("w2"), &mut sdi).unwrap();

        // w2 is active, w1 is inactive.
        let w1_tb = sdi.get("w1.titlebar").unwrap().color;
        let w2_tb = sdi.get("w2.titlebar").unwrap().color;
        assert_eq!(w2_tb, wm.theme.titlebar_active_color);
        assert_eq!(w1_tb, wm.theme.titlebar_inactive_color);

        // Focus w1.
        wm.focus_window("w1", &mut sdi).unwrap();
        let w1_tb = sdi.get("w1.titlebar").unwrap().color;
        let w2_tb = sdi.get("w2.titlebar").unwrap().color;
        assert_eq!(w1_tb, wm.theme.titlebar_active_color);
        assert_eq!(w2_tb, wm.theme.titlebar_inactive_color);
    }

    #[test]
    fn close_updates_active_to_next_topmost() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();
        wm.create_window(&app_config("w2"), &mut sdi).unwrap();

        // Close w2 (active).
        wm.close_window("w2", &mut sdi).unwrap();
        assert_eq!(wm.active_window(), Some("w1"));
    }

    #[test]
    fn minimize_updates_active() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        wm.create_window(&app_config("w1"), &mut sdi).unwrap();
        wm.create_window(&app_config("w2"), &mut sdi).unwrap();

        wm.minimize_window("w2", &mut sdi).unwrap();
        assert_eq!(wm.active_window(), Some("w1"));
    }

    #[test]
    fn fullscreen_window_creates_only_content() {
        let mut sdi = SdiRegistry::new();
        let mut wm = WindowManager::new(800, 600);
        let config = WindowConfig {
            id: "fs".to_string(),
            title: "Full".to_string(),
            x: Some(0),
            y: Some(0),
            width: 800,
            height: 600,
            window_type: WindowType::Fullscreen,
        };
        wm.create_window(&config, &mut sdi).unwrap();

        assert!(sdi.contains("fs.content"));
        assert!(!sdi.contains("fs.frame"));
        assert!(!sdi.contains("fs.titlebar"));
    }

    #[test]
    fn resize_respects_minimum_size() {
        let theme = WmTheme::default();
        let start = Geometry {
            x: 0,
            y: 0,
            w: 100,
            h: 100,
        };
        // Try shrinking way past minimum.
        let (_, _, w, h) = compute_resize(start, ResizeEdge::SouthEast, -200, -200, &theme);
        let min_w = MIN_WINDOW_SIZE + theme.border_width * 2;
        let min_h = MIN_WINDOW_SIZE + theme.titlebar_height + theme.border_width * 2;
        assert_eq!(w, min_w);
        assert_eq!(h, min_h);
    }

    #[test]
    fn with_theme_constructor() {
        let theme = WmTheme {
            titlebar_height: 32,
            ..WmTheme::default()
        };
        let wm = WindowManager::with_theme(800, 600, theme);
        assert_eq!(wm.theme().titlebar_height, 32);
    }
}
