//! Software RGBA framebuffer renderer.
//!
//! Implements `SdiBackend` by drawing into a `Vec<u8>` RGBA buffer. UE5 reads
//! the buffer via `oasis_get_buffer()` and copies it to a `UTexture2D`.

use oasis_core::backend::{Color, SdiBackend, TextureId};
use oasis_core::error::{OasisError, Result};

use crate::font;

/// A stored texture for later blitting.
struct Texture {
    width: u32,
    height: u32,
    data: Vec<u8>,
}

/// Software RGBA framebuffer renderer for UE5 integration.
///
/// All rendering operations write directly to an RGBA pixel buffer.
/// The buffer is exposed to UE5 via the FFI layer. A dirty flag tracks
/// whether the buffer has changed since the last read.
pub struct Ue5Backend {
    width: u32,
    height: u32,
    buffer: Vec<u8>,
    dirty: bool,
    textures: Vec<Option<Texture>>,
    clip: Option<ClipRect>,
}

#[derive(Clone, Copy)]
struct ClipRect {
    x: i32,
    y: i32,
    w: u32,
    h: u32,
}

impl Ue5Backend {
    /// Create a new backend with the given resolution.
    pub fn new(width: u32, height: u32) -> Self {
        let size = (width * height * 4) as usize;
        Self {
            width,
            height,
            buffer: vec![0; size],
            dirty: true,
            textures: Vec::new(),
            clip: None,
        }
    }

    /// Get a read-only reference to the RGBA pixel buffer.
    pub fn buffer(&self) -> &[u8] {
        &self.buffer
    }

    /// Whether the buffer has been modified since the last `clear_dirty()`.
    pub fn is_dirty(&self) -> bool {
        self.dirty
    }

    /// Clear the dirty flag (called after UE5 reads the buffer).
    pub fn clear_dirty(&mut self) {
        self.dirty = false;
    }

    /// Buffer dimensions.
    pub fn dimensions(&self) -> (u32, u32) {
        (self.width, self.height)
    }

    /// Set a single pixel. Performs bounds and clip checking.
    fn set_pixel(&mut self, x: i32, y: i32, color: Color) {
        if x < 0 || y < 0 {
            return;
        }
        let (ux, uy) = (x as u32, y as u32);
        if ux >= self.width || uy >= self.height {
            return;
        }
        // Clip check.
        if let Some(clip) = &self.clip {
            if x < clip.x
                || y < clip.y
                || ux >= (clip.x as u32).saturating_add(clip.w)
                || uy >= (clip.y as u32).saturating_add(clip.h)
            {
                return;
            }
        }
        let offset = ((uy * self.width + ux) * 4) as usize;
        // Alpha blending (source over).
        if color.a == 255 {
            self.buffer[offset] = color.r;
            self.buffer[offset + 1] = color.g;
            self.buffer[offset + 2] = color.b;
            self.buffer[offset + 3] = 255;
        } else if color.a > 0 {
            let sa = color.a as u16;
            let da = 255 - sa;
            self.buffer[offset] =
                ((color.r as u16 * sa + self.buffer[offset] as u16 * da) / 255) as u8;
            self.buffer[offset + 1] =
                ((color.g as u16 * sa + self.buffer[offset + 1] as u16 * da) / 255) as u8;
            self.buffer[offset + 2] =
                ((color.b as u16 * sa + self.buffer[offset + 2] as u16 * da) / 255) as u8;
            self.buffer[offset + 3] = 255;
        }
    }
}

impl SdiBackend for Ue5Backend {
    fn init(&mut self, width: u32, height: u32) -> Result<()> {
        self.width = width;
        self.height = height;
        self.buffer = vec![0; (width * height * 4) as usize];
        self.dirty = true;
        Ok(())
    }

    fn clear(&mut self, color: Color) -> Result<()> {
        for pixel in self.buffer.chunks_exact_mut(4) {
            pixel[0] = color.r;
            pixel[1] = color.g;
            pixel[2] = color.b;
            pixel[3] = color.a;
        }
        self.dirty = true;
        Ok(())
    }

    fn fill_rect(&mut self, x: i32, y: i32, w: u32, h: u32, color: Color) -> Result<()> {
        for dy in 0..h as i32 {
            for dx in 0..w as i32 {
                self.set_pixel(x + dx, y + dy, color);
            }
        }
        self.dirty = true;
        Ok(())
    }

    fn draw_text(
        &mut self,
        text: &str,
        x: i32,
        y: i32,
        font_size: u16,
        color: Color,
    ) -> Result<()> {
        // Scale factor: font_size / 8 (our glyphs are 8px tall).
        let scale = if font_size >= 8 {
            (font_size / 8) as i32
        } else {
            1
        };
        let glyph_w = (font::GLYPH_WIDTH as i32) * scale;

        let mut cx = x;
        for ch in text.chars() {
            let glyph_data = font::glyph(ch);
            for row in 0..8i32 {
                let bits = glyph_data[row as usize];
                for col in 0..8i32 {
                    if bits & (0x80 >> col) != 0 {
                        // Draw a scale x scale block for each set bit.
                        for sy in 0..scale {
                            for sx in 0..scale {
                                self.set_pixel(cx + col * scale + sx, y + row * scale + sy, color);
                            }
                        }
                    }
                }
            }
            cx += glyph_w;
        }
        self.dirty = true;
        Ok(())
    }

    fn blit(&mut self, tex: TextureId, x: i32, y: i32, w: u32, h: u32) -> Result<()> {
        let idx = tex.0 as usize;
        let texture = self
            .textures
            .get(idx)
            .and_then(|t| t.as_ref())
            .ok_or_else(|| OasisError::Backend(format!("invalid texture id: {}", tex.0)))?;

        // Extract texture metadata to release the borrow on self.textures.
        let tex_w = texture.width;
        let tex_h = texture.height;
        let tex_data = texture.data.clone();

        // Simple nearest-neighbor scaling.
        for dy in 0..h {
            for dx in 0..w {
                let src_x = (dx * tex_w / w) as usize;
                let src_y = (dy * tex_h / h) as usize;
                let src_offset = (src_y * tex_w as usize + src_x) * 4;
                if src_offset + 3 < tex_data.len() {
                    let color = Color::rgba(
                        tex_data[src_offset],
                        tex_data[src_offset + 1],
                        tex_data[src_offset + 2],
                        tex_data[src_offset + 3],
                    );
                    self.set_pixel(x + dx as i32, y + dy as i32, color);
                }
            }
        }
        self.dirty = true;
        Ok(())
    }

    fn swap_buffers(&mut self) -> Result<()> {
        // No double buffering needed -- UE5 reads the buffer directly.
        // The dirty flag is already set by draw operations.
        Ok(())
    }

    fn load_texture(&mut self, width: u32, height: u32, rgba_data: &[u8]) -> Result<TextureId> {
        let expected = (width * height * 4) as usize;
        if rgba_data.len() != expected {
            return Err(OasisError::Backend(format!(
                "texture data size mismatch: expected {expected}, got {}",
                rgba_data.len()
            )));
        }

        let texture = Texture {
            width,
            height,
            data: rgba_data.to_vec(),
        };

        // Find a free slot or append.
        for (i, slot) in self.textures.iter_mut().enumerate() {
            if slot.is_none() {
                *slot = Some(texture);
                return Ok(TextureId(i as u64));
            }
        }
        let id = self.textures.len();
        self.textures.push(Some(texture));
        Ok(TextureId(id as u64))
    }

    fn destroy_texture(&mut self, tex: TextureId) -> Result<()> {
        let idx = tex.0 as usize;
        if idx < self.textures.len() {
            self.textures[idx] = None;
        }
        Ok(())
    }

    fn set_clip_rect(&mut self, x: i32, y: i32, w: u32, h: u32) -> Result<()> {
        self.clip = Some(ClipRect { x, y, w, h });
        Ok(())
    }

    fn reset_clip_rect(&mut self) -> Result<()> {
        self.clip = None;
        Ok(())
    }

    fn read_pixels(&self, x: i32, y: i32, w: u32, h: u32) -> Result<Vec<u8>> {
        let mut out = vec![0u8; (w * h * 4) as usize];
        for row in 0..h {
            let sy = (y as u32 + row) as usize;
            if sy >= self.height as usize {
                continue;
            }
            for col in 0..w {
                let sx = (x as u32 + col) as usize;
                if sx >= self.width as usize {
                    continue;
                }
                let src_idx = (sy * self.width as usize + sx) * 4;
                let dst_idx = (row as usize * w as usize + col as usize) * 4;
                out[dst_idx..dst_idx + 4].copy_from_slice(&self.buffer[src_idx..src_idx + 4]);
            }
        }
        Ok(out)
    }

    fn shutdown(&mut self) -> Result<()> {
        self.buffer.clear();
        self.textures.clear();
        log::info!("UE5 backend shut down");
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_creates_buffer() {
        let backend = Ue5Backend::new(480, 272);
        assert_eq!(backend.buffer().len(), 480 * 272 * 4);
        assert_eq!(backend.dimensions(), (480, 272));
    }

    #[test]
    fn clear_fills_buffer() {
        let mut backend = Ue5Backend::new(4, 4);
        backend.clear(Color::rgb(255, 0, 0)).unwrap();
        // Check first pixel.
        assert_eq!(backend.buffer()[0], 255); // R
        assert_eq!(backend.buffer()[1], 0); // G
        assert_eq!(backend.buffer()[2], 0); // B
        assert_eq!(backend.buffer()[3], 255); // A
        // Check last pixel.
        let last = backend.buffer().len() - 4;
        assert_eq!(backend.buffer()[last], 255);
    }

    #[test]
    fn fill_rect_draws_pixels() {
        let mut backend = Ue5Backend::new(10, 10);
        backend.clear(Color::BLACK).unwrap();
        backend
            .fill_rect(2, 2, 3, 3, Color::rgb(0, 255, 0))
            .unwrap();
        // Pixel at (2,2) should be green.
        let offset = (2 * 10 + 2) * 4;
        assert_eq!(backend.buffer()[offset], 0);
        assert_eq!(backend.buffer()[offset + 1], 255);
        // Pixel at (0,0) should still be black.
        assert_eq!(backend.buffer()[0], 0);
        assert_eq!(backend.buffer()[1], 0);
    }

    #[test]
    fn fill_rect_clips_negative() {
        let mut backend = Ue5Backend::new(10, 10);
        backend.clear(Color::BLACK).unwrap();
        // Partially off-screen rect should not panic.
        backend
            .fill_rect(-2, -2, 5, 5, Color::rgb(255, 0, 0))
            .unwrap();
        // Pixel at (0,0) should be red (within the 5x5 rect starting at -2,-2).
        assert_eq!(backend.buffer()[0], 255);
    }

    #[test]
    fn draw_text_renders_characters() {
        let mut backend = Ue5Backend::new(100, 20);
        backend.clear(Color::BLACK).unwrap();
        backend
            .draw_text("A", 0, 0, 8, Color::rgb(255, 255, 255))
            .unwrap();
        // Capital A should have some white pixels.
        let has_white = backend
            .buffer()
            .chunks_exact(4)
            .any(|px| px[0] == 255 && px[1] == 255 && px[2] == 255);
        assert!(has_white);
    }

    #[test]
    fn draw_text_scaled() {
        let mut backend = Ue5Backend::new(100, 40);
        backend.clear(Color::BLACK).unwrap();
        backend.draw_text("X", 0, 0, 16, Color::WHITE).unwrap();
        // At 2x scale, the character should occupy more pixels.
        let white_count = backend
            .buffer()
            .chunks_exact(4)
            .filter(|px| px[0] == 255)
            .count();
        assert!(white_count > 20);
    }

    #[test]
    fn load_and_blit_texture() {
        let mut backend = Ue5Backend::new(10, 10);
        backend.clear(Color::BLACK).unwrap();
        // 2x2 red texture.
        let tex_data = vec![
            255, 0, 0, 255, 255, 0, 0, 255, 255, 0, 0, 255, 255, 0, 0, 255,
        ];
        let tex_id = backend.load_texture(2, 2, &tex_data).unwrap();
        // Blit at (1,1) size 2x2.
        backend.blit(tex_id, 1, 1, 2, 2).unwrap();
        // Pixel at (1,1) should be red.
        let offset = (10 + 1) * 4;
        assert_eq!(backend.buffer()[offset], 255);
        assert_eq!(backend.buffer()[offset + 1], 0);
    }

    #[test]
    fn destroy_texture_invalidates() {
        let mut backend = Ue5Backend::new(10, 10);
        let tex_data = vec![0u8; 2 * 2 * 4];
        let tex_id = backend.load_texture(2, 2, &tex_data).unwrap();
        backend.destroy_texture(tex_id).unwrap();
        assert!(backend.blit(tex_id, 0, 0, 2, 2).is_err());
    }

    #[test]
    fn texture_data_size_mismatch() {
        let mut backend = Ue5Backend::new(10, 10);
        assert!(backend.load_texture(2, 2, &[0; 8]).is_err());
    }

    #[test]
    fn dirty_flag_tracking() {
        let mut backend = Ue5Backend::new(4, 4);
        assert!(backend.is_dirty()); // Dirty on creation.
        backend.clear_dirty();
        assert!(!backend.is_dirty());
        backend.clear(Color::BLACK).unwrap();
        assert!(backend.is_dirty());
    }

    #[test]
    fn clip_rect_restricts_drawing() {
        let mut backend = Ue5Backend::new(10, 10);
        backend.clear(Color::BLACK).unwrap();
        backend.set_clip_rect(2, 2, 3, 3).unwrap();
        backend
            .fill_rect(0, 0, 10, 10, Color::rgb(255, 0, 0))
            .unwrap();
        // Pixel at (0,0) should still be black (outside clip).
        assert_eq!(backend.buffer()[0], 0);
        // Pixel at (3,3) should be red (inside clip).
        let offset = (3 * 10 + 3) * 4;
        assert_eq!(backend.buffer()[offset], 255);

        backend.reset_clip_rect().unwrap();
        backend.fill_rect(0, 0, 1, 1, Color::WHITE).unwrap();
        // Now (0,0) should be white (no clip).
        assert_eq!(backend.buffer()[0], 255);
    }

    #[test]
    fn shutdown_clears_state() {
        let mut backend = Ue5Backend::new(4, 4);
        backend.shutdown().unwrap();
        assert!(backend.buffer().is_empty());
    }

    #[test]
    fn texture_slot_reuse() {
        let mut backend = Ue5Backend::new(4, 4);
        let data = vec![0u8; 4];
        let id0 = backend.load_texture(1, 1, &data).unwrap();
        let id1 = backend.load_texture(1, 1, &data).unwrap();
        backend.destroy_texture(id0).unwrap();
        // Next load should reuse slot 0.
        let id2 = backend.load_texture(1, 1, &data).unwrap();
        assert_eq!(id2.0, id0.0);
        assert_ne!(id1.0, id2.0);
    }
}
