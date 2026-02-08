//! Mouse cursor state and procedural cursor image generation.
//!
//! Provides a visible pointer cursor that follows mouse movement.
//! The cursor is rendered as an SDI overlay object at the highest z-order.

use crate::input::InputEvent;
use crate::sdi::SdiRegistry;

/// Cursor arrow dimensions.
const CURSOR_W: u32 = 12;
const CURSOR_H: u32 = 18;

/// SDI object name for the cursor.
const CURSOR_SDI_NAME: &str = "mouse_cursor";

/// Runtime state for the mouse cursor.
#[derive(Debug)]
pub struct CursorState {
    /// Current X position.
    pub x: i32,
    /// Current Y position.
    pub y: i32,
    /// Whether the cursor is visible.
    pub visible: bool,
}

impl CursorState {
    /// Create a new cursor state centered on screen.
    pub fn new(screen_w: u32, screen_h: u32) -> Self {
        Self {
            x: screen_w as i32 / 2,
            y: screen_h as i32 / 2,
            visible: true,
        }
    }

    /// Set the cursor position directly (useful for tests/screenshots).
    pub fn set_position(&mut self, x: i32, y: i32) {
        self.x = x;
        self.y = y;
    }

    /// Handle an input event, updating cursor position on mouse move.
    pub fn handle_input(&mut self, event: &InputEvent) {
        if let InputEvent::CursorMove { x, y } = event {
            self.x = *x;
            self.y = *y;
            self.visible = true;
        }
    }

    /// Update the cursor SDI object to reflect current position.
    pub fn update_sdi(&self, sdi: &mut SdiRegistry) {
        if !sdi.contains(CURSOR_SDI_NAME) {
            let obj = sdi.create(CURSOR_SDI_NAME);
            obj.w = CURSOR_W;
            obj.h = CURSOR_H;
            obj.overlay = true;
            obj.z = 10000; // Always on top.
        }
        if let Ok(obj) = sdi.get_mut(CURSOR_SDI_NAME) {
            obj.x = self.x;
            obj.y = self.y;
            obj.visible = self.visible;
            // The texture is assigned externally after load_texture.
        }
    }

    /// Hide the cursor SDI object.
    pub fn hide_sdi(sdi: &mut SdiRegistry) {
        if let Ok(obj) = sdi.get_mut(CURSOR_SDI_NAME) {
            obj.visible = false;
        }
    }
}

/// Generate a procedural arrow cursor as RGBA pixel data.
///
/// Returns `(pixels, width, height)`. The arrow is white with a black outline,
/// pointing up-left like a standard OS cursor.
pub fn generate_cursor_pixels() -> (Vec<u8>, u32, u32) {
    // 12x18 cursor bitmap. Legend: 0=transparent, 1=black outline, 2=white fill.
    #[rustfmt::skip]
    let bitmap: [[u8; 12]; 18] = [
        [1,0,0,0,0,0,0,0,0,0,0,0],
        [1,1,0,0,0,0,0,0,0,0,0,0],
        [1,2,1,0,0,0,0,0,0,0,0,0],
        [1,2,2,1,0,0,0,0,0,0,0,0],
        [1,2,2,2,1,0,0,0,0,0,0,0],
        [1,2,2,2,2,1,0,0,0,0,0,0],
        [1,2,2,2,2,2,1,0,0,0,0,0],
        [1,2,2,2,2,2,2,1,0,0,0,0],
        [1,2,2,2,2,2,2,2,1,0,0,0],
        [1,2,2,2,2,2,2,2,2,1,0,0],
        [1,2,2,2,2,2,2,2,2,2,1,0],
        [1,2,2,2,2,2,1,1,1,1,1,0],
        [1,2,2,2,2,2,1,0,0,0,0,0],
        [1,2,2,1,2,2,1,0,0,0,0,0],
        [1,2,1,0,1,2,2,1,0,0,0,0],
        [1,1,0,0,1,2,2,1,0,0,0,0],
        [1,0,0,0,0,1,2,1,0,0,0,0],
        [0,0,0,0,0,1,1,0,0,0,0,0],
    ];

    let w = CURSOR_W;
    let h = CURSOR_H;
    let mut pixels = vec![0u8; (w * h * 4) as usize];

    for (y, row) in bitmap.iter().enumerate() {
        for (x, &val) in row.iter().enumerate() {
            let offset = (y as u32 * w + x as u32) as usize * 4;
            let (r, g, b, a) = match val {
                1 => (0, 0, 0, 255),       // Black outline
                2 => (255, 255, 255, 255), // White fill
                _ => (0, 0, 0, 0),         // Transparent
            };
            pixels[offset] = r;
            pixels[offset + 1] = g;
            pixels[offset + 2] = b;
            pixels[offset + 3] = a;
        }
    }

    (pixels, w, h)
}

impl Default for CursorState {
    fn default() -> Self {
        Self::new(480, 272)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cursor_initial_position() {
        let cursor = CursorState::new(480, 272);
        assert_eq!(cursor.x, 240);
        assert_eq!(cursor.y, 136);
        assert!(cursor.visible);
    }

    #[test]
    fn cursor_updates_on_move() {
        let mut cursor = CursorState::new(480, 272);
        cursor.handle_input(&InputEvent::CursorMove { x: 100, y: 50 });
        assert_eq!(cursor.x, 100);
        assert_eq!(cursor.y, 50);
    }

    #[test]
    fn cursor_ignores_other_events() {
        let mut cursor = CursorState::new(480, 272);
        cursor.handle_input(&InputEvent::Quit);
        assert_eq!(cursor.x, 240);
        assert_eq!(cursor.y, 136);
    }

    #[test]
    fn generate_cursor_correct_size() {
        let (pixels, w, h) = generate_cursor_pixels();
        assert_eq!(w, CURSOR_W);
        assert_eq!(h, CURSOR_H);
        assert_eq!(pixels.len(), (w * h * 4) as usize);
    }

    #[test]
    fn generate_cursor_top_left_is_outline() {
        let (pixels, _, _) = generate_cursor_pixels();
        // Top-left pixel should be black outline (r=0,g=0,b=0,a=255).
        assert_eq!(pixels[0], 0);
        assert_eq!(pixels[1], 0);
        assert_eq!(pixels[2], 0);
        assert_eq!(pixels[3], 255);
    }

    #[test]
    fn cursor_sdi_creates_object() {
        let cursor = CursorState::new(480, 272);
        let mut sdi = SdiRegistry::new();
        cursor.update_sdi(&mut sdi);
        assert!(sdi.contains(CURSOR_SDI_NAME));
        let obj = sdi.get(CURSOR_SDI_NAME).unwrap();
        assert!(obj.overlay);
        assert_eq!(obj.z, 10000);
    }

    #[test]
    fn cursor_color_has_white_fill() {
        let (pixels, w, _) = generate_cursor_pixels();
        // Pixel at (1,2) should be white fill.
        let offset = (2 * w + 1) as usize * 4;
        assert_eq!(pixels[offset], 255); // R
        assert_eq!(pixels[offset + 1], 255); // G
        assert_eq!(pixels[offset + 2], 255); // B
        assert_eq!(pixels[offset + 3], 255); // A
    }
}
