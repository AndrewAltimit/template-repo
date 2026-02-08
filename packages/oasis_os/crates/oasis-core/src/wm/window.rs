//! Window types and configuration for the window manager.
//!
//! The WM is a consumer of the SDI API. Each `Window` owns a group of SDI
//! objects identified by a naming convention: `"{id}.frame"`, `"{id}.titlebar"`,
//! etc. The WM handles behavior; the skin handles appearance.

use crate::backend::Color;

/// Unique window identifier (also the SDI object name prefix).
pub type WindowId = String;

/// The behavioral template of a window.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WindowType {
    /// Draggable, resizable, closable, minimizable, maximizable.
    AppWindow,
    /// Modal, centered, blocks input to other windows.
    Dialog,
    /// Docked to a screen edge, not freely draggable.
    Panel,
    /// Small, always-on-top, draggable, no minimize/maximize.
    FloatingWidget,
    /// No frame, no titlebar, covers entire content area.
    Fullscreen,
}

/// Current display state of a window.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WindowState {
    Normal,
    Minimized,
    Maximized,
}

/// Configuration for creating a new window.
#[derive(Debug, Clone)]
pub struct WindowConfig {
    /// Unique identifier (becomes the SDI object name prefix).
    pub id: String,
    /// Window title displayed in the titlebar.
    pub title: String,
    /// Initial X position. If `None`, the WM cascades automatically.
    pub x: Option<i32>,
    /// Initial Y position. If `None`, the WM cascades automatically.
    pub y: Option<i32>,
    /// Content area width.
    pub width: u32,
    /// Content area height.
    pub height: u32,
    /// Window type (determines available operations).
    pub window_type: WindowType,
}

/// Visual theme parameters for window rendering.
///
/// In Phase 7 these are hardcoded defaults. Phase 8 (skin system) will
/// populate these from the active skin's configuration.
#[derive(Debug, Clone)]
pub struct WmTheme {
    /// Titlebar height in pixels.
    pub titlebar_height: u32,
    /// Frame border width in pixels.
    pub border_width: u32,
    /// Titlebar background color (active window).
    pub titlebar_active_color: Color,
    /// Titlebar background color (inactive window).
    pub titlebar_inactive_color: Color,
    /// Titlebar text color.
    pub titlebar_text_color: Color,
    /// Frame/border color.
    pub frame_color: Color,
    /// Content area background color.
    pub content_bg_color: Color,
    /// Close button color.
    pub btn_close_color: Color,
    /// Minimize button color.
    pub btn_minimize_color: Color,
    /// Maximize button color.
    pub btn_maximize_color: Color,
    /// Button size (square, width = height).
    pub button_size: u32,
    /// Resize handle hit area size in pixels.
    pub resize_handle_size: u32,
    /// Font size for titlebar text.
    pub titlebar_font_size: u16,
}

impl Default for WmTheme {
    fn default() -> Self {
        Self {
            titlebar_height: 24,
            border_width: 1,
            titlebar_active_color: Color::rgb(50, 80, 140),
            titlebar_inactive_color: Color::rgb(80, 80, 80),
            titlebar_text_color: Color::WHITE,
            frame_color: Color::rgb(40, 40, 40),
            content_bg_color: Color::rgb(30, 30, 30),
            btn_close_color: Color::rgb(200, 60, 60),
            btn_minimize_color: Color::rgb(200, 180, 60),
            btn_maximize_color: Color::rgb(60, 180, 60),
            button_size: 16,
            resize_handle_size: 6,
            titlebar_font_size: 12,
        }
    }
}

/// Stored geometry for restore-from-maximize.
#[derive(Debug, Clone, Copy)]
pub struct Geometry {
    pub x: i32,
    pub y: i32,
    pub w: u32,
    pub h: u32,
}

/// A managed window in the WM.
///
/// Tracks the window's metadata, geometry, state, and the names of its
/// SDI child objects. The WM manipulates the SDI registry through these names.
#[derive(Debug, Clone)]
pub struct Window {
    /// Unique identifier (SDI name prefix).
    pub id: WindowId,
    /// Display title.
    pub title: String,
    /// Window type.
    pub window_type: WindowType,
    /// Current state.
    pub state: WindowState,
    /// Position of the window's outer frame (top-left).
    pub x: i32,
    /// Position of the window's outer frame (top-left).
    pub y: i32,
    /// Total outer width (including borders).
    pub outer_w: u32,
    /// Total outer height (including borders and titlebar).
    pub outer_h: u32,
    /// Saved geometry for restoring from maximized state.
    pub saved_geometry: Option<Geometry>,
}

impl Window {
    /// Create a new window from configuration and theme.
    pub fn new(config: &WindowConfig, x: i32, y: i32, theme: &WmTheme) -> Self {
        let has_titlebar = config.window_type != WindowType::Fullscreen;
        let has_border = matches!(
            config.window_type,
            WindowType::AppWindow | WindowType::Dialog
        );

        let border = if has_border { theme.border_width } else { 0 };
        let titlebar_h = if has_titlebar {
            theme.titlebar_height
        } else {
            0
        };

        let outer_w = config.width + border * 2;
        let outer_h = config.height + titlebar_h + border * 2;

        Self {
            id: config.id.clone(),
            title: config.title.clone(),
            window_type: config.window_type,
            state: WindowState::Normal,
            x,
            y,
            outer_w,
            outer_h,
            saved_geometry: None,
        }
    }

    /// Compute the content area rectangle (position and size within the frame).
    pub fn content_rect(&self, theme: &WmTheme) -> (i32, i32, u32, u32) {
        let has_titlebar = self.window_type != WindowType::Fullscreen;
        let has_border = matches!(self.window_type, WindowType::AppWindow | WindowType::Dialog);

        let border = if has_border { theme.border_width } else { 0 };
        let titlebar_h = if has_titlebar {
            theme.titlebar_height
        } else {
            0
        };

        let cx = self.x + border as i32;
        let cy = self.y + titlebar_h as i32 + border as i32;
        let cw = self.outer_w.saturating_sub(border * 2);
        let ch = self
            .outer_h
            .saturating_sub(titlebar_h)
            .saturating_sub(border * 2);
        (cx, cy, cw, ch)
    }

    /// Compute the titlebar rectangle.
    pub fn titlebar_rect(&self, theme: &WmTheme) -> Option<(i32, i32, u32, u32)> {
        if self.window_type == WindowType::Fullscreen {
            return None;
        }
        let has_border = matches!(self.window_type, WindowType::AppWindow | WindowType::Dialog);
        let border = if has_border { theme.border_width } else { 0 };

        let tx = self.x + border as i32;
        let ty = self.y + border as i32;
        let tw = self.outer_w.saturating_sub(border * 2);
        let th = theme.titlebar_height;
        Some((tx, ty, tw, th))
    }

    /// Compute close button rectangle (top-right of titlebar).
    pub fn close_btn_rect(&self, theme: &WmTheme) -> Option<(i32, i32, u32, u32)> {
        let (tx, ty, tw, th) = self.titlebar_rect(theme)?;
        if !self.has_close_button() {
            return None;
        }
        let btn_size = theme.button_size.min(th);
        let bx = tx + tw as i32 - btn_size as i32 - 2;
        let by = ty + (th as i32 - btn_size as i32) / 2;
        Some((bx, by, btn_size, btn_size))
    }

    /// Compute minimize button rectangle (left of close).
    pub fn minimize_btn_rect(&self, theme: &WmTheme) -> Option<(i32, i32, u32, u32)> {
        let (tx, ty, tw, th) = self.titlebar_rect(theme)?;
        if !self.has_minimize_button() {
            return None;
        }
        let btn_size = theme.button_size.min(th);
        // Position: 2 buttons from the right edge (close is rightmost).
        let bx = tx + tw as i32 - (btn_size as i32) * 2 - 4;
        let by = ty + (th as i32 - btn_size as i32) / 2;
        Some((bx, by, btn_size, btn_size))
    }

    /// Compute maximize button rectangle (between minimize and close).
    pub fn maximize_btn_rect(&self, theme: &WmTheme) -> Option<(i32, i32, u32, u32)> {
        let (tx, ty, tw, th) = self.titlebar_rect(theme)?;
        if !self.has_maximize_button() {
            return None;
        }
        let btn_size = theme.button_size.min(th);
        // Position: 3 buttons from the right edge.
        let bx = tx + tw as i32 - (btn_size as i32) * 3 - 6;
        let by = ty + (th as i32 - btn_size as i32) / 2;
        Some((bx, by, btn_size, btn_size))
    }

    /// Whether this window type has a close button.
    pub fn has_close_button(&self) -> bool {
        matches!(
            self.window_type,
            WindowType::AppWindow | WindowType::Dialog | WindowType::FloatingWidget
        )
    }

    /// Whether this window type has a minimize button.
    pub fn has_minimize_button(&self) -> bool {
        self.window_type == WindowType::AppWindow
    }

    /// Whether this window type has a maximize button.
    pub fn has_maximize_button(&self) -> bool {
        self.window_type == WindowType::AppWindow
    }

    /// Whether this window type is resizable.
    pub fn is_resizable(&self) -> bool {
        self.window_type == WindowType::AppWindow
    }

    /// Whether this window type is draggable.
    pub fn is_draggable(&self) -> bool {
        matches!(
            self.window_type,
            WindowType::AppWindow | WindowType::FloatingWidget
        )
    }

    /// The list of SDI object suffixes this window creates.
    pub fn sdi_suffixes(&self) -> Vec<&'static str> {
        match self.window_type {
            WindowType::Fullscreen => vec!["content"],
            WindowType::FloatingWidget => {
                vec!["frame", "titlebar", "title_text", "btn_close", "content"]
            },
            WindowType::Panel => vec!["frame", "titlebar", "title_text", "content"],
            WindowType::Dialog => vec!["frame", "titlebar", "title_text", "btn_close", "content"],
            WindowType::AppWindow => vec![
                "frame",
                "titlebar",
                "title_text",
                "btn_close",
                "btn_minimize",
                "btn_maximize",
                "content",
            ],
        }
    }

    /// Build the full SDI object name for a suffix.
    pub fn sdi_name(&self, suffix: &str) -> String {
        format!("{}.{suffix}", self.id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> WindowConfig {
        WindowConfig {
            id: "test_win".to_string(),
            title: "Test Window".to_string(),
            x: None,
            y: None,
            width: 200,
            height: 150,
            window_type: WindowType::AppWindow,
        }
    }

    #[test]
    fn window_new_computes_outer_dimensions() {
        let theme = WmTheme::default();
        let config = test_config();
        let win = Window::new(&config, 10, 20, &theme);
        // outer_w = content_w + 2*border = 200 + 2 = 202
        assert_eq!(win.outer_w, 200 + theme.border_width * 2);
        // outer_h = content_h + titlebar + 2*border = 150 + 24 + 2 = 176
        assert_eq!(
            win.outer_h,
            150 + theme.titlebar_height + theme.border_width * 2
        );
    }

    #[test]
    fn fullscreen_has_no_border_or_titlebar() {
        let theme = WmTheme::default();
        let config = WindowConfig {
            id: "fs".to_string(),
            title: "Full".to_string(),
            x: None,
            y: None,
            width: 480,
            height: 272,
            window_type: WindowType::Fullscreen,
        };
        let win = Window::new(&config, 0, 0, &theme);
        assert_eq!(win.outer_w, 480);
        assert_eq!(win.outer_h, 272);
        assert!(win.titlebar_rect(&theme).is_none());
    }

    #[test]
    fn content_rect_app_window() {
        let theme = WmTheme::default();
        let config = test_config();
        let win = Window::new(&config, 10, 20, &theme);
        let (cx, cy, cw, ch) = win.content_rect(&theme);
        assert_eq!(cx, 10 + theme.border_width as i32);
        assert_eq!(
            cy,
            20 + theme.titlebar_height as i32 + theme.border_width as i32
        );
        assert_eq!(cw, 200);
        assert_eq!(ch, 150);
    }

    #[test]
    fn titlebar_rect_inside_border() {
        let theme = WmTheme::default();
        let config = test_config();
        let win = Window::new(&config, 10, 20, &theme);
        let (tx, ty, tw, th) = win.titlebar_rect(&theme).unwrap();
        assert_eq!(tx, 10 + theme.border_width as i32);
        assert_eq!(ty, 20 + theme.border_width as i32);
        assert_eq!(tw, 200); // outer_w - 2*border
        assert_eq!(th, theme.titlebar_height);
    }

    #[test]
    fn close_button_top_right() {
        let theme = WmTheme::default();
        let config = test_config();
        let win = Window::new(&config, 0, 0, &theme);
        let (bx, _by, bw, _bh) = win.close_btn_rect(&theme).unwrap();
        let (tx, _ty, tw, _th) = win.titlebar_rect(&theme).unwrap();
        // Close button is near the right edge of the titlebar.
        assert!(bx + bw as i32 <= tx + tw as i32);
        assert!(bx > tx + tw as i32 / 2); // Right half.
    }

    #[test]
    fn dialog_has_no_minimize_maximize() {
        let theme = WmTheme::default();
        let config = WindowConfig {
            id: "dlg".to_string(),
            title: "Dialog".to_string(),
            x: None,
            y: None,
            width: 300,
            height: 100,
            window_type: WindowType::Dialog,
        };
        let win = Window::new(&config, 0, 0, &theme);
        assert!(win.has_close_button());
        assert!(!win.has_minimize_button());
        assert!(!win.has_maximize_button());
        assert!(!win.is_resizable());
    }

    #[test]
    fn floating_widget_draggable_no_resize() {
        let theme = WmTheme::default();
        let config = WindowConfig {
            id: "widget".to_string(),
            title: "Clock".to_string(),
            x: None,
            y: None,
            width: 80,
            height: 40,
            window_type: WindowType::FloatingWidget,
        };
        let win = Window::new(&config, 0, 0, &theme);
        assert!(win.is_draggable());
        assert!(!win.is_resizable());
        assert!(win.has_close_button());
        assert!(!win.has_minimize_button());
    }

    #[test]
    fn sdi_suffixes_by_type() {
        let theme = WmTheme::default();
        let config = test_config();
        let win = Window::new(&config, 0, 0, &theme);
        let suffixes = win.sdi_suffixes();
        assert!(suffixes.contains(&"frame"));
        assert!(suffixes.contains(&"titlebar"));
        assert!(suffixes.contains(&"btn_close"));
        assert!(suffixes.contains(&"btn_minimize"));
        assert!(suffixes.contains(&"btn_maximize"));
        assert!(suffixes.contains(&"content"));
    }

    #[test]
    fn sdi_name_formatting() {
        let theme = WmTheme::default();
        let config = test_config();
        let win = Window::new(&config, 0, 0, &theme);
        assert_eq!(win.sdi_name("frame"), "test_win.frame");
        assert_eq!(win.sdi_name("titlebar"), "test_win.titlebar");
    }

    #[test]
    fn panel_not_draggable() {
        let config = WindowConfig {
            id: "taskbar".to_string(),
            title: "Taskbar".to_string(),
            x: None,
            y: None,
            width: 480,
            height: 32,
            window_type: WindowType::Panel,
        };
        let theme = WmTheme::default();
        let win = Window::new(&config, 0, 0, &theme);
        assert!(!win.is_draggable());
        assert!(!win.is_resizable());
        assert!(!win.has_close_button());
    }

    #[test]
    fn default_theme_reasonable() {
        let theme = WmTheme::default();
        assert!(theme.titlebar_height > 0);
        assert!(theme.button_size > 0);
        assert!(theme.button_size <= theme.titlebar_height);
        assert!(theme.resize_handle_size > 0);
    }
}
