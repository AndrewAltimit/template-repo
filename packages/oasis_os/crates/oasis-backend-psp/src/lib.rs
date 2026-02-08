//! PSP backend for OASIS_OS.
//!
//! Software RGBA framebuffer rendered in RAM, copied to VRAM on
//! `swap_buffers()`. Controller input via `sceCtrlPeekBufferPositive`
//! with edge detection for press/release events.
//!
//! This crate is `no_std` -- it cannot depend on `oasis-core` (which
//! requires `std`). All types are self-contained duplicates of the
//! core equivalents.

#![no_std]

extern crate alloc;

pub mod font;

use alloc::vec;
use alloc::vec::Vec;

use psp::sys::{
    self, CtrlButtons, CtrlMode, DisplayMode, DisplayPixelFormat, DisplaySetBufSync, SceCtrlData,
};

// ---------------------------------------------------------------------------
// Minimal type duplicates from oasis-core (no_std-compatible)
// ---------------------------------------------------------------------------

/// RGBA color.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Color {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub a: u8,
}

impl Color {
    pub const fn rgba(r: u8, g: u8, b: u8, a: u8) -> Self {
        Self { r, g, b, a }
    }
    pub const fn rgb(r: u8, g: u8, b: u8) -> Self {
        Self { r, g, b, a: 255 }
    }
    pub const BLACK: Self = Self::rgb(0, 0, 0);
    pub const WHITE: Self = Self::rgb(255, 255, 255);
}

/// Opaque handle to a loaded texture.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TextureId(pub u64);

/// Platform-agnostic input events (subset matching oasis-core).
#[derive(Debug, Clone, PartialEq)]
pub enum InputEvent {
    CursorMove { x: i32, y: i32 },
    ButtonPress(Button),
    ButtonRelease(Button),
    TriggerPress(Trigger),
    TriggerRelease(Trigger),
    Quit,
}

/// Buttons matching oasis-core::input::Button.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Button {
    Up,
    Down,
    Left,
    Right,
    Confirm,
    Cancel,
    Triangle,
    Square,
    Start,
    Select,
}

/// Shoulder triggers.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Trigger {
    Left,
    Right,
}

// ---------------------------------------------------------------------------
// Stored texture
// ---------------------------------------------------------------------------

struct Texture {
    width: u32,
    height: u32,
    data: Vec<u8>,
}

// ---------------------------------------------------------------------------
// Clip rectangle
// ---------------------------------------------------------------------------

#[derive(Clone, Copy)]
struct ClipRect {
    x: i32,
    y: i32,
    w: u32,
    h: u32,
}

// ---------------------------------------------------------------------------
// PSP display constants
// ---------------------------------------------------------------------------

/// Visible screen width.
pub const SCREEN_WIDTH: u32 = 480;
/// Visible screen height.
pub const SCREEN_HEIGHT: u32 = 272;
/// VRAM row stride in pixels (power-of-2 >= 480).
const BUF_WIDTH: u32 = 512;
/// Uncached VRAM base address for CPU writes.
const VRAM_UNCACHED: usize = 0x4400_0000;
/// Cached VRAM base for display controller.
const VRAM_CACHED: usize = 0x0400_0000;

// ---------------------------------------------------------------------------
// Backend
// ---------------------------------------------------------------------------

/// PSP rendering and input backend.
///
/// Draws into a software RGBA buffer in RAM. On `swap_buffers()` the buffer
/// is copied to VRAM with the correct 512-pixel stride, then
/// `sceDisplaySetFrameBuf` points the display controller at it.
pub struct PspBackend {
    width: u32,
    height: u32,
    /// Software RGBA framebuffer (width * height * 4 bytes).
    buffer: Vec<u8>,
    textures: Vec<Option<Texture>>,
    clip: Option<ClipRect>,
    /// Previous frame's button bitfield for edge detection.
    prev_buttons: u32,
    /// Accumulated analog stick cursor position.
    cursor_x: i32,
    cursor_y: i32,
}

impl PspBackend {
    /// Create a new PSP backend. Call `init()` to set up the display.
    pub fn new() -> Self {
        Self {
            width: SCREEN_WIDTH,
            height: SCREEN_HEIGHT,
            buffer: vec![0u8; (SCREEN_WIDTH * SCREEN_HEIGHT * 4) as usize],
            textures: Vec::new(),
            clip: None,
            prev_buttons: 0,
            cursor_x: (SCREEN_WIDTH / 2) as i32,
            cursor_y: (SCREEN_HEIGHT / 2) as i32,
        }
    }

    /// Initialize PSP display and controller hardware.
    pub fn init(&mut self) {
        unsafe {
            sys::sceDisplaySetMode(DisplayMode::Lcd, SCREEN_WIDTH as usize, SCREEN_HEIGHT as usize);
            sys::sceCtrlSetSamplingCycle(0);
            sys::sceCtrlSetSamplingMode(CtrlMode::Analog);
        }
    }

    /// Clear the framebuffer to a solid color.
    pub fn clear(&mut self, color: Color) {
        for pixel in self.buffer.chunks_exact_mut(4) {
            pixel[0] = color.r;
            pixel[1] = color.g;
            pixel[2] = color.b;
            pixel[3] = color.a;
        }
    }

    /// Draw a filled rectangle.
    pub fn fill_rect(&mut self, x: i32, y: i32, w: u32, h: u32, color: Color) {
        for dy in 0..h as i32 {
            for dx in 0..w as i32 {
                self.set_pixel(x + dx, y + dy, color);
            }
        }
    }

    /// Draw text using the embedded 8x8 bitmap font.
    pub fn draw_text(&mut self, text: &str, x: i32, y: i32, font_size: u16, color: Color) {
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
                        for sy in 0..scale {
                            for sx in 0..scale {
                                self.set_pixel(
                                    cx + col * scale + sx,
                                    y + row * scale + sy,
                                    color,
                                );
                            }
                        }
                    }
                }
            }
            cx += glyph_w;
        }
    }

    /// Blit a loaded texture at the given position and size.
    pub fn blit(&mut self, tex: TextureId, x: i32, y: i32, w: u32, h: u32) {
        let idx = tex.0 as usize;
        let Some(Some(texture)) = self.textures.get(idx) else {
            return;
        };
        let tex_w = texture.width;
        let tex_h = texture.height;
        let tex_data = texture.data.clone();

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
    }

    /// Load raw RGBA pixel data as a texture.
    pub fn load_texture(&mut self, width: u32, height: u32, rgba_data: &[u8]) -> Option<TextureId> {
        let expected = (width * height * 4) as usize;
        if rgba_data.len() != expected {
            return None;
        }
        let texture = Texture {
            width,
            height,
            data: rgba_data.to_vec(),
        };
        // Reuse free slot.
        for (i, slot) in self.textures.iter_mut().enumerate() {
            if slot.is_none() {
                *slot = Some(texture);
                return Some(TextureId(i as u64));
            }
        }
        let id = self.textures.len();
        self.textures.push(Some(texture));
        Some(TextureId(id as u64))
    }

    /// Destroy a loaded texture.
    pub fn destroy_texture(&mut self, tex: TextureId) {
        let idx = tex.0 as usize;
        if idx < self.textures.len() {
            self.textures[idx] = None;
        }
    }

    /// Set the clipping rectangle.
    pub fn set_clip_rect(&mut self, x: i32, y: i32, w: u32, h: u32) {
        self.clip = Some(ClipRect { x, y, w, h });
    }

    /// Reset clipping to full screen.
    pub fn reset_clip_rect(&mut self) {
        self.clip = None;
    }

    /// Copy the software framebuffer to VRAM and present.
    ///
    /// The PSP display controller expects rows of `BUF_WIDTH` (512) pixels,
    /// but only the leftmost 480 are visible. We copy each row individually
    /// to account for the stride difference.
    pub fn swap_buffers(&mut self) {
        unsafe {
            let vram = VRAM_UNCACHED as *mut u8;
            let src = self.buffer.as_ptr();
            let visible_row_bytes = (self.width * 4) as usize;
            let stride_bytes = (BUF_WIDTH * 4) as usize;

            for row in 0..self.height as usize {
                let src_offset = row * visible_row_bytes;
                let dst_offset = row * stride_bytes;
                core::ptr::copy_nonoverlapping(
                    src.add(src_offset),
                    vram.add(dst_offset),
                    visible_row_bytes,
                );
            }

            sys::sceDisplaySetFrameBuf(
                VRAM_CACHED as *const u8,
                BUF_WIDTH as usize,
                DisplayPixelFormat::Psm8888,
                DisplaySetBufSync::NextFrame,
            );
            sys::sceDisplayWaitVblankStart();
        }
    }

    /// Poll controller input, returning events with edge detection.
    pub fn poll_events(&mut self) -> Vec<InputEvent> {
        let mut events = Vec::new();
        let mut pad = SceCtrlData::default();

        unsafe {
            sys::sceCtrlPeekBufferPositive(&mut pad as *mut SceCtrlData, 1);
        }

        let curr = pad.buttons.bits();
        let pressed = curr & !self.prev_buttons;
        let released = !curr & self.prev_buttons;
        self.prev_buttons = curr;

        // Map PSP buttons to our Button/Trigger enums.
        Self::check_button(pressed, released, CtrlButtons::UP, Button::Up, &mut events);
        Self::check_button(
            pressed,
            released,
            CtrlButtons::DOWN,
            Button::Down,
            &mut events,
        );
        Self::check_button(
            pressed,
            released,
            CtrlButtons::LEFT,
            Button::Left,
            &mut events,
        );
        Self::check_button(
            pressed,
            released,
            CtrlButtons::RIGHT,
            Button::Right,
            &mut events,
        );
        Self::check_button(
            pressed,
            released,
            CtrlButtons::CROSS,
            Button::Confirm,
            &mut events,
        );
        Self::check_button(
            pressed,
            released,
            CtrlButtons::CIRCLE,
            Button::Cancel,
            &mut events,
        );
        Self::check_button(
            pressed,
            released,
            CtrlButtons::TRIANGLE,
            Button::Triangle,
            &mut events,
        );
        Self::check_button(
            pressed,
            released,
            CtrlButtons::SQUARE,
            Button::Square,
            &mut events,
        );
        Self::check_button(
            pressed,
            released,
            CtrlButtons::START,
            Button::Start,
            &mut events,
        );
        Self::check_button(
            pressed,
            released,
            CtrlButtons::SELECT,
            Button::Select,
            &mut events,
        );

        // Shoulder triggers.
        Self::check_trigger(
            pressed,
            released,
            CtrlButtons::LTRIGGER,
            Trigger::Left,
            &mut events,
        );
        Self::check_trigger(
            pressed,
            released,
            CtrlButtons::RTRIGGER,
            Trigger::Right,
            &mut events,
        );

        // Analog stick -> cursor movement with deadzone.
        let dx = pad.lx as i32 - 128;
        let dy = pad.ly as i32 - 128;
        const DEADZONE: i32 = 40;
        if dx.abs() > DEADZONE || dy.abs() > DEADZONE {
            let move_x = if dx.abs() > DEADZONE { dx / 16 } else { 0 };
            let move_y = if dy.abs() > DEADZONE { dy / 16 } else { 0 };
            self.cursor_x = (self.cursor_x + move_x).clamp(0, self.width as i32 - 1);
            self.cursor_y = (self.cursor_y + move_y).clamp(0, self.height as i32 - 1);
            events.push(InputEvent::CursorMove {
                x: self.cursor_x,
                y: self.cursor_y,
            });
        }

        events
    }

    /// Current cursor position (for rendering the cursor sprite).
    pub fn cursor_pos(&self) -> (i32, i32) {
        (self.cursor_x, self.cursor_y)
    }

    /// Read-only access to the software framebuffer.
    pub fn buffer(&self) -> &[u8] {
        &self.buffer
    }

    // -- Private helpers ----------------------------------------------------

    /// Set a pixel with bounds checking, clip checking, and alpha blending.
    fn set_pixel(&mut self, x: i32, y: i32, color: Color) {
        if x < 0 || y < 0 {
            return;
        }
        let (ux, uy) = (x as u32, y as u32);
        if ux >= self.width || uy >= self.height {
            return;
        }
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

    /// Emit press/release events for a button if its state changed.
    fn check_button(
        pressed: u32,
        released: u32,
        psp_btn: CtrlButtons,
        btn: Button,
        events: &mut Vec<InputEvent>,
    ) {
        let mask = psp_btn.bits();
        if pressed & mask != 0 {
            events.push(InputEvent::ButtonPress(btn));
        }
        if released & mask != 0 {
            events.push(InputEvent::ButtonRelease(btn));
        }
    }

    /// Emit press/release events for a shoulder trigger.
    fn check_trigger(
        pressed: u32,
        released: u32,
        psp_btn: CtrlButtons,
        trigger: Trigger,
        events: &mut Vec<InputEvent>,
    ) {
        let mask = psp_btn.bits();
        if pressed & mask != 0 {
            events.push(InputEvent::TriggerPress(trigger));
        }
        if released & mask != 0 {
            events.push(InputEvent::TriggerRelease(trigger));
        }
    }
}

// ---------------------------------------------------------------------------
// Wallpaper generator (procedural PSIX-style gradient)
// ---------------------------------------------------------------------------

/// Generate a PSIX-style green/yellow/orange gradient wallpaper as RGBA bytes.
pub fn generate_gradient(w: u32, h: u32) -> Vec<u8> {
    let mut data = vec![0u8; (w * h * 4) as usize];
    for y in 0..h {
        for x in 0..w {
            let fx = x as f32 / w as f32;
            let fy = y as f32 / h as f32;
            // HSV-like interpolation: hue shifts from green (120) to orange (30).
            let hue = 120.0 - 90.0 * fx;
            let sat = 0.7 + 0.3 * fy;
            let val = 0.85 - 0.25 * fy;
            let (r, g, b) = hsv_to_rgb(hue, sat, val);
            let offset = ((y * w + x) * 4) as usize;
            data[offset] = r;
            data[offset + 1] = g;
            data[offset + 2] = b;
            data[offset + 3] = 255;
        }
    }
    data
}

/// HSV to RGB conversion (h in 0..360, s/v in 0..1).
fn hsv_to_rgb(h: f32, s: f32, v: f32) -> (u8, u8, u8) {
    let c = v * s;
    let rem = (h / 60.0) % 2.0 - 1.0;
    let abs_rem = if rem < 0.0 { -rem } else { rem };
    let x = c * (1.0 - abs_rem);
    let m = v - c;
    let (r1, g1, b1) = if h < 60.0 {
        (c, x, 0.0)
    } else if h < 120.0 {
        (x, c, 0.0)
    } else if h < 180.0 {
        (0.0, c, x)
    } else if h < 240.0 {
        (0.0, x, c)
    } else if h < 300.0 {
        (x, 0.0, c)
    } else {
        (c, 0.0, x)
    };
    (
        ((r1 + m) * 255.0) as u8,
        ((g1 + m) * 255.0) as u8,
        ((b1 + m) * 255.0) as u8,
    )
}

// ---------------------------------------------------------------------------
// Cursor generator (procedural arrow)
// ---------------------------------------------------------------------------

/// Width of the procedural cursor sprite.
pub const CURSOR_W: u32 = 12;
/// Height of the procedural cursor sprite.
pub const CURSOR_H: u32 = 18;

/// Generate a white arrow cursor with black outline as RGBA pixels.
pub fn generate_cursor_pixels() -> Vec<u8> {
    // 12x18 arrow cursor bitmap: 1 = white fill, 2 = black outline, 0 = transparent.
    #[rustfmt::skip]
    let bitmap: [[u8; 12]; 18] = [
        [2,0,0,0,0,0,0,0,0,0,0,0],
        [2,2,0,0,0,0,0,0,0,0,0,0],
        [2,1,2,0,0,0,0,0,0,0,0,0],
        [2,1,1,2,0,0,0,0,0,0,0,0],
        [2,1,1,1,2,0,0,0,0,0,0,0],
        [2,1,1,1,1,2,0,0,0,0,0,0],
        [2,1,1,1,1,1,2,0,0,0,0,0],
        [2,1,1,1,1,1,1,2,0,0,0,0],
        [2,1,1,1,1,1,1,1,2,0,0,0],
        [2,1,1,1,1,1,1,1,1,2,0,0],
        [2,1,1,1,1,1,1,1,1,1,2,0],
        [2,1,1,1,1,1,2,2,2,2,2,0],
        [2,1,1,1,2,1,2,0,0,0,0,0],
        [2,1,1,2,0,2,1,2,0,0,0,0],
        [2,1,2,0,0,2,1,2,0,0,0,0],
        [2,2,0,0,0,0,2,1,2,0,0,0],
        [2,0,0,0,0,0,2,1,2,0,0,0],
        [0,0,0,0,0,0,0,2,0,0,0,0],
    ];
    let mut data = vec![0u8; (CURSOR_W * CURSOR_H * 4) as usize];
    for (y, row) in bitmap.iter().enumerate() {
        for (x, &val) in row.iter().enumerate() {
            let offset = (y * CURSOR_W as usize + x) * 4;
            match val {
                1 => {
                    data[offset] = 255;
                    data[offset + 1] = 255;
                    data[offset + 2] = 255;
                    data[offset + 3] = 255;
                }
                2 => {
                    data[offset] = 0;
                    data[offset + 1] = 0;
                    data[offset + 2] = 0;
                    data[offset + 3] = 255;
                }
                _ => {} // transparent (alpha stays 0)
            }
        }
    }
    data
}

// ---------------------------------------------------------------------------
// Status bar helpers (minimal, no std::time dependency)
// ---------------------------------------------------------------------------

/// Draw a PSIX-style status bar at the top of the screen.
pub fn draw_status_bar(backend: &mut PspBackend, version: &str) {
    let bar_color = Color::rgba(30, 80, 30, 200);
    backend.fill_rect(0, 0, SCREEN_WIDTH, 18, bar_color);
    backend.draw_text(version, 4, 4, 8, Color::WHITE);
}

/// Draw a PSIX-style bottom bar with navigation hints.
pub fn draw_bottom_bar(backend: &mut PspBackend, hint: &str) {
    let bar_y = (SCREEN_HEIGHT - 18) as i32;
    let bar_color = Color::rgba(30, 80, 30, 200);
    backend.fill_rect(0, bar_y, SCREEN_WIDTH, 18, bar_color);
    backend.draw_text(hint, 4, bar_y + 4, 8, Color::WHITE);
}
