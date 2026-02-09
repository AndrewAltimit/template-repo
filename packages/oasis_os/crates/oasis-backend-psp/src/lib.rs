//! PSP backend for OASIS_OS.
//!
//! Hardware-accelerated rendering via the PSP Graphics Engine (sceGu/sceGum).
//! All rectangles, textures, and text are drawn as GU `Sprites` primitives,
//! offloading work from the 333MHz MIPS CPU to the dedicated GE hardware.
//!
//! Controller input via `sceCtrlPeekBufferPositive` with edge detection for
//! press/release events.
//!
//! Uses `restricted_std` with `RUST_PSP_BUILD_STD=1` for std support on PSP.
//! Types are imported from `oasis-core` directly.

#![feature(restricted_std)]

pub mod font;

use std::alloc::{alloc, dealloc, Layout};
use std::ffi::c_void;
use std::mem::size_of;
use std::ptr;

use psp::sys::{
    self, BlendFactor, BlendOp, ClearBuffer, CtrlButtons, CtrlMode, DisplayPixelFormat,
    GuContextType, GuPrimitive, GuState, GuSyncBehavior, GuSyncMode, MatrixMode, MipmapLevel,
    SceCtrlData, TextureColorComponent, TextureEffect, TextureFilter, TexturePixelFormat,
    VertexType,
};
use psp::vram_alloc::get_vram_allocator;

// ---------------------------------------------------------------------------
// Re-export shared types from oasis-core
// ---------------------------------------------------------------------------

pub use oasis_core::backend::{Color, SdiBackend, TextureId};
pub use oasis_core::error::{OasisError, Result as OasisResult};
pub use oasis_core::input::{Button, InputEvent, Trigger};
pub use oasis_core::sdi::SdiRegistry;
pub use oasis_core::wm::manager::{WindowManager, WmEvent};
pub use oasis_core::wm::window::{WindowConfig, WindowType, WmTheme};

/// PSP-specific extension for Color -> ABGR conversion (used by sceGu).
pub trait ColorExt {
    fn to_abgr(&self) -> u32;
}

impl ColorExt for Color {
    fn to_abgr(&self) -> u32 {
        (self.a as u32) << 24 | (self.b as u32) << 16 | (self.g as u32) << 8 | self.r as u32
    }
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
    /// 16-byte aligned pixel data pointer (RAM or volatile mem).
    data: *mut u8,
    /// Layout used for deallocation (only valid if `in_volatile` is false).
    layout: Layout,
    /// True if data lives in volatile memory (not individually freeable).
    in_volatile: bool,
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

// ---------------------------------------------------------------------------
// Volatile memory bump allocator (PSP-2000+ extra 4MB RAM)
// ---------------------------------------------------------------------------

/// Simple bump allocator over the volatile memory region.
///
/// On PSP-2000 and later, `sceKernelVolatileMemTryLock` provides access to an
/// extra 4MB of RAM. This allocator hands out 16-byte-aligned chunks from that
/// region for texture storage, freeing main heap for application data.
struct VolatileAllocator {
    base: *mut u8,
    size: usize,
    offset: usize,
}

impl VolatileAllocator {
    /// Create a new allocator over the given memory region.
    fn new(base: *mut u8, size: usize) -> Self {
        Self { base, size, offset: 0 }
    }

    /// Allocate `len` bytes with 16-byte alignment. Returns null on OOM.
    fn alloc(&mut self, len: usize) -> *mut u8 {
        let aligned = (self.offset + 15) & !15;
        if aligned + len > self.size {
            return ptr::null_mut();
        }
        let ptr = unsafe { self.base.add(aligned) };
        self.offset = aligned + len;
        ptr
    }

    /// Reset the allocator, freeing all allocations.
    fn reset(&mut self) {
        self.offset = 0;
    }

    /// Bytes remaining.
    fn remaining(&self) -> usize {
        let aligned = (self.offset + 15) & !15;
        self.size.saturating_sub(aligned)
    }
}

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
    /// Volatile memory bump allocator (PSP-2000+ extra 4MB).
    volatile_alloc: Option<VolatileAllocator>,
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
            volatile_alloc: None,
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

            // Claim volatile memory (extra 4MB on PSP-2000+) for texture cache.
            let mut vol_ptr: *mut c_void = ptr::null_mut();
            let mut vol_size: i32 = 0;
            let vol_ret = sys::sceKernelVolatileMemTryLock(
                0,
                &mut vol_ptr as *mut *mut c_void,
                &mut vol_size,
            );
            if vol_ret == 0 && !vol_ptr.is_null() && vol_size > 0 {
                self.volatile_alloc =
                    Some(VolatileAllocator::new(vol_ptr as *mut u8, vol_size as usize));
                psp::dprintln!(
                    "OASIS_OS: Volatile mem claimed: {} KB at {:p}",
                    vol_size / 1024,
                    vol_ptr,
                );
            }

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
    pub fn clear_inner(&mut self, color: Color) {
        unsafe {
            sys::sceGuClearColor(color.to_abgr());
            sys::sceGuClear(ClearBuffer::COLOR_BUFFER_BIT | ClearBuffer::FAST_CLEAR_BIT);
        }
    }

    /// Draw a filled rectangle.
    pub fn fill_rect_inner(&mut self, x: i32, y: i32, w: u32, h: u32, color: Color) {
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
    pub fn draw_text_inner(&mut self, text: &str, x: i32, y: i32, font_size: u16, color: Color) {
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
    pub fn blit_inner(&mut self, tex: TextureId, x: i32, y: i32, w: u32, h: u32) {
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
    /// On PSP-2000+, textures are allocated from the extra 4MB volatile memory
    /// when available, falling back to the main heap.
    pub fn load_texture_inner(&mut self, width: u32, height: u32, rgba_data: &[u8]) -> Option<TextureId> {
        let expected = (width * height * 4) as usize;
        if rgba_data.len() != expected {
            return None;
        }

        let buf_w = width.next_power_of_two();
        let buf_h = height.next_power_of_two();
        let buf_size = (buf_w * buf_h * 4) as usize;

        // Try volatile memory first, fall back to main heap.
        let (data, layout, in_volatile) =
            if let Some(ref mut va) = self.volatile_alloc {
                let p = va.alloc(buf_size);
                if !p.is_null() {
                    (p, Layout::new::<u8>(), true)
                } else {
                    let layout = Layout::from_size_align(buf_size, 16).ok()?;
                    let p = unsafe { alloc(layout) };
                    if p.is_null() {
                        return None;
                    }
                    (p, layout, false)
                }
            } else {
                let layout = Layout::from_size_align(buf_size, 16).ok()?;
                let p = unsafe { alloc(layout) };
                if p.is_null() {
                    return None;
                }
                (p, layout, false)
            };

        // Zero the buffer first (for padding areas).
        unsafe {
            // Manual zero loop to avoid core::ptr::write_bytes (see MEMORY.md footgun).
            let slice = std::slice::from_raw_parts_mut(data, buf_size);
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
            in_volatile,
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
    ///
    /// Textures in volatile memory are not individually freed (the bump
    /// allocator reclaims them all at once on reset).
    pub fn destroy_texture_inner(&mut self, tex: TextureId) {
        let idx = tex.0 as usize;
        if idx < self.textures.len() {
            if let Some(texture) = self.textures[idx].take() {
                if !texture.in_volatile {
                    unsafe {
                        dealloc(texture.data, texture.layout);
                    }
                }
            }
        }
    }

    /// Set the clipping rectangle via GU scissor.
    pub fn set_clip_rect_inner(&mut self, x: i32, y: i32, w: u32, h: u32) {
        unsafe {
            sys::sceGuScissor(x, y, x + w as i32, y + h as i32);
        }
    }

    /// Reset clipping to full screen.
    pub fn reset_clip_rect_inner(&mut self) {
        unsafe {
            sys::sceGuScissor(0, 0, SCREEN_WIDTH as i32, SCREEN_HEIGHT as i32);
        }
    }

    /// Finalize the current display list, swap buffers, and open the next frame.
    pub fn swap_buffers_inner(&mut self) {
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
    pub fn poll_events_inner(&mut self) -> Vec<InputEvent> {
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

    /// Query volatile memory cache status.
    ///
    /// Returns `(total_bytes, remaining_bytes)` if volatile memory was
    /// claimed, or `None` on PSP-1000 / if already locked.
    pub fn volatile_mem_info(&self) -> Option<(usize, usize)> {
        self.volatile_alloc
            .as_ref()
            .map(|va| (va.size, va.remaining()))
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
// SdiBackend trait implementation
// ---------------------------------------------------------------------------

impl SdiBackend for PspBackend {
    fn init(&mut self, _width: u32, _height: u32) -> OasisResult<()> {
        // PSP backend initializes during PspBackend::init().
        Ok(())
    }

    fn clear(&mut self, color: Color) -> OasisResult<()> {
        self.clear_inner(color);
        Ok(())
    }

    fn blit(&mut self, tex: TextureId, x: i32, y: i32, w: u32, h: u32) -> OasisResult<()> {
        self.blit_inner(tex, x, y, w, h);
        Ok(())
    }

    fn fill_rect(&mut self, x: i32, y: i32, w: u32, h: u32, color: Color) -> OasisResult<()> {
        self.fill_rect_inner(x, y, w, h, color);
        Ok(())
    }

    fn draw_text(
        &mut self,
        text: &str,
        x: i32,
        y: i32,
        font_size: u16,
        color: Color,
    ) -> OasisResult<()> {
        self.draw_text_inner(text, x, y, font_size, color);
        Ok(())
    }

    fn swap_buffers(&mut self) -> OasisResult<()> {
        self.swap_buffers_inner();
        Ok(())
    }

    fn load_texture(
        &mut self,
        width: u32,
        height: u32,
        rgba_data: &[u8],
    ) -> OasisResult<TextureId> {
        self.load_texture_inner(width, height, rgba_data)
            .ok_or_else(|| OasisError::Backend("PSP texture allocation failed".into()))
    }

    fn destroy_texture(&mut self, tex: TextureId) -> OasisResult<()> {
        self.destroy_texture_inner(tex);
        Ok(())
    }

    fn set_clip_rect(&mut self, x: i32, y: i32, w: u32, h: u32) -> OasisResult<()> {
        self.set_clip_rect_inner(x, y, w, h);
        Ok(())
    }

    fn reset_clip_rect(&mut self) -> OasisResult<()> {
        self.reset_clip_rect_inner();
        Ok(())
    }

    fn read_pixels(&self, _x: i32, _y: i32, _w: u32, _h: u32) -> OasisResult<Vec<u8>> {
        Err(OasisError::Backend(
            "read_pixels not supported on PSP".into(),
        ))
    }

    fn shutdown(&mut self) -> OasisResult<()> {
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// InputBackend trait implementation
// ---------------------------------------------------------------------------

impl oasis_core::backend::InputBackend for PspBackend {
    fn poll_events(&mut self) -> Vec<InputEvent> {
        self.poll_events_inner()
    }
}

// ---------------------------------------------------------------------------
// PSP-tuned WM theme (compact for 480x272 screen)
// ---------------------------------------------------------------------------

/// Create a compact WmTheme tuned for the PSP's 480x272 display.
pub fn psp_wm_theme() -> WmTheme {
    WmTheme {
        titlebar_height: 14,
        border_width: 1,
        titlebar_active_color: Color::rgba(40, 70, 130, 230),
        titlebar_inactive_color: Color::rgba(60, 60, 60, 200),
        titlebar_text_color: Color::WHITE,
        frame_color: Color::rgba(30, 30, 30, 200),
        content_bg_color: Color::rgba(20, 20, 30, 220),
        btn_close_color: Color::rgb(180, 50, 50),
        btn_minimize_color: Color::rgb(180, 160, 50),
        btn_maximize_color: Color::rgb(50, 160, 50),
        button_size: 10,
        resize_handle_size: 4,
        titlebar_font_size: 8,
    }
}

// ---------------------------------------------------------------------------
// Background audio thread (std::thread + mpsc)
// ---------------------------------------------------------------------------

use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::mpsc;
use std::sync::Arc;

/// Shared audio state readable from the main thread.
pub struct AudioState {
    pub playing: AtomicBool,
    pub paused: AtomicBool,
    pub sample_rate: AtomicU32,
    pub bitrate: AtomicU32,
    pub channels: AtomicU32,
}

impl Default for AudioState {
    fn default() -> Self {
        Self {
            playing: AtomicBool::new(false),
            paused: AtomicBool::new(false),
            sample_rate: AtomicU32::new(0),
            bitrate: AtomicU32::new(0),
            channels: AtomicU32::new(0),
        }
    }
}

/// Handle to the background audio state (readable from main thread).
pub struct AudioHandle {
    pub tx: mpsc::Sender<WorkerCmd>,
    pub state: Arc<AudioState>,
}

impl AudioHandle {
    pub fn is_playing(&self) -> bool {
        self.state.playing.load(Ordering::Relaxed)
    }

    pub fn is_paused(&self) -> bool {
        self.state.paused.load(Ordering::Relaxed)
    }

    pub fn sample_rate(&self) -> u32 {
        self.state.sample_rate.load(Ordering::Relaxed)
    }

    pub fn bitrate(&self) -> u32 {
        self.state.bitrate.load(Ordering::Relaxed)
    }

    pub fn channels(&self) -> u32 {
        self.state.channels.load(Ordering::Relaxed)
    }
}

// ---------------------------------------------------------------------------
// Unified background worker thread (audio + file I/O)
//
// PSP's std::thread has a TLS limitation that prevents spawning multiple
// threads. We combine audio playback and file I/O into a single worker
// thread with a unified command channel.
// ---------------------------------------------------------------------------

/// Requests sent to the I/O side of the worker thread.
pub enum IoRequest {
    /// Load and decode a JPEG into RGBA pixels.
    LoadTexture {
        path: String,
        max_w: i32,
        max_h: i32,
    },
    /// Read a file into a byte buffer.
    ReadFile { path: String },
}

/// Responses from the I/O side of the worker thread.
pub enum IoResponse {
    /// A texture was decoded successfully.
    TextureReady {
        path: String,
        width: u32,
        height: u32,
        rgba: Vec<u8>,
    },
    /// A file was read successfully.
    FileReady { path: String, data: Vec<u8> },
    /// An I/O operation failed.
    Error { path: String, msg: String },
}

/// Handle to the I/O response channel.
pub struct IoHandle {
    pub tx: mpsc::Sender<WorkerCmd>,
    pub rx: mpsc::Receiver<IoResponse>,
}

/// Unified commands for the single background worker thread.
pub enum WorkerCmd {
    // Audio commands.
    AudioLoadAndPlay(String),
    AudioPause,
    AudioResume,
    AudioStop,
    // I/O commands.
    Io(IoRequest),
    /// Shut down the worker thread.
    Shutdown,
}

/// Spawn the single background worker thread.
///
/// Returns handles for audio state and I/O responses. Both share the same
/// command sender (cloned).
pub fn spawn_worker() -> (AudioHandle, IoHandle) {
    let (cmd_tx, cmd_rx) = mpsc::channel::<WorkerCmd>();
    let (io_resp_tx, io_resp_rx) = mpsc::channel::<IoResponse>();
    let audio_state = Arc::new(AudioState::default());
    let state_clone = audio_state.clone();

    std::thread::spawn(move || worker_thread_fn(cmd_rx, io_resp_tx, state_clone));

    let audio = AudioHandle {
        tx: cmd_tx.clone(),
        state: audio_state,
    };
    let io = IoHandle {
        tx: cmd_tx,
        rx: io_resp_rx,
    };
    (audio, io)
}

/// Unified worker thread main loop (audio + I/O).
fn worker_thread_fn(
    rx: mpsc::Receiver<WorkerCmd>,
    io_tx: mpsc::Sender<IoResponse>,
    audio_state: Arc<AudioState>,
) {
    let mut player = AudioPlayer::new();
    if !player.init() {
        psp::dprintln!("OASIS_OS: Worker thread audio init failed");
    }

    loop {
        // Non-blocking check for commands.
        match rx.try_recv() {
            Ok(WorkerCmd::AudioLoadAndPlay(path)) => {
                if player.load_and_play(&path) {
                    audio_state.playing.store(true, Ordering::Relaxed);
                    audio_state.paused.store(false, Ordering::Relaxed);
                    audio_state.sample_rate.store(player.sample_rate as u32, Ordering::Relaxed);
                    audio_state.bitrate.store(player.bitrate as u32, Ordering::Relaxed);
                    audio_state.channels.store(player.channels as u32, Ordering::Relaxed);
                } else {
                    audio_state.playing.store(false, Ordering::Relaxed);
                }
            }
            Ok(WorkerCmd::AudioPause) => {
                if player.is_playing() && !player.is_paused() {
                    player.toggle_pause();
                    audio_state.paused.store(true, Ordering::Relaxed);
                }
            }
            Ok(WorkerCmd::AudioResume) => {
                if player.is_playing() && player.is_paused() {
                    player.toggle_pause();
                    audio_state.paused.store(false, Ordering::Relaxed);
                }
            }
            Ok(WorkerCmd::AudioStop) => {
                player.stop();
                audio_state.playing.store(false, Ordering::Relaxed);
                audio_state.paused.store(false, Ordering::Relaxed);
            }
            Ok(WorkerCmd::Io(request)) => {
                handle_io_request(request, &io_tx);
            }
            Ok(WorkerCmd::Shutdown) => {
                player.stop();
                audio_state.playing.store(false, Ordering::Relaxed);
                break;
            }
            Err(mpsc::TryRecvError::Empty) => {}
            Err(mpsc::TryRecvError::Disconnected) => break,
        }

        if player.is_playing() && !player.is_paused() {
            // update() contains the blocking sceAudioOutputBlocking call.
            player.update();
            // Check if playback ended naturally.
            if !player.is_playing() {
                audio_state.playing.store(false, Ordering::Relaxed);
            }
        } else {
            // Sleep when idle to avoid spinning.
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
    }
}

/// Process a single I/O request (called from worker thread).
fn handle_io_request(request: IoRequest, tx: &mpsc::Sender<IoResponse>) {
    match request {
        IoRequest::LoadTexture { path, max_w, max_h } => match read_file(&path) {
            Some(data) => match decode_jpeg(&data, max_w, max_h) {
                Some((w, h, rgba)) => {
                    let _ = tx.send(IoResponse::TextureReady {
                        path,
                        width: w,
                        height: h,
                        rgba,
                    });
                }
                None => {
                    let _ = tx.send(IoResponse::Error {
                        path,
                        msg: "JPEG decode failed".into(),
                    });
                }
            },
            None => {
                let _ = tx.send(IoResponse::Error {
                    path,
                    msg: "file read failed".into(),
                });
            }
        },
        IoRequest::ReadFile { path } => match read_file(&path) {
            Some(data) => {
                let _ = tx.send(IoResponse::FileReady { path, data });
            }
            None => {
                let _ = tx.send(IoResponse::Error {
                    path,
                    msg: "file not found".into(),
                });
            }
        },
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

/// Taylor-series sine approximation (no libm dependency).
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

/// Newton-Raphson square root approximation (no libm dependency).
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
// System info (kernel mode queries)
// ---------------------------------------------------------------------------

/// Runtime hardware info queried from PSP firmware.
pub struct SystemInfo {
    /// CPU clock frequency in MHz.
    pub cpu_mhz: i32,
    /// Bus clock frequency in MHz.
    pub bus_mhz: i32,
    /// Media Engine clock frequency in MHz (kernel mode only).
    pub me_mhz: i32,
    /// Whether extra 4MB volatile RAM was claimed (PSP-2000+).
    pub volatile_mem_available: bool,
    /// Size of extra volatile memory in bytes (0 if unavailable).
    pub volatile_mem_size: i32,
}

impl SystemInfo {
    /// Query system info from PSP hardware.
    ///
    /// CPU and bus frequencies are available in user mode. ME frequency
    /// requires kernel mode (enabled via the `kernel` feature flag).
    ///
    /// Volatile memory status is reported by `PspBackend` (which claims it
    /// during `init()` for the texture cache).
    pub fn query() -> Self {
        unsafe {
            let cpu_mhz = sys::scePowerGetCpuClockFrequency();
            let bus_mhz = sys::scePowerGetBusClockFrequency();
            let me_mhz = sys::scePowerGetMeClockFrequency();

            Self {
                cpu_mhz,
                bus_mhz,
                me_mhz,
                volatile_mem_available: false,
                volatile_mem_size: 0,
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Live status polling (battery, clock, USB, WiFi)
// ---------------------------------------------------------------------------

/// Dynamic status info polled each frame (or periodically).
pub struct StatusBarInfo {
    /// Battery charge percentage (0-100), or -1 if no battery.
    pub battery_percent: i32,
    /// Whether the battery is currently charging.
    pub battery_charging: bool,
    /// Whether AC power is connected.
    pub ac_power: bool,
    /// Current hour (0-23).
    pub hour: u16,
    /// Current minute (0-59).
    pub minute: u16,
    /// Whether a USB cable is connected.
    pub usb_connected: bool,
    /// Whether the WiFi switch is on.
    pub wifi_on: bool,
}

impl StatusBarInfo {
    /// Poll live status from PSP hardware.
    pub fn poll() -> Self {
        unsafe {
            let battery_exist = sys::scePowerIsBatteryExist() > 0;
            let battery_percent = if battery_exist {
                sys::scePowerGetBatteryLifePercent()
            } else {
                -1
            };
            let battery_charging = sys::scePowerIsBatteryCharging() > 0;
            let ac_power = sys::scePowerIsPowerOnline() > 0;

            let mut time = sys::ScePspDateTime {
                year: 0,
                month: 0,
                day: 0,
                hour: 0,
                minutes: 0,
                seconds: 0,
                microseconds: 0,
            };
            sys::sceRtcGetCurrentClockLocalTime(&mut time);

            let usb_state = sys::sceUsbGetState();
            let usb_connected = usb_state.contains(sys::UsbState::CONNECTED);

            let wifi_on = sys::sceWlanGetSwitchState() > 0;

            Self {
                battery_percent,
                battery_charging,
                ac_power,
                hour: time.hour,
                minute: time.minutes,
                usb_connected,
                wifi_on,
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Exception handler (kernel mode)
// ---------------------------------------------------------------------------

/// Register a default exception handler that prints the exception type
/// via debug output. Prevents silent crashes on real hardware.
pub fn register_exception_handler() {
    unsafe {
        sys::sceKernelRegisterDefaultExceptionHandler(exception_handler);
    }
}

/// Exception handler callback -- prints exception info and halts.
unsafe extern "C" fn exception_handler(exception: u32, _context: *mut c_void) -> i32 {
    let name = match exception {
        0 => "Interrupt",
        1 => "TLB Modification",
        2 => "TLB Load Miss",
        3 => "TLB Store Miss",
        4 => "Address Error (Load)",
        5 => "Address Error (Store)",
        6 => "Bus Error (Insn)",
        7 => "Bus Error (Data)",
        8 => "Syscall",
        9 => "Breakpoint",
        10 => "Reserved Instruction",
        11 => "Coprocessor Unusable",
        12 => "Overflow",
        _ => "Unknown",
    };
    psp::dprintln!("OASIS_OS EXCEPTION: {} (code {})", name, exception);
    // Spin forever -- the debug output is visible in PPSSPP console
    // and on real hardware via psplink. Returning -1 passes to next handler.
    -1
}

// ---------------------------------------------------------------------------
// Clock frequency control
// ---------------------------------------------------------------------------

/// Set CPU, PLL, and bus clock frequencies.
///
/// Common presets:
/// - `set_clock(333, 333, 166)` -- maximum performance
/// - `set_clock(266, 266, 133)` -- balanced
/// - `set_clock(222, 222, 111)` -- power saving (default)
///
/// Returns 0 on success, < 0 on error.
pub fn set_clock(pll: i32, cpu: i32, bus: i32) -> i32 {
    unsafe { sys::scePowerSetClockFrequency(pll, cpu, bus) }
}

// ---------------------------------------------------------------------------
// File system browsing (sceIo*)
// ---------------------------------------------------------------------------

/// A single entry from a directory listing.
pub struct FileEntry {
    /// File or directory name (ASCII, up to 255 chars).
    pub name: String,
    /// File size in bytes (0 for directories).
    pub size: i64,
    /// True if this entry is a directory.
    pub is_dir: bool,
}

/// List the contents of a directory path (e.g. `"ms0:/"`, `"ms0:/PSP/GAME"`).
///
/// Returns a sorted list of entries (directories first, then files,
/// alphabetically within each group). Returns an empty vec on error.
pub fn list_directory(path: &str) -> Vec<FileEntry> {
    let mut entries = Vec::new();

    // Build null-terminated path.
    let mut path_buf = Vec::with_capacity(path.len() + 1);
    path_buf.extend_from_slice(path.as_bytes());
    path_buf.push(0);

    unsafe {
        let dfd = sys::sceIoDopen(path_buf.as_ptr());
        if dfd.0 < 0 {
            return entries;
        }

        let mut dirent: sys::SceIoDirent = std::mem::zeroed();
        loop {
            let ret = sys::sceIoDread(dfd, &mut dirent);
            if ret <= 0 {
                break;
            }

            // Extract name (null-terminated UTF-8 in d_name).
            let name_bytes = &dirent.d_name;
            let len = name_bytes.iter().position(|&b| b == 0).unwrap_or(name_bytes.len());
            let name = std::str::from_utf8(&name_bytes[..len])
                .unwrap_or("???")
                .to_string();

            // Skip . and ..
            if name == "." || name == ".." {
                continue;
            }

            let is_dir = dirent.d_stat.st_attr.contains(sys::IoStatAttr::IFDIR)
                || dirent.d_stat.st_mode.contains(sys::IoStatMode::IFDIR);
            let size = if is_dir { 0 } else { dirent.d_stat.st_size };

            entries.push(FileEntry { name, size, is_dir });
        }

        sys::sceIoDclose(dfd);
    }

    // Sort: directories first, then alphabetically.
    entries.sort_by(|a, b| {
        b.is_dir
            .cmp(&a.is_dir)
            .then_with(|| a.name.cmp(&b.name))
    });

    entries
}

/// Format a file size as a human-readable string.
pub fn format_size(bytes: i64) -> String {
    if bytes < 1024 {
        format!("{} B", bytes)
    } else if bytes < 1024 * 1024 {
        format!("{} KB", bytes / 1024)
    } else {
        format!("{}.{} MB", bytes / (1024 * 1024), (bytes / 102400) % 10)
    }
}

// ---------------------------------------------------------------------------
// File reading helper
// ---------------------------------------------------------------------------

/// Read an entire file into a byte vector.
///
/// Returns `None` if the file cannot be opened or read.
pub fn read_file(path: &str) -> Option<Vec<u8>> {
    let mut path_buf = Vec::with_capacity(path.len() + 1);
    path_buf.extend_from_slice(path.as_bytes());
    path_buf.push(0);

    unsafe {
        // Get file size first via stat.
        let mut stat: sys::SceIoStat = std::mem::zeroed();
        if sys::sceIoGetstat(path_buf.as_ptr(), &mut stat) < 0 {
            return None;
        }
        let size = stat.st_size as usize;
        if size == 0 {
            return Some(Vec::new());
        }

        let fd = sys::sceIoOpen(path_buf.as_ptr(), sys::IoOpenFlags::RD_ONLY, 0);
        if fd.0 < 0 {
            return None;
        }

        let mut data = vec![0u8; size];
        let mut total_read = 0usize;
        while total_read < size {
            let chunk = (size - total_read).min(65536) as u32;
            let n = sys::sceIoRead(
                fd,
                data.as_mut_ptr().add(total_read) as *mut c_void,
                chunk,
            );
            if n <= 0 {
                break;
            }
            total_read += n as usize;
        }
        sys::sceIoClose(fd);

        if total_read == size {
            Some(data)
        } else {
            None
        }
    }
}

// ---------------------------------------------------------------------------
// Hardware JPEG decoding (sceJpeg)
// ---------------------------------------------------------------------------

/// Decode a JPEG image using the PSP's hardware MJPEG decoder.
///
/// Returns `(width, height, rgba_pixels)` on success. The output is RGBA8888.
/// `max_w` and `max_h` set the maximum decode dimensions (use 480, 272 for
/// screen-sized images).
pub fn decode_jpeg(jpeg_data: &[u8], max_w: i32, max_h: i32) -> Option<(u32, u32, Vec<u8>)> {
    unsafe {
        if sys::sceJpegInitMJpeg() < 0 {
            return None;
        }
        if sys::sceJpegCreateMJpeg(max_w, max_h) < 0 {
            sys::sceJpegFinishMJpeg();
            return None;
        }

        // Output buffer: max_w * max_h * 4, 64-byte aligned.
        let out_size = (max_w as usize) * (max_h as usize) * 4;
        let out_layout = Layout::from_size_align(out_size, 64).ok()?;
        let out_buf = alloc(out_layout);
        if out_buf.is_null() {
            sys::sceJpegDeleteMJpeg();
            sys::sceJpegFinishMJpeg();
            return None;
        }

        // sceJpegDecodeMJpeg needs a mutable pointer to the JPEG data.
        let mut jpeg_copy = Vec::from(jpeg_data);

        let ret = sys::sceJpegDecodeMJpeg(
            jpeg_copy.as_mut_ptr(),
            jpeg_copy.len(),
            out_buf as *mut c_void,
            0,
        );

        sys::sceJpegDeleteMJpeg();
        sys::sceJpegFinishMJpeg();

        if ret < 0 {
            dealloc(out_buf, out_layout);
            return None;
        }

        // Return value encodes dimensions: (width << 16) | height.
        let width = ((ret >> 16) & 0xFFFF) as u32;
        let height = (ret & 0xFFFF) as u32;
        let pixel_count = (width * height * 4) as usize;

        let mut rgba = vec![0u8; pixel_count];
        // Manual copy (see MEMORY.md footgun re: ptr intrinsics).
        let src = std::slice::from_raw_parts(out_buf, pixel_count);
        rgba.copy_from_slice(src);

        dealloc(out_buf, out_layout);
        Some((width, height, rgba))
    }
}

// ---------------------------------------------------------------------------
// Audio player (MP3 via sceMp3 + sceAudio)
// ---------------------------------------------------------------------------

/// MP3 playback engine using the PSP's hardware MP3 decoder.
///
/// Call `init()` once, `load_mp3()` to load a file, then `update()` each
/// frame to pump decoded audio to the hardware output channel.
pub struct AudioPlayer {
    /// Audio channel reserved for playback (-1 if none).
    channel: i32,
    /// MP3 decoder handle.
    mp3_handle: i32,
    /// MP3 stream buffer (>= 8192 bytes, 64-byte aligned).
    mp3_buf: *mut u8,
    mp3_buf_layout: Layout,
    /// PCM output buffer (>= 9216 bytes, 64-byte aligned).
    pcm_buf: *mut u8,
    pcm_buf_layout: Layout,
    /// The entire MP3 file loaded into RAM.
    file_data: Vec<u8>,
    /// Current read position in file_data for streaming.
    file_pos: usize,
    /// Whether the decoder is initialized and playing.
    playing: bool,
    paused: bool,
    /// Cached MP3 info.
    pub sample_rate: i32,
    pub bitrate: i32,
    pub channels: i32,
}

const MP3_BUF_SIZE: usize = 16384; // 16 KB stream buffer
const PCM_BUF_SIZE: usize = 9216; // minimum for sceMp3

impl AudioPlayer {
    pub fn new() -> Self {
        Self {
            channel: -1,
            mp3_handle: -1,
            mp3_buf: ptr::null_mut(),
            mp3_buf_layout: Layout::new::<u8>(),
            pcm_buf: ptr::null_mut(),
            pcm_buf_layout: Layout::new::<u8>(),
            file_data: Vec::new(),
            file_pos: 0,
            playing: false,
            paused: false,
            sample_rate: 0,
            bitrate: 0,
            channels: 0,
        }
    }

    /// Initialize the MP3 subsystem and allocate buffers.
    pub fn init(&mut self) -> bool {
        unsafe {
            if sys::sceMp3InitResource() < 0 {
                return false;
            }
        }

        let mp3_layout = Layout::from_size_align(MP3_BUF_SIZE, 64).unwrap();
        let pcm_layout = Layout::from_size_align(PCM_BUF_SIZE, 64).unwrap();
        let mp3_buf = unsafe { alloc(mp3_layout) };
        let pcm_buf = unsafe { alloc(pcm_layout) };
        if mp3_buf.is_null() || pcm_buf.is_null() {
            return false;
        }

        self.mp3_buf = mp3_buf;
        self.mp3_buf_layout = mp3_layout;
        self.pcm_buf = pcm_buf;
        self.pcm_buf_layout = pcm_layout;
        true
    }

    /// Load an MP3 file from a path on the Memory Stick and start playback.
    pub fn load_and_play(&mut self, path: &str) -> bool {
        // Stop any current playback.
        self.stop();

        // Read entire file into RAM.
        let data = match read_file(path) {
            Some(d) => d,
            None => return false,
        };
        if data.is_empty() {
            return false;
        }

        self.file_data = data;
        self.file_pos = 0;

        unsafe {
            // Set up MP3 init args.
            let mut init_arg = sys::SceMp3InitArg {
                mp3_stream_start: 0,
                unk1: 0,
                mp3_stream_end: self.file_data.len() as u32,
                unk2: 0,
                mp3_buf: self.mp3_buf as *mut c_void,
                mp3_buf_size: MP3_BUF_SIZE as i32,
                pcm_buf: self.pcm_buf as *mut c_void,
                pcm_buf_size: PCM_BUF_SIZE as i32,
            };

            let handle = sys::sceMp3ReserveMp3Handle(&mut init_arg);
            if handle < 0 {
                return false;
            }
            self.mp3_handle = handle;
            let mp3h = sys::Mp3Handle(handle);

            // Feed initial data.
            if !self.feed_data() {
                sys::sceMp3ReleaseMp3Handle(mp3h);
                self.mp3_handle = -1;
                return false;
            }

            // Initialize decoder (parses headers).
            if sys::sceMp3Init(mp3h) < 0 {
                sys::sceMp3ReleaseMp3Handle(mp3h);
                self.mp3_handle = -1;
                return false;
            }

            // Query format info.
            self.sample_rate = sys::sceMp3GetSamplingRate(mp3h);
            self.bitrate = sys::sceMp3GetBitRate(mp3h);
            self.channels = sys::sceMp3GetMp3ChannelNum(mp3h);

            // Get max samples per decode.
            let max_samples = sys::sceMp3GetMaxOutputSample(mp3h);
            if max_samples <= 0 {
                sys::sceMp3ReleaseMp3Handle(mp3h);
                self.mp3_handle = -1;
                return false;
            }

            // Reserve audio channel.
            let fmt = if self.channels == 1 {
                sys::AudioFormat::Mono
            } else {
                sys::AudioFormat::Stereo
            };
            let ch = sys::sceAudioChReserve(-1, max_samples, fmt);
            if ch < 0 {
                sys::sceMp3ReleaseMp3Handle(mp3h);
                self.mp3_handle = -1;
                return false;
            }
            self.channel = ch;

            // Set up sample rate conversion if needed (PSP audio is 44.1kHz native).
            // sceAudioSRCChReserve handles resampling for non-44100 rates, but
            // the channel-based API works fine for most MP3s.

            self.playing = true;
            self.paused = false;
        }

        psp::dprintln!(
            "OASIS_OS: MP3 loaded - {}Hz, {}kbps, {}ch",
            self.sample_rate,
            self.bitrate,
            self.channels,
        );
        true
    }

    /// Pump decoded audio to the output channel. Call each frame.
    pub fn update(&mut self) {
        if !self.playing || self.paused || self.mp3_handle < 0 {
            return;
        }

        unsafe {
            let mp3h = sys::Mp3Handle(self.mp3_handle);

            // Feed more MP3 data if the decoder needs it.
            if sys::sceMp3CheckStreamDataNeeded(mp3h) > 0 {
                self.feed_data();
            }

            // Decode one frame.
            let mut dst: *mut i16 = ptr::null_mut();
            let decoded = sys::sceMp3Decode(mp3h, &mut dst);
            if decoded > 0 && !dst.is_null() {
                // Output decoded PCM. Blocking ensures proper pacing.
                sys::sceAudioOutputBlocking(
                    self.channel,
                    sys::AUDIO_VOLUME_MAX as i32,
                    dst as *mut c_void,
                );
            } else {
                // End of stream or error.
                self.playing = false;
            }
        }
    }

    /// Stop playback and release resources.
    pub fn stop(&mut self) {
        if self.mp3_handle >= 0 {
            unsafe {
                sys::sceMp3ReleaseMp3Handle(sys::Mp3Handle(self.mp3_handle));
            }
            self.mp3_handle = -1;
        }
        if self.channel >= 0 {
            unsafe {
                sys::sceAudioChRelease(self.channel);
            }
            self.channel = -1;
        }
        self.playing = false;
        self.paused = false;
        self.file_data = Vec::new();
        self.file_pos = 0;
    }

    /// Toggle pause/resume.
    pub fn toggle_pause(&mut self) {
        self.paused = !self.paused;
    }

    pub fn is_playing(&self) -> bool {
        self.playing
    }

    pub fn is_paused(&self) -> bool {
        self.paused
    }

    /// Feed MP3 data from the file buffer into the decoder's stream buffer.
    fn feed_data(&mut self) -> bool {
        unsafe {
            let mp3h = sys::Mp3Handle(self.mp3_handle);
            let mut write_ptr: *mut u8 = ptr::null_mut();
            let mut to_write: i32 = 0;
            let mut src_pos: i32 = 0;

            if sys::sceMp3GetInfoToAddStreamData(
                mp3h,
                &mut write_ptr,
                &mut to_write,
                &mut src_pos,
            ) < 0
            {
                return false;
            }

            if to_write <= 0 || write_ptr.is_null() {
                return true; // nothing to feed right now
            }

            let remaining = self.file_data.len() - self.file_pos;
            let copy_len = (to_write as usize).min(remaining);
            if copy_len == 0 {
                // Signal end of stream by notifying with 0.
                sys::sceMp3NotifyAddStreamData(mp3h, 0);
                return true;
            }

            ptr::copy_nonoverlapping(
                self.file_data.as_ptr().add(self.file_pos),
                write_ptr,
                copy_len,
            );
            self.file_pos += copy_len;

            sys::sceMp3NotifyAddStreamData(mp3h, copy_len as i32);
        }
        true
    }
}

impl Drop for AudioPlayer {
    fn drop(&mut self) {
        self.stop();
        if !self.mp3_buf.is_null() {
            unsafe { dealloc(self.mp3_buf, self.mp3_buf_layout) };
        }
        if !self.pcm_buf.is_null() {
            unsafe { dealloc(self.pcm_buf, self.pcm_buf_layout) };
        }
        unsafe {
            sys::sceMp3TermResource();
        }
    }
}

// ---------------------------------------------------------------------------
// Power callbacks (sleep/wake)
// ---------------------------------------------------------------------------

/// Flags indicating power events. Matches `sys::PowerInfo` bits.
static mut POWER_RESUMED: bool = false;

/// Register a power callback for suspend/resume notification.
///
/// On suspend, the PSP saves state automatically. On resume, the callback
/// sets a flag that can be polled from the main loop to re-init state.
pub fn register_power_callback() {
    unsafe {
        let cbid = sys::sceKernelCreateCallback(
            b"OasisPowerCB\0".as_ptr(),
            power_callback,
            ptr::null_mut(),
        );
        if cbid.0 >= 0 {
            sys::scePowerRegisterCallback(-1, cbid);
        }
    }
}

/// Check and clear the "resumed from sleep" flag.
pub fn check_power_resumed() -> bool {
    unsafe {
        let r = POWER_RESUMED;
        POWER_RESUMED = false;
        r
    }
}

/// Prevent the PSP from auto-suspending due to idle timeout.
/// Call once per frame during active use.
pub fn power_tick() {
    unsafe {
        sys::scePowerTick(sys::PowerTick::All);
    }
}

unsafe extern "C" fn power_callback(_arg1: i32, power_info: i32, _arg: *mut c_void) -> i32 {
    let info = sys::PowerInfo::from_bits_truncate(power_info as u32);
    if info.contains(sys::PowerInfo::RESUME_COMPLETE) {
        psp::dprintln!("OASIS_OS: Resumed from sleep");
        unsafe { POWER_RESUMED = true };
    }
    if info.contains(sys::PowerInfo::SUSPENDING) {
        psp::dprintln!("OASIS_OS: Entering suspend");
    }
    0
}

// ---------------------------------------------------------------------------
// Status bar helpers
// ---------------------------------------------------------------------------

/// Draw a PSIX-style status bar at the top of the screen.
pub fn draw_status_bar(backend: &mut PspBackend, version: &str) {
    let bar_color = Color::rgba(30, 80, 30, 200);
    backend.fill_rect_inner(0, 0, SCREEN_WIDTH, 18, bar_color);
    backend.draw_text_inner(version, 4, 4, 8, Color::WHITE);
}

/// Draw a PSIX-style bottom bar with navigation hints.
pub fn draw_bottom_bar(backend: &mut PspBackend, hint: &str) {
    let bar_y = (SCREEN_HEIGHT - 18) as i32;
    let bar_color = Color::rgba(30, 80, 30, 200);
    backend.fill_rect_inner(0, bar_y, SCREEN_WIDTH, 18, bar_color);
    backend.draw_text_inner(hint, 4, bar_y + 4, 8, Color::WHITE);
}
