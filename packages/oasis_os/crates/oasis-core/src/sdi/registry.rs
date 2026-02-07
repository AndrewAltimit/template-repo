//! SDI object registry.
//!
//! The registry is a flat collection of named `SdiObject`s. It provides
//! create, lookup, z-order management, and a `draw` method that iterates
//! objects in z-order and dispatches to the rendering backend.

use std::collections::HashMap;

use serde::Deserialize;

use crate::backend::{Color, SdiBackend};
use crate::error::{OasisError, Result};
use crate::sdi::object::SdiObject;

/// The SDI scene graph: a flat, named registry of blittable objects.
#[derive(Debug)]
pub struct SdiRegistry {
    objects: HashMap<String, SdiObject>,
    /// Monotonically increasing counter for assigning z-order to new objects.
    next_z: i32,
}

impl SdiRegistry {
    /// Create an empty registry.
    pub fn new() -> Self {
        Self {
            objects: HashMap::new(),
            next_z: 0,
        }
    }

    /// Create a new object and insert it into the registry.
    /// Returns a mutable reference to the newly created object for chaining.
    ///
    /// If an object with the same name already exists, it is replaced.
    pub fn create(&mut self, name: impl Into<String>) -> &mut SdiObject {
        let name = name.into();
        let mut obj = SdiObject::new(&name);
        obj.z = self.next_z;
        self.next_z += 1;
        self.objects.insert(name.clone(), obj);
        self.objects.get_mut(&name).unwrap()
    }

    /// Get a shared reference to an object by name.
    pub fn get(&self, name: &str) -> Result<&SdiObject> {
        self.objects
            .get(name)
            .ok_or_else(|| OasisError::Sdi(format!("object not found: {name}")))
    }

    /// Get a mutable reference to an object by name.
    pub fn get_mut(&mut self, name: &str) -> Result<&mut SdiObject> {
        self.objects
            .get_mut(name)
            .ok_or_else(|| OasisError::Sdi(format!("object not found: {name}")))
    }

    /// Remove an object from the registry.
    pub fn destroy(&mut self, name: &str) -> Result<()> {
        self.objects
            .remove(name)
            .map(|_| ())
            .ok_or_else(|| OasisError::Sdi(format!("object not found: {name}")))
    }

    /// Move an object to the top of the z-order (drawn last = on top).
    pub fn move_to_top(&mut self, name: &str) -> Result<()> {
        let new_z = self.next_z;
        self.next_z += 1;
        let obj = self.get_mut(name)?;
        obj.z = new_z;
        Ok(())
    }

    /// Move an object to the bottom of the z-order (drawn first = behind).
    pub fn move_to_bottom(&mut self, name: &str) -> Result<()> {
        let min_z = self.objects.values().map(|o| o.z).min().unwrap_or(0) - 1;
        let obj = self.get_mut(name)?;
        obj.z = min_z;
        Ok(())
    }

    /// Returns the number of objects in the registry.
    pub fn len(&self) -> usize {
        self.objects.len()
    }

    /// Returns true if the registry contains no objects.
    pub fn is_empty(&self) -> bool {
        self.objects.is_empty()
    }

    /// Returns true if an object with the given name exists.
    pub fn contains(&self, name: &str) -> bool {
        self.objects.contains_key(name)
    }

    /// Load raw RGBA pixel data as a texture through the backend and assign it
    /// to the named object. The object's dimensions are updated to match.
    pub fn load_image(
        &mut self,
        name: &str,
        width: u32,
        height: u32,
        rgba_data: &[u8],
        backend: &mut dyn SdiBackend,
    ) -> Result<()> {
        let tex = backend.load_texture(width, height, rgba_data)?;
        let obj = self.get_mut(name)?;
        obj.texture = Some(tex);
        obj.w = width;
        obj.h = height;
        Ok(())
    }

    /// Apply a theme from a TOML string. Each top-level key is an object name;
    /// nested keys set properties (x, y, w, h, visible, alpha, color, text,
    /// font_size). Objects that don't exist yet are created.
    pub fn load_theme(&mut self, toml_str: &str) -> Result<()> {
        let theme: HashMap<String, ThemeEntry> =
            toml::from_str(toml_str).map_err(|e| OasisError::Config(format!("{e}")))?;

        for (name, entry) in theme {
            if !self.contains(&name) {
                self.create(&name);
            }
            let obj = self.get_mut(&name)?;
            if let Some(x) = entry.x {
                obj.x = x;
            }
            if let Some(y) = entry.y {
                obj.y = y;
            }
            if let Some(w) = entry.w {
                obj.w = w;
            }
            if let Some(h) = entry.h {
                obj.h = h;
            }
            if let Some(a) = entry.alpha {
                obj.alpha = a;
            }
            if let Some(v) = entry.visible {
                obj.visible = v;
            }
            if let Some(ref t) = entry.text {
                obj.text = Some(t.clone());
            }
            if let Some(fs) = entry.font_size {
                obj.font_size = fs;
            }
            if let Some(ref c) = entry.color {
                if let Some(parsed) = parse_color(c) {
                    obj.color = parsed;
                }
            }
            if let Some(ref c) = entry.text_color {
                if let Some(parsed) = parse_color(c) {
                    obj.text_color = parsed;
                }
            }
        }
        Ok(())
    }

    /// Return an iterator over all object names in the registry.
    pub fn names(&self) -> impl Iterator<Item = &str> {
        self.objects.keys().map(String::as_str)
    }

    /// Draw all visible objects to the backend, sorted by z-order (ascending).
    pub fn draw(&self, backend: &mut dyn SdiBackend) -> Result<()> {
        let mut sorted: Vec<&SdiObject> = self.objects.values().collect();
        sorted.sort_by_key(|o| o.z);

        for obj in sorted {
            if !obj.visible || obj.alpha == 0 {
                continue;
            }

            // Textured object -- blit the texture.
            if let Some(tex) = obj.texture {
                backend.blit(tex, obj.x, obj.y, obj.w, obj.h)?;
                continue;
            }

            // If the object has a fill color with nonzero area, draw the rect.
            if obj.w > 0 && obj.h > 0 {
                let color = Color::rgba(obj.color.r, obj.color.g, obj.color.b, obj.alpha);
                backend.fill_rect(obj.x, obj.y, obj.w, obj.h, color)?;
            }

            // If the object carries text, draw it on top.
            if let Some(ref text) = obj.text {
                backend.draw_text(text, obj.x, obj.y, obj.font_size, obj.text_color)?;
            }
        }

        Ok(())
    }
}

/// Deserialization helper for theme TOML entries.
#[derive(Debug, Deserialize)]
struct ThemeEntry {
    x: Option<i32>,
    y: Option<i32>,
    w: Option<u32>,
    h: Option<u32>,
    alpha: Option<u8>,
    visible: Option<bool>,
    text: Option<String>,
    font_size: Option<u16>,
    color: Option<String>,
    text_color: Option<String>,
}

/// Parse a color string like "#RRGGBB" or "#RRGGBBAA".
fn parse_color(s: &str) -> Option<Color> {
    let s = s.strip_prefix('#')?;
    if s.len() == 6 {
        let r = u8::from_str_radix(&s[0..2], 16).ok()?;
        let g = u8::from_str_radix(&s[2..4], 16).ok()?;
        let b = u8::from_str_radix(&s[4..6], 16).ok()?;
        Some(Color::rgb(r, g, b))
    } else if s.len() == 8 {
        let r = u8::from_str_radix(&s[0..2], 16).ok()?;
        let g = u8::from_str_radix(&s[2..4], 16).ok()?;
        let b = u8::from_str_radix(&s[4..6], 16).ok()?;
        let a = u8::from_str_radix(&s[6..8], 16).ok()?;
        Some(Color::rgba(r, g, b, a))
    } else {
        None
    }
}

impl Default for SdiRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn create_and_get() {
        let mut reg = SdiRegistry::new();
        {
            let obj = reg.create("panel");
            obj.x = 10;
            obj.y = 20;
        }
        let obj = reg.get("panel").unwrap();
        assert_eq!(obj.x, 10);
        assert_eq!(obj.y, 20);
    }

    #[test]
    fn get_nonexistent_returns_error() {
        let reg = SdiRegistry::new();
        assert!(reg.get("nope").is_err());
    }

    #[test]
    fn destroy_removes_object() {
        let mut reg = SdiRegistry::new();
        reg.create("temp");
        assert!(reg.contains("temp"));
        reg.destroy("temp").unwrap();
        assert!(!reg.contains("temp"));
    }

    #[test]
    fn z_order_auto_increments() {
        let mut reg = SdiRegistry::new();
        reg.create("a");
        reg.create("b");
        reg.create("c");
        let a = reg.get("a").unwrap().z;
        let b = reg.get("b").unwrap().z;
        let c = reg.get("c").unwrap().z;
        assert!(a < b);
        assert!(b < c);
    }

    #[test]
    fn move_to_top() {
        let mut reg = SdiRegistry::new();
        reg.create("bottom");
        reg.create("top");
        let top_z = reg.get("top").unwrap().z;
        reg.move_to_top("bottom").unwrap();
        let bottom_z = reg.get("bottom").unwrap().z;
        assert!(bottom_z > top_z);
    }

    #[test]
    fn move_to_bottom() {
        let mut reg = SdiRegistry::new();
        reg.create("a");
        reg.create("b");
        let a_z = reg.get("a").unwrap().z;
        reg.move_to_bottom("b").unwrap();
        let b_z = reg.get("b").unwrap().z;
        assert!(b_z < a_z);
    }

    #[test]
    fn len_and_is_empty() {
        let mut reg = SdiRegistry::new();
        assert!(reg.is_empty());
        reg.create("x");
        assert_eq!(reg.len(), 1);
        assert!(!reg.is_empty());
    }

    #[test]
    fn load_theme_creates_and_updates() {
        let mut reg = SdiRegistry::new();
        reg.create("existing");
        let theme = r##"
[existing]
x = 42
y = 10

[new_obj]
x = 100
w = 50
h = 30
color = "#FF0000"
text = "hello"
font_size = 16
"##;
        reg.load_theme(theme).unwrap();
        let e = reg.get("existing").unwrap();
        assert_eq!(e.x, 42);
        assert_eq!(e.y, 10);

        let n = reg.get("new_obj").unwrap();
        assert_eq!(n.x, 100);
        assert_eq!(n.w, 50);
        assert_eq!(n.h, 30);
        assert_eq!(n.color.r, 255);
        assert_eq!(n.color.g, 0);
        assert_eq!(n.text.as_deref(), Some("hello"));
        assert_eq!(n.font_size, 16);
    }

    #[test]
    fn parse_color_hex() {
        let c = super::parse_color("#1A2B3C").unwrap();
        assert_eq!(c.r, 0x1A);
        assert_eq!(c.g, 0x2B);
        assert_eq!(c.b, 0x3C);
        assert_eq!(c.a, 255);

        let c2 = super::parse_color("#1A2B3C80").unwrap();
        assert_eq!(c2.a, 0x80);
    }

    #[test]
    fn parse_color_invalid() {
        assert!(super::parse_color("not-a-color").is_none());
        assert!(super::parse_color("#GG0000").is_none());
        assert!(super::parse_color("#12345").is_none());
    }

    #[test]
    fn text_object_defaults() {
        let mut reg = SdiRegistry::new();
        let obj = reg.create("label");
        obj.text = Some("test".into());
        obj.font_size = 14;
        let o = reg.get("label").unwrap();
        assert_eq!(o.text.as_deref(), Some("test"));
        assert_eq!(o.font_size, 14);
    }

    #[test]
    fn names_iterator() {
        let mut reg = SdiRegistry::new();
        reg.create("a");
        reg.create("b");
        let mut names: Vec<&str> = reg.names().collect();
        names.sort();
        assert_eq!(names, vec!["a", "b"]);
    }
}
