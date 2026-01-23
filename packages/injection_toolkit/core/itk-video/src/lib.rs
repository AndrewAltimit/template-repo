//! Video decoding and frame management for the Injection Toolkit.
//!
//! This crate provides video decoding capabilities using ffmpeg-next,
//! with support for local files, HLS/DASH streams, and optionally YouTube
//! via yt-dlp.
//!
//! # Architecture
//!
//! ```text
//! StreamSource (file/URL)
//!       │
//!       ▼
//! VideoDecoder (ffmpeg-next)
//!       │
//!       ▼
//! Scaler (to 1280x720 RGBA)
//!       │
//!       ▼
//! FrameWriter (to shared memory)
//! ```
//!
//! # Example
//!
//! ```ignore
//! use itk_video::{VideoDecoder, StreamSource, FrameWriter};
//! use itk_shmem::FrameBuffer;
//!
//! let source = StreamSource::File("/path/to/video.mp4".into());
//! let mut decoder = VideoDecoder::new(source)?;
//! let buffer = FrameBuffer::create("video_frames", 1280, 720)?;
//! let mut writer = FrameWriter::new(buffer);
//!
//! while let Some(frame) = decoder.next_frame()? {
//!     writer.write_frame(&frame)?;
//! }
//! ```

pub mod decoder;
pub mod error;
pub mod frame_writer;
pub mod scaler;
pub mod stream;

#[cfg(feature = "youtube")]
pub mod youtube;

pub use decoder::VideoDecoder;
pub use error::{VideoError, VideoResult};
pub use frame_writer::FrameWriter;
pub use scaler::FrameScaler;
pub use stream::StreamSource;

/// Default output width for video frames (720p).
pub const DEFAULT_WIDTH: u32 = 1280;

/// Default output height for video frames (720p).
pub const DEFAULT_HEIGHT: u32 = 720;

/// Bytes per pixel for RGBA format.
pub const BYTES_PER_PIXEL: usize = 4;

/// Calculate the size of a single frame in bytes.
#[inline]
pub const fn frame_size(width: u32, height: u32) -> usize {
    (width as usize) * (height as usize) * BYTES_PER_PIXEL
}
