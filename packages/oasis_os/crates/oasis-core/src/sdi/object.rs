//! SDI scene graph objects.
//!
//! An `SdiObject` is a named, positionable, blittable element in the scene
//! graph. SDI is deliberately flat -- no hierarchy, no parent-child, no
//! grouping. The window manager (when present) simulates hierarchy via
//! naming conventions.

use crate::backend::{Color, TextureId};

/// A single object in the SDI scene graph.
#[derive(Debug, Clone)]
pub struct SdiObject {
    /// Unique name (used as the registry key).
    pub name: String,
    /// X position in virtual screen coordinates.
    pub x: i32,
    /// Y position in virtual screen coordinates.
    pub y: i32,
    /// Width in pixels.
    pub w: u32,
    /// Height in pixels.
    pub h: u32,
    /// Alpha (0 = fully transparent, 255 = fully opaque).
    pub alpha: u8,
    /// Z-order index (higher = drawn later = on top).
    pub z: i32,
    /// Whether this object is drawn.
    pub visible: bool,
    /// Optional texture handle. If `None`, the object draws as a solid `color`.
    pub texture: Option<TextureId>,
    /// Solid fill color (used when `texture` is `None` and `text` is `None`).
    pub color: Color,
    /// Optional text content. When set, the object renders text instead of a
    /// filled rectangle. The `color` field is used as the text color.
    pub text: Option<String>,
    /// Font size in pixels (used when `text` is `Some`).
    pub font_size: u16,
    /// Text color (separate from background fill color).
    pub text_color: Color,
    /// When true, this object is drawn in the overlay pass (on top of all
    /// base-layer objects). Matches PSIX's two-layer rendering model.
    pub overlay: bool,
}

impl SdiObject {
    /// Create a new object with sensible defaults.
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            x: 0,
            y: 0,
            w: 0,
            h: 0,
            alpha: 255,
            z: 0,
            visible: true,
            texture: None,
            color: Color::WHITE,
            text: None,
            font_size: 12,
            text_color: Color::BLACK,
            overlay: false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_object_defaults() {
        let obj = SdiObject::new("test");
        assert_eq!(obj.name, "test");
        assert_eq!(obj.x, 0);
        assert_eq!(obj.y, 0);
        assert_eq!(obj.alpha, 255);
        assert!(obj.visible);
        assert!(obj.texture.is_none());
    }
}
