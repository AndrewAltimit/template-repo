//! SDL2 backend for OASIS_OS.
//!
//! Implements `SdiBackend` and `InputBackend` using SDL2. Used for desktop
//! development and Raspberry Pi deployment (via SDL2's kmsdrm or X11 backend).

mod font;
mod sdl_audio;

use std::collections::HashMap;

use sdl2::EventPump;
use sdl2::event::Event;
use sdl2::keyboard::Keycode;
use sdl2::pixels::PixelFormatEnum;
use sdl2::rect::Rect;
use sdl2::render::{Canvas, Texture, TextureCreator};
use sdl2::video::{Window, WindowContext};

use oasis_core::backend::{Color, SdiBackend, TextureId};
use oasis_core::error::{OasisError, Result};
use oasis_core::input::{Button, InputEvent, Trigger};

pub use sdl_audio::SdlAudioBackend;

/// SDL2 rendering and input backend.
///
/// Supports solid-color rects, 8x8 bitmap text, and RGBA texture loading/blitting.
///
/// # Safety
///
/// `textures` is declared before `texture_creator` so that Rust's drop order
/// (declaration order) destroys all textures before the creator they borrow from.
/// The `Texture<'static>` lifetime is erased via transmute in `load_texture()` --
/// this is sound because the `TextureCreator` always outlives the textures.
pub struct SdlBackend {
    canvas: Canvas<Window>,
    event_pump: EventPump,
    textures: HashMap<u64, Texture<'static>>,
    texture_creator: TextureCreator<WindowContext>,
    next_texture_id: u64,
}

impl SdlBackend {
    /// Create a new SDL2 backend with a window.
    pub fn new(title: &str, width: u32, height: u32) -> Result<Self> {
        let sdl = sdl2::init().map_err(|e| OasisError::Backend(e.to_string()))?;
        let video = sdl
            .video()
            .map_err(|e| OasisError::Backend(e.to_string()))?;
        let window = video
            .window(title, width, height)
            .position_centered()
            .build()
            .map_err(|e| OasisError::Backend(e.to_string()))?;
        let canvas = window
            .into_canvas()
            .accelerated()
            .present_vsync()
            .build()
            .map_err(|e| OasisError::Backend(e.to_string()))?;
        let texture_creator = canvas.texture_creator();
        let event_pump = sdl
            .event_pump()
            .map_err(|e| OasisError::Backend(e.to_string()))?;

        log::info!("SDL2 backend initialized: {width}x{height}");

        Ok(Self {
            canvas,
            event_pump,
            textures: HashMap::new(),
            texture_creator,
            next_texture_id: 1,
        })
    }
}

impl SdiBackend for SdlBackend {
    fn init(&mut self, _width: u32, _height: u32) -> Result<()> {
        Ok(())
    }

    fn clear(&mut self, color: Color) -> Result<()> {
        self.canvas.set_draw_color(sdl2::pixels::Color::RGBA(
            color.r, color.g, color.b, color.a,
        ));
        self.canvas.clear();
        Ok(())
    }

    fn blit(&mut self, tex: TextureId, x: i32, y: i32, w: u32, h: u32) -> Result<()> {
        let texture = self
            .textures
            .get(&tex.0)
            .ok_or_else(|| OasisError::Backend(format!("texture not found: {}", tex.0)))?;
        self.canvas
            .copy(texture, None, Rect::new(x, y, w, h))
            .map_err(|e| OasisError::Backend(e.to_string()))?;
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
        let sdl_color = sdl2::pixels::Color::RGBA(color.r, color.g, color.b, color.a);
        self.canvas.set_draw_color(sdl_color);

        let mut cx = x;
        for ch in text.chars() {
            let glyph_data = font::glyph(ch);
            for row in 0..8i32 {
                let bits = glyph_data[row as usize];
                for col in 0..8i32 {
                    if bits & (0x80 >> col) != 0 {
                        let px = cx + col * scale;
                        let py = y + row * scale;
                        if scale == 1 {
                            // Single pixel -- use draw_point for speed.
                            let _ = self.canvas.draw_point(sdl2::rect::Point::new(px, py));
                        } else {
                            let _ = self.canvas.fill_rect(Rect::new(
                                px,
                                py,
                                scale as u32,
                                scale as u32,
                            ));
                        }
                    }
                }
            }
            cx += glyph_w;
        }
        Ok(())
    }

    fn fill_rect(&mut self, x: i32, y: i32, w: u32, h: u32, color: Color) -> Result<()> {
        if color.a < 255 {
            self.canvas.set_blend_mode(sdl2::render::BlendMode::Blend);
        } else {
            self.canvas.set_blend_mode(sdl2::render::BlendMode::None);
        }
        self.canvas.set_draw_color(sdl2::pixels::Color::RGBA(
            color.r, color.g, color.b, color.a,
        ));
        self.canvas
            .fill_rect(Rect::new(x, y, w, h))
            .map_err(|e| OasisError::Backend(e.to_string()))?;
        Ok(())
    }

    fn swap_buffers(&mut self) -> Result<()> {
        self.canvas.present();
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

        let mut texture = self
            .texture_creator
            .create_texture_streaming(PixelFormatEnum::ABGR8888, width, height)
            .map_err(|e| OasisError::Backend(e.to_string()))?;

        texture
            .with_lock(None, |buffer: &mut [u8], _pitch: usize| {
                buffer[..expected].copy_from_slice(rgba_data);
            })
            .map_err(|e| OasisError::Backend(e.to_string()))?;

        // Enable alpha blending so transparent pixels work.
        texture.set_blend_mode(sdl2::render::BlendMode::Blend);

        // SAFETY: The texture borrows from self.texture_creator which lives in the
        // same struct. `textures` is declared before `texture_creator`, so Rust drops
        // textures first. The erased lifetime is therefore always valid.
        let texture: Texture<'static> = unsafe { std::mem::transmute(texture) };

        let id = self.next_texture_id;
        self.next_texture_id += 1;
        self.textures.insert(id, texture);
        Ok(TextureId(id))
    }

    fn destroy_texture(&mut self, tex: TextureId) -> Result<()> {
        self.textures.remove(&tex.0);
        Ok(())
    }

    fn set_clip_rect(&mut self, x: i32, y: i32, w: u32, h: u32) -> Result<()> {
        self.canvas.set_clip_rect(Rect::new(x, y, w, h));
        Ok(())
    }

    fn reset_clip_rect(&mut self) -> Result<()> {
        self.canvas.set_clip_rect(None);
        Ok(())
    }

    fn read_pixels(&self, x: i32, y: i32, w: u32, h: u32) -> Result<Vec<u8>> {
        let rect = Rect::new(x, y, w, h);
        self.canvas
            .read_pixels(rect, PixelFormatEnum::ABGR8888)
            .map_err(|e| OasisError::Backend(e.to_string()))
    }

    fn shutdown(&mut self) -> Result<()> {
        log::info!("SDL2 backend shut down");
        Ok(())
    }
}

impl oasis_core::backend::InputBackend for SdlBackend {
    fn poll_events(&mut self) -> Vec<InputEvent> {
        let mut events = Vec::new();
        for event in self.event_pump.poll_iter() {
            if let Some(e) = map_sdl_event(event) {
                events.push(e);
            }
        }
        events
    }
}

/// Map an SDL2 event to an OASIS_OS input event.
fn map_sdl_event(event: Event) -> Option<InputEvent> {
    match event {
        Event::Quit { .. } => Some(InputEvent::Quit),
        Event::KeyDown {
            keycode: Some(key), ..
        } => map_key_down(key),
        Event::KeyUp {
            keycode: Some(key), ..
        } => map_key_up(key),
        Event::MouseMotion { x, y, .. } => Some(InputEvent::CursorMove { x, y }),
        Event::MouseButtonDown { x, y, .. } => Some(InputEvent::PointerClick { x, y }),
        Event::MouseButtonUp { x, y, .. } => Some(InputEvent::PointerRelease { x, y }),
        Event::Window {
            win_event: sdl2::event::WindowEvent::FocusGained,
            ..
        } => Some(InputEvent::FocusGained),
        Event::Window {
            win_event: sdl2::event::WindowEvent::FocusLost,
            ..
        } => Some(InputEvent::FocusLost),
        Event::TextInput { text, .. } => text.chars().next().map(InputEvent::TextInput),
        _ => None,
    }
}

fn map_key_down(key: Keycode) -> Option<InputEvent> {
    match key {
        Keycode::Up => Some(InputEvent::ButtonPress(Button::Up)),
        Keycode::Down => Some(InputEvent::ButtonPress(Button::Down)),
        Keycode::Left => Some(InputEvent::ButtonPress(Button::Left)),
        Keycode::Right => Some(InputEvent::ButtonPress(Button::Right)),
        Keycode::Return => Some(InputEvent::ButtonPress(Button::Confirm)),
        Keycode::Escape => Some(InputEvent::ButtonPress(Button::Cancel)),
        Keycode::Space => Some(InputEvent::ButtonPress(Button::Triangle)),
        Keycode::Tab => Some(InputEvent::ButtonPress(Button::Square)),
        Keycode::F1 => Some(InputEvent::ButtonPress(Button::Start)),
        Keycode::F2 => Some(InputEvent::ButtonPress(Button::Select)),
        Keycode::Backspace => Some(InputEvent::Backspace),
        Keycode::Q => Some(InputEvent::TriggerPress(Trigger::Left)),
        Keycode::E => Some(InputEvent::TriggerPress(Trigger::Right)),
        _ => None,
    }
}

fn map_key_up(key: Keycode) -> Option<InputEvent> {
    match key {
        Keycode::Up => Some(InputEvent::ButtonRelease(Button::Up)),
        Keycode::Down => Some(InputEvent::ButtonRelease(Button::Down)),
        Keycode::Left => Some(InputEvent::ButtonRelease(Button::Left)),
        Keycode::Right => Some(InputEvent::ButtonRelease(Button::Right)),
        Keycode::Return => Some(InputEvent::ButtonRelease(Button::Confirm)),
        Keycode::Escape => Some(InputEvent::ButtonRelease(Button::Cancel)),
        Keycode::Space => Some(InputEvent::ButtonRelease(Button::Triangle)),
        Keycode::Tab => Some(InputEvent::ButtonRelease(Button::Square)),
        Keycode::F1 => Some(InputEvent::ButtonRelease(Button::Start)),
        Keycode::F2 => Some(InputEvent::ButtonRelease(Button::Select)),
        Keycode::Q => Some(InputEvent::TriggerRelease(Trigger::Left)),
        Keycode::E => Some(InputEvent::TriggerRelease(Trigger::Right)),
        _ => None,
    }
}
