//! SDI object registry.
//!
//! The registry is a flat collection of named `SdiObject`s. It provides
//! create, lookup, z-order management, and a `draw` method that iterates
//! objects in z-order and dispatches to the rendering backend.

use std::collections::HashMap;

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

    /// Draw all visible objects to the backend, sorted by z-order (ascending).
    pub fn draw(&self, backend: &mut dyn SdiBackend) -> Result<()> {
        let mut sorted: Vec<&SdiObject> = self.objects.values().collect();
        sorted.sort_by_key(|o| o.z);

        for obj in sorted {
            if !obj.visible || obj.alpha == 0 {
                continue;
            }

            match obj.texture {
                Some(tex) => backend.blit(tex, obj.x, obj.y, obj.w, obj.h)?,
                None => {
                    let color = Color::rgba(obj.color.r, obj.color.g, obj.color.b, obj.alpha);
                    backend.fill_rect(obj.x, obj.y, obj.w, obj.h, color)?;
                },
            }
        }

        Ok(())
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
}
