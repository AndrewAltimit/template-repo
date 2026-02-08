//! PSP backend for OASIS_OS.
//!
//! Hardware-accelerated rendering via the PSP Graphics Engine (sceGu/sceGum).
//! All rectangles, textures, and text are drawn as GU `Sprites` primitives,
//! offloading work from the 333MHz MIPS CPU to the dedicated GE hardware.
//!
//! Controller input via `sceCtrlPeekBufferPositive` with edge detection for
//! press/release events.
//!
//! This crate is `no_std` -- it cannot depend on `oasis-core` (which
//! requires `std`). All types are self-contained duplicates of the
//! core equivalents.

#![no_std]

extern crate alloc;

pub mod font;

use alloc::alloc::{alloc, dealloc, Layout};
use alloc::vec;
use alloc::vec::Vec;
use core::ffi::c_void;
use core::mem::size_of;
use core::ptr;

use psp::sys::{
    self, BlendFactor, BlendOp, ClearBuffer, CtrlButtons, CtrlMode, DisplayPixelFormat,
    GuContextType, GuPrimitive, GuState, GuSyncBehavior, GuSyncMode, MatrixMode, MipmapLevel,
    SceCtrlData, TextureColorComponent, TextureEffect, TextureFilter, TexturePixelFormat,
    VertexType,
};
use psp::vram_alloc::get_vram_allocator;

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

    /// Convert to PSP ABGR u32 format used by sceGu functions.
    pub const fn to_abgr(&self) -> u32 {
        (self.a as u32) << 24 | (self.b as u32) << 16 | (self.g as u32) << 8 | self.r as u32
    }
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
// Vertex types for 2D GU rendering
// ---------------------------------------------------------------------------

/// Colored vertex for fill_rect (no texture).
#[repr(C, align(4))]
struct ColorVertex {
    color: u32,
    x: i16,
    y: i16,
    z: i16,
    _pad: i16,
}

/// Vertex type flags for ColorVertex.
const COLOR_VTYPE: VertexType = VertexType::from_bits_truncate(
    VertexType::COLOR_8888.bits() | VertexType::VERTEX_16BIT.bits() | VertexType::TRANSFORM_2D.bits(),
);

/// Textured + colored vertex for blit and draw_text.
#[repr(C, align(4))]
struct TexturedColorVertex {
    u: i16,
    v: i16,
    color: u32,
    x: i16,
    y: i16,
    z: i16,
    _pad: i16,
}

/// Vertex type flags for TexturedColorVertex.
const TEXTURED_COLOR_VTYPE: VertexType = VertexType::from_bits_truncate(
    VertexType::TEXTURE_16BIT.bits()
        | VertexType::COLOR_8888.bits()
        | VertexType::VERTEX_16BIT.bits()
        | VertexType::TRANSFORM_2D.bits(),
);

// ---------------------------------------------------------------------------
// Stored texture
// ---------------------------------------------------------------------------

struct Texture {
    width: u32,
    height: u32,
    /// Power-of-2 buffer width for GU.
    buf_w: u32,
    /// Power-of-2 buffer height for GU.
    buf_h: u32,
    /// 16-byte aligned pixel data pointer (RAM).
    data: *mut u8,
    /// Layout used for deallocation.
    layout: Layout,
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

/// Font atlas dimensions.
const FONT_ATLAS_W: u32 = 128;
const FONT_ATLAS_H: u32 = 64;
/// Glyphs per row in the atlas.
const ATLAS_COLS: u32 = 16;

// ---------------------------------------------------------------------------
// Display list (16-byte aligned, in BSS)
// ---------------------------------------------------------------------------

const DISPLAY_LIST_SIZE: usize = 0x40000; // 256 KB

#[repr(C, align(16))]
struct Align16<T>(T);

static mut DISPLAY_LIST: Align16<[u8; DISPLAY_LIST_SIZE]> = Align16([0u8; DISPLAY_LIST_SIZE]);

// ---------------------------------------------------------------------------
// Backend
// ---------------------------------------------------------------------------

/// PSP rendering and input backend.
///
/// Draws using the PSP Graphics Engine (GE) via sceGu. All rendering calls
/// add commands to a display list; `swap_buffers()` submits the list, waits
/// for vblank, swaps framebuffers, and opens the next frame's list.
pub struct PspBackend {
    width: u32,
    height: u32,
    textures: Vec<Option<Texture>>,
    /// Previous frame's button bitfield for edge detection.
    prev_buttons: u32,
    /// Accumulated analog stick cursor position.
    cursor_x: i32,
    cursor_y: i32,
    /// 16-byte aligned RAM pointer to the font atlas texture (128x64 RGBA).
    font_atlas_ptr: *mut u8,
}

impl PspBackend {
    /// Create a new PSP backend. Call `init()` to set up the display.
    pub fn new() -> Self {
        Self {
            width: SCREEN_WIDTH,
            height: SCREEN_HEIGHT,
            textures: Vec::new(),
            prev_buttons: 0,
            cursor_x: (SCREEN_WIDTH / 2) as i32,
            cursor_y: (SCREEN_HEIGHT / 2) as i32,
            font_atlas_ptr: ptr::null_mut(),
        }
    }

    /// Initialize PSP display via GU and controller hardware.
    pub fn init(&mut self) {
        unsafe {
            // Controller setup.
            sys::sceCtrlSetSamplingCycle(0);
            sys::sceCtrlSetSamplingMode(CtrlMode::Analog);

            // VRAM allocation: 2 framebuffers (no depth buffer for 2D).
            let allocator = get_vram_allocator().unwrap();
            let fbp0 = allocator
                .alloc_texture_pixels(BUF_WIDTH, SCREEN_HEIGHT, TexturePixelFormat::Psm8888)
                .unwrap();
            let fbp1 = allocator
                .alloc_texture_pixels(BUF_WIDTH, SCREEN_HEIGHT, TexturePixelFormat::Psm8888)
                .unwrap();

            let fbp0_zero = fbp0.as_mut_ptr_from_zero() as *mut c_void;
            let fbp1_zero = fbp1.as_mut_ptr_from_zero() as *mut c_void;

            // Font atlas in RAM (16-byte aligned). Using RAM avoids PPSSPP
            // texture cache issues with direct VRAM writes. The GE reads it
            // via DMA using the uncached mirror address.
            let atlas_size = (FONT_ATLAS_W * FONT_ATLAS_H * 4) as usize;
            let atlas_layout = Layout::from_size_align(atlas_size, 16).unwrap();
            let atlas_ptr = alloc(atlas_layout);
            self.font_atlas_ptr = atlas_ptr;

            // GU initialization.
            sys::sceGuInit();
            sys::sceGuStart(
                GuContextType::Direct,
                &raw mut DISPLAY_LIST as *mut c_void,
            );

            // Draw buffer (render target) and display buffer.
            sys::sceGuDrawBuffer(DisplayPixelFormat::Psm8888, fbp0_zero, BUF_WIDTH as i32);
            sys::sceGuDispBuffer(
                SCREEN_WIDTH as i32,
                SCREEN_HEIGHT as i32,
                fbp1_zero,
                BUF_WIDTH as i32,
            );

            // Viewport and coordinate setup.
            sys::sceGuOffset(2048 - (SCREEN_WIDTH / 2), 2048 - (SCREEN_HEIGHT / 2));
            sys::sceGuViewport(2048, 2048, SCREEN_WIDTH as i32, SCREEN_HEIGHT as i32);

            // Scissor (full screen).
            sys::sceGuScissor(0, 0, SCREEN_WIDTH as i32, SCREEN_HEIGHT as i32);
            sys::sceGuEnable(GuState::ScissorTest);

            // Alpha blending.
            sys::sceGuEnable(GuState::Blend);
            sys::sceGuBlendFunc(
                BlendOp::Add,
                BlendFactor::SrcAlpha,
                BlendFactor::OneMinusSrcAlpha,
                0,
                0,
            );

            // Texture state.
            sys::sceGuEnable(GuState::Texture2D);
            sys::sceGuTexFunc(TextureEffect::Modulate, TextureColorComponent::Rgba);
            sys::sceGuTexFilter(TextureFilter::Nearest, TextureFilter::Nearest);

            // Projection: orthographic 2D.
            sys::sceGumMatrixMode(MatrixMode::Projection);
            sys::sceGumLoadIdentity();
            sys::sceGumOrtho(
                0.0,
                SCREEN_WIDTH as f32,
                SCREEN_HEIGHT as f32,
                0.0,
                -1.0,
                1.0,
            );

            // View and model: identity.
            sys::sceGumMatrixMode(MatrixMode::View);
            sys::sceGumLoadIdentity();
            sys::sceGumMatrixMode(MatrixMode::Model);
            sys::sceGumLoadIdentity();

            // Finalize init list, sync, enable display.
            sys::sceGuFinish();
            sys::sceGuSync(GuSyncMode::Finish, GuSyncBehavior::Wait);
            sys::sceDisplayWaitVblankStart();
            sys::sceGuDisplay(true);

            // Build font atlas in RAM.
            self.build_font_atlas(atlas_ptr);

            // Open the first frame's display list.
            sys::sceGuStart(
                GuContextType::Direct,
                &raw mut DISPLAY_LIST as *mut c_void,
            );
        }
    }

    /// Build the 128x64 font atlas in a RAM buffer.
    ///
    /// 16 glyphs per row, 6 rows (95 glyphs for ASCII 32-126).
    /// Each glyph is 8x8. White where bit is set, transparent elsewhere.
    unsafe fn build_font_atlas(&self, buf: *mut u8) {
        let pixels = buf as *mut u32;
        let stride = FONT_ATLAS_W;
        let total = (FONT_ATLAS_W * FONT_ATLAS_H) as usize;

        // Zero the entire atlas first (manual loop -- see MEMORY.md footgun).
        for i in 0..total {
            unsafe { pixels.add(i).write(0u32) };
        }

        for idx in 0u32..95 {
            let col = idx % ATLAS_COLS;
            let row = idx / ATLAS_COLS;
            let glyph_data = font::glyph((idx + 32) as u8 as char);

            for gy in 0..8u32 {
                let bits = glyph_data[gy as usize];
                for gx in 0..8u32 {
                    if bits & (0x80 >> gx) != 0 {
                        let px = col * 8 + gx;
                        let py = row * 8 + gy;
                        let offset = (py * stride + px) as usize;
                        unsafe { pixels.add(offset).write(0xFFFF_FFFFu32) }; // opaque white
                    }
                }
            }
        }
    }

    /// Clear the screen to a solid color.
    pub fn clear(&mut self, color: Color) {
        unsafe {
            sys::sceGuClearColor(color.to_abgr());
            sys::sceGuClear(ClearBuffer::COLOR_BUFFER_BIT | ClearBuffer::FAST_CLEAR_BIT);
        }
    }

    /// Draw a filled rectangle.
    pub fn fill_rect(&mut self, x: i32, y: i32, w: u32, h: u32, color: Color) {
        unsafe {
            sys::sceGuDisable(GuState::Texture2D);

            let verts = sys::sceGuGetMemory(
                (2 * size_of::<ColorVertex>()) as i32,
            ) as *mut ColorVertex;
            if verts.is_null() {
                sys::sceGuEnable(GuState::Texture2D);
                return;
            }

            let abgr = color.to_abgr();
            let x1 = x as i16;
            let y1 = y as i16;
            let x2 = (x + w as i32) as i16;
            let y2 = (y + h as i32) as i16;

            ptr::write(
                verts,
                ColorVertex { color: abgr, x: x1, y: y1, z: 0, _pad: 0 },
            );
            ptr::write(
                verts.add(1),
                ColorVertex { color: abgr, x: x2, y: y2, z: 0, _pad: 0 },
            );

            sys::sceGuDrawArray(
                GuPrimitive::Sprites,
                COLOR_VTYPE,
                2,
                ptr::null(),
                verts as *const c_void,
            );
            sys::sceGuEnable(GuState::Texture2D);
        }
    }

    /// Draw text using the embedded 8x8 bitmap font via the GU font atlas.
    pub fn draw_text(&mut self, text: &str, x: i32, y: i32, font_size: u16, color: Color) {
        let scale = if font_size >= 8 {
            (font_size / 8) as i32
        } else {
            1
        };
        let glyph_w = (font::GLYPH_WIDTH as i32) * scale;
        let abgr = color.to_abgr();

        unsafe {
            // Bind font atlas (RAM texture -- use uncached pointer + flush).
            let uncached_atlas = (self.font_atlas_ptr as usize | 0x4000_0000) as *const c_void;
            sys::sceGuTexMode(TexturePixelFormat::Psm8888, 0, 0, 0);
            sys::sceGuTexImage(
                MipmapLevel::None,
                FONT_ATLAS_W as i32,
                FONT_ATLAS_H as i32,
                FONT_ATLAS_W as i32,
                uncached_atlas,
            );
            sys::sceGuTexFunc(TextureEffect::Modulate, TextureColorComponent::Rgba);
            sys::sceGuTexFlush();
            sys::sceGuTexSync();

            let mut cx = x;
            for ch in text.chars() {
                let idx = (ch as u32).wrapping_sub(32);
                // Out-of-range characters get the fallback block (draw as filled rect).
                let (u0, v0) = if idx < 95 {
                    let col = idx % ATLAS_COLS;
                    let row = idx / ATLAS_COLS;
                    ((col * 8) as i16, (row * 8) as i16)
                } else {
                    // Use space glyph for out-of-range (index 0 = space).
                    (0i16, 0i16)
                };

                let verts = sys::sceGuGetMemory(
                    (2 * size_of::<TexturedColorVertex>()) as i32,
                ) as *mut TexturedColorVertex;
                if verts.is_null() {
                    break;
                }

                ptr::write(
                    verts,
                    TexturedColorVertex {
                        u: u0,
                        v: v0,
                        color: abgr,
                        x: cx as i16,
                        y: y as i16,
                        z: 0,
                        _pad: 0,
                    },
                );
                ptr::write(
                    verts.add(1),
                    TexturedColorVertex {
                        u: u0 + 8,
                        v: v0 + 8,
                        color: abgr,
                        x: (cx + 8 * scale) as i16,
                        y: (y + 8 * scale) as i16,
                        z: 0,
                        _pad: 0,
                    },
                );

                sys::sceGuDrawArray(
                    GuPrimitive::Sprites,
                    TEXTURED_COLOR_VTYPE,
                    2,
                    ptr::null(),
                    verts as *const c_void,
                );

                cx += glyph_w;
            }
        }
    }

    /// Blit a loaded texture at the given position and size.
    pub fn blit(&mut self, tex: TextureId, x: i32, y: i32, w: u32, h: u32) {
        let idx = tex.0 as usize;
        let Some(Some(texture)) = self.textures.get(idx) else {
            return;
        };
        let tex_w = texture.width as i16;
        let tex_h = texture.height as i16;
        let buf_w = texture.buf_w;
        let buf_h = texture.buf_h;
        let data_ptr = texture.data;

        unsafe {
            // Textures are in RAM -- use uncached address and flush.
            let uncached_ptr = (data_ptr as usize | 0x4000_0000) as *const c_void;
            sys::sceGuTexMode(TexturePixelFormat::Psm8888, 0, 0, 0);
            sys::sceGuTexImage(
                MipmapLevel::None,
                buf_w as i32,
                buf_h as i32,
                buf_w as i32,
                uncached_ptr,
            );
            sys::sceGuTexFunc(TextureEffect::Modulate, TextureColorComponent::Rgba);
            sys::sceGuTexFlush();
            sys::sceGuTexSync();

            let verts = sys::sceGuGetMemory(
                (2 * size_of::<TexturedColorVertex>()) as i32,
            ) as *mut TexturedColorVertex;
            if verts.is_null() {
                return;
            }

            let white = 0xFFFF_FFFFu32;

            ptr::write(
                verts,
                TexturedColorVertex {
                    u: 0,
                    v: 0,
                    color: white,
                    x: x as i16,
                    y: y as i16,
                    z: 0,
                    _pad: 0,
                },
            );
            ptr::write(
                verts.add(1),
                TexturedColorVertex {
                    u: tex_w,
                    v: tex_h,
                    color: white,
                    x: (x + w as i32) as i16,
                    y: (y + h as i32) as i16,
                    z: 0,
                    _pad: 0,
                },
            );

            sys::sceGuDrawArray(
                GuPrimitive::Sprites,
                TEXTURED_COLOR_VTYPE,
                2,
                ptr::null(),
                verts as *const c_void,
            );
        }
    }

    /// Load raw RGBA pixel data as a texture.
    ///
    /// The data is copied into a power-of-2 aligned buffer suitable for the GU.
    pub fn load_texture(&mut self, width: u32, height: u32, rgba_data: &[u8]) -> Option<TextureId> {
        let expected = (width * height * 4) as usize;
        if rgba_data.len() != expected {
            return None;
        }

        let buf_w = width.next_power_of_two();
        let buf_h = height.next_power_of_two();
        let buf_size = (buf_w * buf_h * 4) as usize;
        let layout = Layout::from_size_align(buf_size, 16).ok()?;

        let data = unsafe { alloc(layout) };
        if data.is_null() {
            return None;
        }

        // Zero the buffer first (for padding areas).
        unsafe {
            // Manual zero loop to avoid core::ptr::write_bytes (see MEMORY.md footgun).
            let slice = core::slice::from_raw_parts_mut(data, buf_size);
            for byte in slice.iter_mut() {
                *byte = 0;
            }
        }

        // Copy source rows into the power-of-2 buffer.
        let src_stride = (width * 4) as usize;
        let dst_stride = (buf_w * 4) as usize;
        for row in 0..height as usize {
            unsafe {
                ptr::copy_nonoverlapping(
                    rgba_data.as_ptr().add(row * src_stride),
                    data.add(row * dst_stride),
                    src_stride,
                );
            }
        }

        let texture = Texture {
            width,
            height,
            buf_w,
            buf_h,
            data,
            layout,
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

    /// Destroy a loaded texture, freeing its memory.
    pub fn destroy_texture(&mut self, tex: TextureId) {
        let idx = tex.0 as usize;
        if idx < self.textures.len() {
            if let Some(texture) = self.textures[idx].take() {
                unsafe {
                    dealloc(texture.data, texture.layout);
                }
            }
        }
    }

    /// Set the clipping rectangle via GU scissor.
    pub fn set_clip_rect(&mut self, x: i32, y: i32, w: u32, h: u32) {
        unsafe {
            sys::sceGuScissor(x, y, x + w as i32, y + h as i32);
        }
    }

    /// Reset clipping to full screen.
    pub fn reset_clip_rect(&mut self) {
        unsafe {
            sys::sceGuScissor(0, 0, SCREEN_WIDTH as i32, SCREEN_HEIGHT as i32);
        }
    }

    /// Finalize the current display list, swap buffers, and open the next frame.
    pub fn swap_buffers(&mut self) {
        unsafe {
            sys::sceGuFinish();
            sys::sceGuSync(GuSyncMode::Finish, GuSyncBehavior::Wait);
            sys::sceDisplayWaitVblankStart();
            sys::sceGuSwapBuffers();
            sys::sceGuStart(
                GuContextType::Direct,
                &raw mut DISPLAY_LIST as *mut c_void,
            );
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

    // -- Private helpers ----------------------------------------------------

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

/// Generate a PSIX-style gradient wallpaper as RGBA bytes.
///
/// Produces the characteristic orange-to-green sweep with wave arcs emanating
/// from the lower-left, matching `oasis-core`'s `wallpaper::generate_gradient`.
pub fn generate_gradient(w: u32, h: u32) -> Vec<u8> {
    let mut buf = vec![0u8; (w * h * 4) as usize];

    for y in 0..h {
        for x in 0..w {
            let offset = ((y * w + x) * 4) as usize;

            let nx = x as f32 / w as f32;
            let ny = y as f32 / h as f32;

            // Horizontal sweep: hot orange (left) -> bright lime green (right).
            let t = nx * 0.88 + ny * 0.12;

            let (r, g, b) = if t < 0.15 {
                let s = t / 0.15;
                lerp_rgb((245, 110, 15), (255, 170, 15), s)
            } else if t < 0.32 {
                let s = (t - 0.15) / 0.17;
                lerp_rgb((255, 170, 15), (255, 230, 30), s)
            } else if t < 0.48 {
                let s = (t - 0.32) / 0.16;
                lerp_rgb((255, 230, 30), (230, 245, 40), s)
            } else if t < 0.65 {
                let s = (t - 0.48) / 0.17;
                lerp_rgb((230, 245, 40), (140, 235, 50), s)
            } else {
                let s = (t - 0.65) / 0.35;
                lerp_rgb((140, 235, 50), (200, 252, 130), s)
            };

            // Vertical brightness: lighter toward top, darker at bottom.
            let vert = 1.0 + (0.5 - ny) * 0.18;

            // Wave arcs from lower-left (characteristic PSIX pattern).
            let dx = nx + 0.05;
            let dy = ny - 1.3;
            let dist = sqrt_approx(dx * dx + dy * dy);
            let arc1 = sin_approx(dist * 12.0) * 0.18;
            let arc2 = sin_approx(dist * 22.0 + 1.2) * 0.09;
            let arc3 = sin_approx(dist * 36.0 + nx * 2.5) * 0.04;

            // Arcs fade toward the right.
            let arc_fade = (1.0 - nx * 0.45).clamp(0.0, 1.0);
            let wave = 1.0 + (arc1 + arc2 + arc3) * arc_fade;

            let scale = vert * wave;
            buf[offset] = (r as f32 * scale).clamp(0.0, 255.0) as u8;
            buf[offset + 1] = (g as f32 * scale).clamp(0.0, 255.0) as u8;
            buf[offset + 2] = (b as f32 * scale).clamp(0.0, 255.0) as u8;
            buf[offset + 3] = 255;
        }
    }

    buf
}

/// Linear interpolation between two RGB colors.
fn lerp_rgb(a: (u8, u8, u8), b: (u8, u8, u8), t: f32) -> (u8, u8, u8) {
    let r = a.0 as f32 + (b.0 as f32 - a.0 as f32) * t;
    let g = a.1 as f32 + (b.1 as f32 - a.1 as f32) * t;
    let bv = a.2 as f32 + (b.2 as f32 - a.2 as f32) * t;
    (r as u8, g as u8, bv as u8)
}

/// Taylor-series sine approximation (no libm dependency for `no_std`).
fn sin_approx(mut x: f32) -> f32 {
    const PI: f32 = 3.14159265;
    const TWO_PI: f32 = 6.2831853;
    x = x % TWO_PI;
    if x > PI {
        x -= TWO_PI;
    }
    if x < -PI {
        x += TWO_PI;
    }
    let x2 = x * x;
    x * (1.0 - x2 * (1.0 / 6.0 - x2 * (1.0 / 120.0 - x2 / 5040.0)))
}

/// Newton-Raphson square root approximation (no libm dependency for `no_std`).
fn sqrt_approx(x: f32) -> f32 {
    if x <= 0.0 {
        return 0.0;
    }
    let mut g = x * 0.5;
    g = 0.5 * (g + x / g);
    g = 0.5 * (g + x / g);
    g = 0.5 * (g + x / g);
    0.5 * (g + x / g)
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
