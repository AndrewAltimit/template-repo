//! Window manager hit testing.
//!
//! When a pointer click arrives, the WM walks windows in reverse z-order
//! (topmost first) and checks regions in priority order:
//! titlebar buttons > titlebar body > resize handles > content > desktop.

use super::window::{Window, WindowId, WindowState, WmTheme};

/// Which titlebar button was hit.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ButtonKind {
    Close,
    Minimize,
    Maximize,
}

/// Which resize edge or corner was hit.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResizeEdge {
    North,
    South,
    East,
    West,
    NorthEast,
    NorthWest,
    SouthEast,
    SouthWest,
}

/// The result of a hit test.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum HitRegion {
    /// A titlebar button was clicked.
    TitlebarButton(WindowId, ButtonKind),
    /// The titlebar body was clicked (initiates drag).
    Titlebar(WindowId),
    /// A resize handle was clicked.
    ResizeHandle(WindowId, ResizeEdge),
    /// The content area was clicked. Coordinates are content-local.
    Content(WindowId, i32, i32),
    /// Nothing was hit (desktop background).
    Desktop,
}

/// Test whether a point (px, py) is inside a rectangle (rx, ry, rw, rh).
fn point_in_rect(px: i32, py: i32, rx: i32, ry: i32, rw: u32, rh: u32) -> bool {
    px >= rx && py >= ry && px < rx + rw as i32 && py < ry + rh as i32
}

/// Perform a hit test against a single window. Returns the first matching
/// region, checking in priority order per the design doc.
fn hit_test_window(window: &Window, x: i32, y: i32, theme: &WmTheme) -> Option<HitRegion> {
    // Skip minimized windows.
    if window.state == WindowState::Minimized {
        return None;
    }

    // Check if the point is within the outer frame at all.
    if !point_in_rect(x, y, window.x, window.y, window.outer_w, window.outer_h) {
        return None;
    }

    // 1. Titlebar buttons (highest priority).
    if let Some((bx, by, bw, bh)) = window.close_btn_rect(theme) {
        if point_in_rect(x, y, bx, by, bw, bh) {
            return Some(HitRegion::TitlebarButton(
                window.id.clone(),
                ButtonKind::Close,
            ));
        }
    }
    if let Some((bx, by, bw, bh)) = window.minimize_btn_rect(theme) {
        if point_in_rect(x, y, bx, by, bw, bh) {
            return Some(HitRegion::TitlebarButton(
                window.id.clone(),
                ButtonKind::Minimize,
            ));
        }
    }
    if let Some((bx, by, bw, bh)) = window.maximize_btn_rect(theme) {
        if point_in_rect(x, y, bx, by, bw, bh) {
            return Some(HitRegion::TitlebarButton(
                window.id.clone(),
                ButtonKind::Maximize,
            ));
        }
    }

    // 2. Titlebar body (initiates drag).
    if let Some((tx, ty, tw, th)) = window.titlebar_rect(theme) {
        if point_in_rect(x, y, tx, ty, tw, th) {
            return Some(HitRegion::Titlebar(window.id.clone()));
        }
    }

    // 3. Resize handles (edges and corners).
    if window.is_resizable() {
        if let Some(edge) = check_resize_handles(window, x, y, theme) {
            return Some(HitRegion::ResizeHandle(window.id.clone(), edge));
        }
    }

    // 4. Content area.
    let (cx, cy, cw, ch) = window.content_rect(theme);
    if point_in_rect(x, y, cx, cy, cw, ch) {
        let local_x = x - cx;
        let local_y = y - cy;
        return Some(HitRegion::Content(window.id.clone(), local_x, local_y));
    }

    // Point is in the frame border but not in any specific region.
    // Treat this as a titlebar-like region (allows dragging from frame edges).
    if window.is_draggable() {
        Some(HitRegion::Titlebar(window.id.clone()))
    } else {
        // For non-draggable windows (Panel), frame hits are content.
        let (cx, cy, _, _) = window.content_rect(theme);
        Some(HitRegion::Content(window.id.clone(), x - cx, y - cy))
    }
}

/// Check if a point hits one of the resize handles around the window edges.
fn check_resize_handles(window: &Window, x: i32, y: i32, theme: &WmTheme) -> Option<ResizeEdge> {
    let handle = theme.resize_handle_size as i32;
    let wx = window.x;
    let wy = window.y;
    let wr = wx + window.outer_w as i32;
    let wb = wy + window.outer_h as i32;

    let in_left = x >= wx && x < wx + handle;
    let in_right = x >= wr - handle && x < wr;
    let in_top = y >= wy && y < wy + handle;
    let in_bottom = y >= wb - handle && y < wb;

    // Corners first (they overlap edges).
    if in_top && in_left {
        return Some(ResizeEdge::NorthWest);
    }
    if in_top && in_right {
        return Some(ResizeEdge::NorthEast);
    }
    if in_bottom && in_left {
        return Some(ResizeEdge::SouthWest);
    }
    if in_bottom && in_right {
        return Some(ResizeEdge::SouthEast);
    }
    if in_top {
        return Some(ResizeEdge::North);
    }
    if in_bottom {
        return Some(ResizeEdge::South);
    }
    if in_left {
        return Some(ResizeEdge::West);
    }
    if in_right {
        return Some(ResizeEdge::East);
    }

    None
}

/// Perform a hit test against all windows. Windows are provided in z-order
/// (last element = topmost). Returns the first hit found, walking from top
/// to bottom.
pub fn hit_test(windows: &[Window], x: i32, y: i32, theme: &WmTheme) -> HitRegion {
    for window in windows.iter().rev() {
        if let Some(region) = hit_test_window(window, x, y, theme) {
            return region;
        }
    }
    HitRegion::Desktop
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::wm::window::{WindowConfig, WindowType};

    fn make_window(id: &str, x: i32, y: i32, w: u32, h: u32) -> Window {
        let config = WindowConfig {
            id: id.to_string(),
            title: id.to_string(),
            x: None,
            y: None,
            width: w,
            height: h,
            window_type: WindowType::AppWindow,
        };
        Window::new(&config, x, y, &WmTheme::default())
    }

    #[test]
    fn desktop_when_no_windows() {
        let theme = WmTheme::default();
        assert_eq!(hit_test(&[], 100, 100, &theme), HitRegion::Desktop);
    }

    #[test]
    fn desktop_when_miss_all_windows() {
        let theme = WmTheme::default();
        let win = make_window("w1", 10, 10, 100, 80);
        // Click far away from the window.
        assert_eq!(hit_test(&[win], 500, 500, &theme), HitRegion::Desktop);
    }

    #[test]
    fn content_area_hit() {
        let theme = WmTheme::default();
        let win = make_window("w1", 0, 0, 200, 150);
        let (cx, cy, _cw, _ch) = win.content_rect(&theme);
        // Click in the center of content.
        let result = hit_test(&[win], cx + 50, cy + 50, &theme);
        assert_eq!(result, HitRegion::Content("w1".to_string(), 50, 50));
    }

    #[test]
    fn titlebar_hit() {
        let theme = WmTheme::default();
        let win = make_window("w1", 0, 0, 200, 150);
        let (tx, ty, _tw, _th) = win.titlebar_rect(&theme).unwrap();
        // Click in the left side of the titlebar (away from buttons).
        let result = hit_test(&[win], tx + 5, ty + 5, &theme);
        assert_eq!(result, HitRegion::Titlebar("w1".to_string()));
    }

    #[test]
    fn close_button_hit() {
        let theme = WmTheme::default();
        let win = make_window("w1", 0, 0, 200, 150);
        let (bx, by, bw, bh) = win.close_btn_rect(&theme).unwrap();
        let result = hit_test(&[win], bx + bw as i32 / 2, by + bh as i32 / 2, &theme);
        assert_eq!(
            result,
            HitRegion::TitlebarButton("w1".to_string(), ButtonKind::Close)
        );
    }

    #[test]
    fn minimize_button_hit() {
        let theme = WmTheme::default();
        let win = make_window("w1", 0, 0, 200, 150);
        let (bx, by, bw, bh) = win.minimize_btn_rect(&theme).unwrap();
        let result = hit_test(&[win], bx + bw as i32 / 2, by + bh as i32 / 2, &theme);
        assert_eq!(
            result,
            HitRegion::TitlebarButton("w1".to_string(), ButtonKind::Minimize)
        );
    }

    #[test]
    fn maximize_button_hit() {
        let theme = WmTheme::default();
        let win = make_window("w1", 0, 0, 200, 150);
        let (bx, by, bw, bh) = win.maximize_btn_rect(&theme).unwrap();
        let result = hit_test(&[win], bx + bw as i32 / 2, by + bh as i32 / 2, &theme);
        assert_eq!(
            result,
            HitRegion::TitlebarButton("w1".to_string(), ButtonKind::Maximize)
        );
    }

    #[test]
    fn topmost_window_wins_overlap() {
        let theme = WmTheme::default();
        let win_bottom = make_window("bottom", 0, 0, 200, 150);
        let win_top = make_window("top", 10, 10, 200, 150);
        let (cx, cy, _cw, _ch) = win_top.content_rect(&theme);
        // Both windows overlap here, but top is last in the vec (topmost).
        let result = hit_test(&[win_bottom, win_top], cx + 5, cy + 5, &theme);
        match result {
            HitRegion::Content(id, _, _) => assert_eq!(id, "top"),
            other => panic!("expected Content(top), got {other:?}"),
        }
    }

    #[test]
    fn resize_handle_south_east() {
        let theme = WmTheme::default();
        let win = make_window("w1", 0, 0, 200, 150);
        // Click on the bottom-right corner.
        let x = win.outer_w as i32 - 2;
        let y = win.outer_h as i32 - 2;
        let result = hit_test(&[win], x, y, &theme);
        assert_eq!(
            result,
            HitRegion::ResizeHandle("w1".to_string(), ResizeEdge::SouthEast)
        );
    }

    #[test]
    fn resize_handle_north() {
        let theme = WmTheme::default();
        let win = make_window("w1", 0, 0, 200, 150);
        // Click on the very top edge (y=0), within the border but outside the
        // titlebar (which starts at y=border_width=1). Titlebar has higher
        // priority than resize handles, so we must click outside it.
        let result = hit_test(&[win], 100, 0, &theme);
        assert_eq!(
            result,
            HitRegion::ResizeHandle("w1".to_string(), ResizeEdge::North)
        );
    }

    #[test]
    fn minimized_window_not_hit() {
        let theme = WmTheme::default();
        let mut win = make_window("w1", 0, 0, 200, 150);
        win.state = WindowState::Minimized;
        let result = hit_test(&[win], 50, 50, &theme);
        assert_eq!(result, HitRegion::Desktop);
    }

    #[test]
    fn fullscreen_window_no_titlebar_hit() {
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
        // Click anywhere should be content (no titlebar, no resize).
        let result = hit_test(&[win], 100, 100, &theme);
        assert_eq!(result, HitRegion::Content("fs".to_string(), 100, 100));
    }

    #[test]
    fn dialog_not_resizable() {
        let theme = WmTheme::default();
        let config = WindowConfig {
            id: "dlg".to_string(),
            title: "Dialog".to_string(),
            x: None,
            y: None,
            width: 200,
            height: 100,
            window_type: WindowType::Dialog,
        };
        let win = Window::new(&config, 0, 0, &theme);
        // Click on bottom-right corner -- should NOT be a resize handle.
        let x = win.outer_w as i32 - 2;
        let y = win.outer_h as i32 - 2;
        let result = hit_test(&[win], x, y, &theme);
        // Dialog frame hits are content (not draggable).
        match result {
            HitRegion::Content(id, _, _) => assert_eq!(id, "dlg"),
            other => panic!("expected Content for dialog frame hit, got {other:?}"),
        }
    }

    #[test]
    fn point_in_rect_basic() {
        assert!(point_in_rect(5, 5, 0, 0, 10, 10));
        assert!(!point_in_rect(10, 10, 0, 0, 10, 10)); // Exclusive upper bound.
        assert!(!point_in_rect(-1, 5, 0, 0, 10, 10));
    }
}
