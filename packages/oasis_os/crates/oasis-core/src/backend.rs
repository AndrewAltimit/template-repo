//! Backend trait definitions.
//!
//! Every platform implements these traits. The core framework dispatches all
//! I/O through trait boundaries -- it never calls platform-specific APIs.

use crate::error::Result;
use crate::input::InputEvent;

/// A color in RGBA format (0-255 per channel).
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

/// Opaque handle to a loaded texture in the backend.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct TextureId(pub u64);

/// Rendering backend trait.
///
/// Four implementations cover all deployment targets: GU (PSP), SDL2
/// (desktop/Pi), framebuffer (headless Pi), and UE5 render target.
pub trait SdiBackend {
    /// Initialize the rendering subsystem.
    fn init(&mut self, width: u32, height: u32) -> Result<()>;

    /// Clear the screen to a solid color.
    fn clear(&mut self, color: Color) -> Result<()>;

    /// Blit a texture at the given position and size.
    fn blit(&mut self, tex: TextureId, x: i32, y: i32, w: u32, h: u32) -> Result<()>;

    /// Draw a filled rectangle (used when no texture is assigned).
    fn fill_rect(&mut self, x: i32, y: i32, w: u32, h: u32, color: Color) -> Result<()>;

    /// Draw text at the given position. The backend chooses its available font.
    /// `font_size` is a hint in pixels; backends may approximate.
    fn draw_text(&mut self, text: &str, x: i32, y: i32, font_size: u16, color: Color)
    -> Result<()>;

    /// Present the current frame to the display.
    fn swap_buffers(&mut self) -> Result<()>;

    /// Load raw RGBA pixel data as a texture. Returns a handle for later blit.
    fn load_texture(&mut self, width: u32, height: u32, rgba_data: &[u8]) -> Result<TextureId>;

    /// Destroy a previously loaded texture.
    fn destroy_texture(&mut self, tex: TextureId) -> Result<()>;

    /// Set the clipping rectangle (for window manager content clipping).
    fn set_clip_rect(&mut self, x: i32, y: i32, w: u32, h: u32) -> Result<()>;

    /// Reset clipping to the full screen.
    fn reset_clip_rect(&mut self) -> Result<()>;

    /// Read the current framebuffer as RGBA pixel data.
    /// Returns (width, height, rgba_bytes).
    fn read_pixels(&self, x: i32, y: i32, w: u32, h: u32) -> Result<Vec<u8>>;

    /// Shut down the rendering subsystem and release resources.
    fn shutdown(&mut self) -> Result<()>;
}

/// Input backend trait.
///
/// Maps platform-specific input to the platform-agnostic `InputEvent` enum.
pub trait InputBackend {
    /// Poll for pending input events.
    fn poll_events(&mut self) -> Vec<InputEvent>;
}

/// Network backend trait.
///
/// Abstracts TCP operations across sceNetInet (PSP) and std::net (Linux).
pub trait NetworkBackend {
    /// Start listening for incoming connections on the given port.
    fn listen(&mut self, port: u16) -> Result<()>;

    /// Accept a pending connection. Returns `None` if no connection waiting.
    fn accept(&mut self) -> Result<Option<Box<dyn NetworkStream>>>;

    /// Open an outbound TCP connection.
    fn connect(&mut self, address: &str, port: u16) -> Result<Box<dyn NetworkStream>>;
}

/// A bidirectional byte stream (TCP connection).
pub trait NetworkStream: Send {
    fn read(&mut self, buf: &mut [u8]) -> Result<usize>;
    fn write(&mut self, data: &[u8]) -> Result<usize>;
    fn close(&mut self) -> Result<()>;
}

/// Opaque handle to a loaded audio track in the backend.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct AudioTrackId(pub u64);

/// Audio playback backend trait.
///
/// Two implementations cover all deployment targets: rodio/SDL2_mixer (desktop/Pi)
/// and Media Engine offloading (PSP via PRX stubs).
pub trait AudioBackend {
    /// Initialize the audio subsystem (open device, set sample rate).
    fn init(&mut self) -> Result<()>;

    /// Load an audio file from raw bytes (MP3, WAV, OGG).
    /// Returns a handle for playback control.
    fn load_track(&mut self, data: &[u8]) -> Result<AudioTrackId>;

    /// Start playing a loaded track from the beginning.
    fn play(&mut self, track: AudioTrackId) -> Result<()>;

    /// Pause the currently playing track.
    fn pause(&mut self) -> Result<()>;

    /// Resume a paused track.
    fn resume(&mut self) -> Result<()>;

    /// Stop playback and reset position to the beginning.
    fn stop(&mut self) -> Result<()>;

    /// Set volume (0 = silent, 100 = full).
    fn set_volume(&mut self, volume: u8) -> Result<()>;

    /// Get the current volume (0-100).
    fn get_volume(&self) -> u8;

    /// Return `true` if audio is currently playing.
    fn is_playing(&self) -> bool;

    /// Get the current playback position in milliseconds.
    fn position_ms(&self) -> u64;

    /// Get the total duration of the current track in milliseconds.
    /// Returns 0 if no track is loaded.
    fn duration_ms(&self) -> u64;

    /// Unload a previously loaded track and free its resources.
    fn unload_track(&mut self, track: AudioTrackId) -> Result<()>;

    /// Shut down the audio subsystem and release all resources.
    fn shutdown(&mut self) -> Result<()>;
}
