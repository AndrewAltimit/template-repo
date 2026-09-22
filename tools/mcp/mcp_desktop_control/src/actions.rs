//! Composite desktop actions built from backend primitives.
//!
//! These functions are blocking (they sleep between events so applications
//! register them as distinct) and are always run on a blocking thread by the
//! server. Keeping them platform-neutral means clicks, drags and chords
//! behave identically on X11 and Windows and are tested against the mock
//! backend.

use std::thread::sleep;
use std::time::Duration;

use crate::backend::{DesktopBackend, DesktopError, DesktopResult};
use crate::keys::Key;
use crate::types::{MouseButton, Rect, ScreenInfo, ScrollDirection, WindowInfo};

/// How long a button or key is held for a single press.
const PRESS_HOLD: Duration = Duration::from_millis(15);
/// Gap between the clicks of a multi-click (well below any double-click time).
const CLICK_GAP: Duration = Duration::from_millis(40);
/// Pause after moving the pointer before pressing, so hover state settles.
const SETTLE: Duration = Duration::from_millis(15);
/// Approximate interval between intermediate drag positions.
const DRAG_STEP_MS: u64 = 10;
/// Upper bound on intermediate drag positions.
const MAX_DRAG_STEPS: u64 = 200;

/// Apply the optional title / visibility filters of `list_windows`.
pub fn filter_windows(
    windows: Vec<WindowInfo>,
    title_filter: Option<&str>,
    visible_only: bool,
) -> Vec<WindowInfo> {
    let needle = title_filter
        .map(str::trim)
        .filter(|f| !f.is_empty())
        .map(str::to_lowercase);
    windows
        .into_iter()
        .filter(|w| !visible_only || w.visible)
        .filter(|w| {
            needle
                .as_deref()
                .is_none_or(|n| w.title.to_lowercase().contains(n))
        })
        .collect()
}

/// The primary screen, or the first one if none is flagged primary.
pub fn primary_screen(screens: &[ScreenInfo]) -> Option<&ScreenInfo> {
    screens
        .iter()
        .find(|s| s.is_primary)
        .or_else(|| screens.first())
}

/// Resolve `screenshot_screen`'s `screen_id` (default: primary screen).
pub fn screen_rect(screens: &[ScreenInfo], screen_id: Option<u32>) -> DesktopResult<Rect> {
    let screen = match screen_id {
        None => primary_screen(screens)
            .ok_or_else(|| DesktopError::ScreenNotFound("no screens detected".to_string()))?,
        Some(id) => screens.iter().find(|s| s.id == id).ok_or_else(|| {
            let valid: Vec<String> = screens.iter().map(|s| s.id.to_string()).collect();
            DesktopError::ScreenNotFound(format!(
                "screen_id {id} does not exist (valid ids: {})",
                valid.join(", ")
            ))
        })?,
    };
    Ok(Rect::new(screen.x, screen.y, screen.width, screen.height))
}

/// Clip a requested capture region to the desktop; error if it is empty or
/// entirely off-screen.
pub fn clip_region(requested: Rect, desktop: Rect) -> DesktopResult<Rect> {
    if requested.width == 0 || requested.height == 0 {
        return Err(DesktopError::InvalidInput(
            "Region width and height must be at least 1".to_string(),
        ));
    }
    requested.intersect(&desktop).ok_or_else(|| {
        DesktopError::InvalidInput(format!(
            "Region {}x{} at ({}, {}) is entirely outside the desktop {}x{} at ({}, {})",
            requested.width,
            requested.height,
            requested.x,
            requested.y,
            desktop.width,
            desktop.height,
            desktop.x,
            desktop.y
        ))
    })
}

/// Move the pointer (absolute or relative) and return the final target.
pub fn move_mouse(
    b: &dyn DesktopBackend,
    x: i32,
    y: i32,
    relative: bool,
) -> DesktopResult<(i32, i32)> {
    let target = if relative {
        let (cx, cy) = b.mouse_position()?;
        (cx.saturating_add(x), cy.saturating_add(y))
    } else {
        (x, y)
    };
    b.move_mouse(target.0, target.1)?;
    Ok(target)
}

/// Click `clicks` times, optionally moving to `at` first.
pub fn click(
    b: &dyn DesktopBackend,
    button: MouseButton,
    at: Option<(i32, i32)>,
    clicks: u32,
) -> DesktopResult<()> {
    if let Some((x, y)) = at {
        b.move_mouse(x, y)?;
        sleep(SETTLE);
    }
    for i in 0..clicks {
        if i > 0 {
            sleep(CLICK_GAP);
        }
        b.mouse_button(button, true)?;
        sleep(PRESS_HOLD);
        b.mouse_button(button, false)?;
    }
    Ok(())
}

/// Intermediate pointer positions for a drag (excluding the start point,
/// including the end point).
pub fn drag_path(start: (i32, i32), end: (i32, i32), steps: u32) -> Vec<(i32, i32)> {
    let steps = steps.max(1);
    (1..=steps)
        .map(|i| {
            let t = f64::from(i) / f64::from(steps);
            let lerp = |a: i32, b: i32| (f64::from(a) + (f64::from(b) - f64::from(a)) * t).round();
            // lerp stays within [min(a,b), max(a,b)], so the cast is exact.
            (lerp(start.0, end.0) as i32, lerp(start.1, end.1) as i32)
        })
        .collect()
}

/// Number of intermediate drag positions for a duration.
pub fn drag_steps(duration_ms: u64) -> u32 {
    // Bounded by MAX_DRAG_STEPS, so the conversion cannot fail.
    u32::try_from((duration_ms / DRAG_STEP_MS).clamp(1, MAX_DRAG_STEPS)).unwrap_or(1)
}

/// Press at `start`, move smoothly to `end` over `duration_ms`, release.
///
/// The button is always released, even if an intermediate move fails, so a
/// failed drag never leaves the button stuck down.
pub fn drag(
    b: &dyn DesktopBackend,
    start: (i32, i32),
    end: (i32, i32),
    button: MouseButton,
    duration_ms: u64,
) -> DesktopResult<()> {
    b.move_mouse(start.0, start.1)?;
    sleep(SETTLE);
    b.mouse_button(button, true)?;
    let steps = drag_steps(duration_ms);
    let delay = Duration::from_millis(duration_ms / u64::from(steps));
    let moved = drag_path(start, end, steps)
        .into_iter()
        .try_for_each(|(x, y)| {
            sleep(delay);
            b.move_mouse(x, y)
        });
    sleep(SETTLE);
    let released = b.mouse_button(button, false);
    moved.and(released)
}

/// Scroll, optionally moving to `at` first.
pub fn scroll(
    b: &dyn DesktopBackend,
    direction: ScrollDirection,
    amount: i32,
    at: Option<(i32, i32)>,
) -> DesktopResult<()> {
    if let Some((x, y)) = at {
        b.move_mouse(x, y)?;
        sleep(SETTLE);
    }
    b.scroll(direction, amount)
}

/// Press `keys` in order, then release them in reverse order.
///
/// If any press fails, every key already pressed is released before the
/// error is returned, so a bad key name never leaves Ctrl/Alt stuck down.
pub fn chord(b: &dyn DesktopBackend, keys: &[Key]) -> DesktopResult<()> {
    let mut pressed: Vec<Key> = Vec::with_capacity(keys.len());
    let mut result = Ok(());
    for &key in keys {
        if let Err(e) = b.key(key, true) {
            result = Err(e);
            break;
        }
        pressed.push(key);
    }
    if result.is_ok() {
        sleep(PRESS_HOLD);
    }
    for &key in pressed.iter().rev() {
        let released = b.key(key, false);
        if result.is_ok() {
            result = released;
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::mock::{Event, MockBackend};
    use crate::keys::NamedKey;

    #[test]
    fn filter_by_title_and_visibility() {
        let m = MockBackend::new();
        let all = filter_windows(m.windows.clone(), None, false);
        assert_eq!(all.len(), 3);
        let visible = filter_windows(m.windows.clone(), None, true);
        assert_eq!(visible.len(), 2);
        let fx = filter_windows(m.windows.clone(), Some("FIRE"), true);
        assert_eq!(fx.len(), 1);
        assert_eq!(fx[0].id, "200");
        let hidden = filter_windows(m.windows.clone(), Some("notes"), true);
        assert!(hidden.is_empty());
        let blank = filter_windows(m.windows.clone(), Some("  "), false);
        assert_eq!(blank.len(), 3);
    }

    #[test]
    fn screen_selection_defaults_to_primary() {
        let m = MockBackend::new();
        assert_eq!(
            screen_rect(&m.screens, None).unwrap(),
            Rect::new(1920, 0, 1280, 1024)
        );
        assert_eq!(
            screen_rect(&m.screens, Some(0)).unwrap(),
            Rect::new(0, 0, 1920, 1080)
        );
        let err = screen_rect(&m.screens, Some(7)).unwrap_err().to_string();
        assert!(err.contains("valid ids: 0, 1"), "{err}");
        assert!(screen_rect(&[], None).is_err());
    }

    #[test]
    fn region_clipping() {
        let desk = Rect::new(0, 0, 100, 100);
        assert_eq!(
            clip_region(Rect::new(90, 90, 50, 50), desk).unwrap(),
            Rect::new(90, 90, 10, 10)
        );
        assert!(clip_region(Rect::new(0, 0, 0, 5), desk).is_err());
        assert!(clip_region(Rect::new(200, 0, 5, 5), desk).is_err());
    }

    #[test]
    fn drag_path_is_monotonic_and_ends_at_target() {
        let path = drag_path((0, 0), (100, -50), 4);
        assert_eq!(path, vec![(25, -13), (50, -25), (75, -38), (100, -50)]);
        assert_eq!(drag_path((5, 5), (5, 5), 0), vec![(5, 5)]);
        assert_eq!(drag_steps(0), 1);
        assert_eq!(drag_steps(500), 50);
        assert_eq!(drag_steps(u64::MAX), 200);
    }

    #[test]
    fn relative_move_saturates() {
        let m = MockBackend::new();
        *m.pointer.lock().unwrap() = (i32::MAX - 1, 0);
        let target = move_mouse(&m, 10, -3, true).unwrap();
        assert_eq!(target, (i32::MAX, -3));
    }

    #[test]
    fn double_click_sequence() {
        let m = MockBackend::new();
        click(&m, MouseButton::Right, Some((3, 4)), 2).unwrap();
        assert_eq!(
            m.events(),
            vec![
                Event::MoveMouse(3, 4),
                Event::Button(MouseButton::Right, true),
                Event::Button(MouseButton::Right, false),
                Event::Button(MouseButton::Right, true),
                Event::Button(MouseButton::Right, false),
            ]
        );
    }

    #[test]
    fn drag_sequence_presses_moves_and_releases() {
        let m = MockBackend::new();
        drag(&m, (0, 0), (20, 0), MouseButton::Left, 20).unwrap();
        let ev = m.events();
        assert_eq!(ev.first(), Some(&Event::MoveMouse(0, 0)));
        assert_eq!(ev[1], Event::Button(MouseButton::Left, true));
        assert_eq!(ev[ev.len() - 2], Event::MoveMouse(20, 0));
        assert_eq!(ev.last(), Some(&Event::Button(MouseButton::Left, false)));
    }

    #[test]
    fn chord_releases_in_reverse_order() {
        let m = MockBackend::new();
        let ctrl = Key::Named(NamedKey::Ctrl);
        let shift = Key::Named(NamedKey::Shift);
        let s = Key::Char('s');
        chord(&m, &[ctrl, shift, s]).unwrap();
        assert_eq!(
            m.events(),
            vec![
                Event::Key(ctrl, true),
                Event::Key(shift, true),
                Event::Key(s, true),
                Event::Key(s, false),
                Event::Key(shift, false),
                Event::Key(ctrl, false),
            ]
        );
    }

    #[test]
    fn chord_failure_releases_already_pressed_keys() {
        let mut m = MockBackend::new();
        let bad = Key::Char('\u{2603}');
        m.failing_key = Some(bad);
        let ctrl = Key::Named(NamedKey::Ctrl);
        assert!(chord(&m, &[ctrl, bad]).is_err());
        assert_eq!(
            m.events(),
            vec![Event::Key(ctrl, true), Event::Key(ctrl, false)]
        );
    }
}
