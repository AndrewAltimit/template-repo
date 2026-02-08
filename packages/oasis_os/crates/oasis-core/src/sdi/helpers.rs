//! Shared SDI object creation helpers.
//!
//! Consolidates the repeated patterns of create-if-missing + update for
//! common UI elements: text labels, thin borders, and metallic bezels.

use super::SdiRegistry;
use crate::backend::Color;

/// Z-order constants for overlay layers.
pub const Z_BAR: i32 = 900;
pub const Z_BORDER: i32 = 901;
pub const Z_TEXT: i32 = 902;

/// Ensure an overlay text object exists and is visible.
///
/// Creates the object if missing, then marks it visible each frame.
/// The caller should follow up with `sdi.get_mut(name)` to set `.text`.
pub fn ensure_text(
    sdi: &mut SdiRegistry,
    name: &str,
    x: i32,
    y: i32,
    font_size: u16,
    color: Color,
) {
    if !sdi.contains(name) {
        let obj = sdi.create(name);
        obj.x = x;
        obj.y = y;
        obj.font_size = font_size;
        obj.text_color = color;
        obj.w = 0;
        obj.h = 0;
        obj.overlay = true;
        obj.z = Z_TEXT;
    }
    if let Ok(obj) = sdi.get_mut(name) {
        obj.visible = true;
    }
}

/// Ensure a thin 1px border/line overlay exists and is visible.
pub fn ensure_border(
    sdi: &mut SdiRegistry,
    name: &str,
    x: i32,
    y: i32,
    w: u32,
    h: u32,
    color: Color,
) {
    if !sdi.contains(name) {
        let obj = sdi.create(name);
        obj.overlay = true;
        obj.z = Z_BORDER;
    }
    if let Ok(obj) = sdi.get_mut(name) {
        obj.x = x;
        obj.y = y;
        obj.w = w;
        obj.h = h;
        obj.color = color;
        obj.visible = true;
    }
}

/// Ensure a chrome/metallic bezel with all 4 edges.
///
/// Creates 5 SDI objects: fill (`name`), top (`{name}_t`), bottom (`{name}_b`),
/// left (`{name}_l`), and right (`{name}_r`).
pub fn ensure_chrome_bezel(
    sdi: &mut SdiRegistry,
    name: &str,
    x: i32,
    y: i32,
    w: u32,
    h: u32,
    style: &BezelStyle,
) {
    // Main fill.
    if !sdi.contains(name) {
        let obj = sdi.create(name);
        obj.overlay = true;
        obj.z = Z_BAR;
    }
    if let Ok(obj) = sdi.get_mut(name) {
        obj.x = x;
        obj.y = y;
        obj.w = w;
        obj.h = h;
        obj.color = style.fill;
        obj.visible = true;
    }

    // Four edges.
    let edges: [(&str, i32, i32, u32, u32, Color); 4] = [
        ("_t", x, y, w, 1, style.top),
        ("_b", x, y + h as i32 - 1, w, 1, style.bottom),
        ("_l", x, y, 1, h, style.left),
        ("_r", x + w as i32 - 1, y, 1, h, style.right),
    ];
    for (suffix, ex, ey, ew, eh, color) in &edges {
        let edge_name = format!("{name}{suffix}");
        ensure_border(sdi, &edge_name, *ex, *ey, *ew, *eh, *color);
    }
}

/// Style parameters for a chrome bezel.
pub struct BezelStyle {
    pub fill: Color,
    pub top: Color,
    pub bottom: Color,
    pub left: Color,
    pub right: Color,
}

impl BezelStyle {
    /// Chrome/silver metallic style matching PSIX.
    pub fn chrome() -> Self {
        Self {
            fill: Color::rgba(160, 170, 180, 80),
            top: Color::rgba(255, 255, 255, 120),
            bottom: Color::rgba(60, 70, 80, 140),
            left: Color::rgba(255, 255, 255, 80),
            right: Color::rgba(80, 90, 100, 120),
        }
    }
}

/// Hide a list of named SDI objects.
pub fn hide_objects(sdi: &mut SdiRegistry, names: &[&str]) {
    for name in names {
        if let Ok(obj) = sdi.get_mut(name) {
            obj.visible = false;
        }
    }
}

/// Hide a range of indexed SDI objects (`{prefix}0`, `{prefix}1`, ...).
pub fn hide_indexed(sdi: &mut SdiRegistry, prefix: &str, count: usize) {
    for i in 0..count {
        let name = format!("{prefix}{i}");
        if let Ok(obj) = sdi.get_mut(&name) {
            obj.visible = false;
        }
    }
}

/// Hide all bezel-related objects (fill + 4 edges).
pub fn hide_bezel(sdi: &mut SdiRegistry, name: &str) {
    let names: [String; 5] = [
        name.to_string(),
        format!("{name}_t"),
        format!("{name}_b"),
        format!("{name}_l"),
        format!("{name}_r"),
    ];
    for n in &names {
        if let Ok(obj) = sdi.get_mut(n) {
            obj.visible = false;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ensure_text_creates_and_shows() {
        let mut sdi = SdiRegistry::new();
        ensure_text(&mut sdi, "test_text", 10, 20, 8, Color::WHITE);
        assert!(sdi.contains("test_text"));
        assert!(sdi.get("test_text").unwrap().visible);
        assert_eq!(sdi.get("test_text").unwrap().x, 10);
    }

    #[test]
    fn ensure_border_creates_and_shows() {
        let mut sdi = SdiRegistry::new();
        ensure_border(&mut sdi, "test_border", 5, 10, 100, 1, Color::WHITE);
        assert!(sdi.contains("test_border"));
        let obj = sdi.get("test_border").unwrap();
        assert_eq!(obj.w, 100);
        assert_eq!(obj.h, 1);
    }

    #[test]
    fn chrome_bezel_creates_five_objects() {
        let mut sdi = SdiRegistry::new();
        ensure_chrome_bezel(&mut sdi, "bz", 0, 0, 50, 20, &BezelStyle::chrome());
        assert!(sdi.contains("bz"));
        assert!(sdi.contains("bz_t"));
        assert!(sdi.contains("bz_b"));
        assert!(sdi.contains("bz_l"));
        assert!(sdi.contains("bz_r"));
    }

    #[test]
    fn hide_bezel_hides_all() {
        let mut sdi = SdiRegistry::new();
        ensure_chrome_bezel(&mut sdi, "bz", 0, 0, 50, 20, &BezelStyle::chrome());
        hide_bezel(&mut sdi, "bz");
        assert!(!sdi.get("bz").unwrap().visible);
        assert!(!sdi.get("bz_t").unwrap().visible);
    }

    #[test]
    fn hide_indexed_hides_range() {
        let mut sdi = SdiRegistry::new();
        for i in 0..3 {
            ensure_text(&mut sdi, &format!("item_{i}"), 0, 0, 8, Color::WHITE);
        }
        hide_indexed(&mut sdi, "item_", 3);
        assert!(!sdi.get("item_0").unwrap().visible);
        assert!(!sdi.get("item_2").unwrap().visible);
    }
}
