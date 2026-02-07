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
    /// Solid fill color (used when `texture` is `None`).
    pub color: Color,
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
