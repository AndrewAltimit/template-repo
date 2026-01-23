//! Error types for video operations.

use thiserror::Error;

/// Result type for video operations.
pub type VideoResult<T> = Result<T, VideoError>;

/// Errors that can occur during video operations.
#[derive(Debug, Error)]
pub enum VideoError {
    /// Failed to open the video source.
    #[error("failed to open video source: {0}")]
    OpenFailed(String),

    /// Failed to find a video stream in the source.
    #[error("no video stream found in source")]
    NoVideoStream,

    /// Failed to find a suitable decoder.
    #[error("no decoder found for codec: {0}")]
    NoDecoder(String),

    /// Failed to decode a frame.
    #[error("decode error: {0}")]
    DecodeError(String),

    /// Failed to scale/convert a frame.
    #[error("scaling error: {0}")]
    ScaleError(String),

    /// Failed to seek in the video.
    #[error("seek error: {0}")]
    SeekError(String),

    /// End of stream reached.
    #[error("end of stream")]
    EndOfStream,

    /// Invalid frame data.
    #[error("invalid frame data: {0}")]
    InvalidFrame(String),

    /// Shared memory error.
    #[error("shared memory error: {0}")]
    SharedMemory(#[from] itk_shmem::ShmemError),

    /// I/O error.
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// FFmpeg error.
    #[error("ffmpeg error: {0}")]
    Ffmpeg(String),

    /// YouTube extraction error (only with `youtube` feature).
    #[cfg(feature = "youtube")]
    #[error("YouTube extraction failed: {0}")]
    YoutubeExtraction(String),

    /// YouTube feature not enabled.
    #[error("YouTube support not enabled (build with --features youtube)")]
    YoutubeNotEnabled,

    /// Invalid URL format.
    #[error("invalid URL: {0}")]
    InvalidUrl(String),

    /// Unsupported pixel format.
    #[error("unsupported pixel format: {0:?}")]
    UnsupportedPixelFormat(String),
}

impl From<ffmpeg_next::Error> for VideoError {
    fn from(err: ffmpeg_next::Error) -> Self {
        VideoError::Ffmpeg(err.to_string())
    }
}
