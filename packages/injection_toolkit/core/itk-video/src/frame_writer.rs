//! Frame writer for shared memory output.

use crate::decoder::DecodedFrame;
use crate::error::{VideoError, VideoResult};
use crate::{DEFAULT_HEIGHT, DEFAULT_WIDTH};
use itk_shmem::{FrameBuffer, SharedMemory};
use std::hash::{Hash, Hasher};
use tracing::{debug, trace};

/// Default shared memory name for video frames.
pub const DEFAULT_SHMEM_NAME: &str = "itk_video_frames";

/// Writes decoded video frames to a shared memory buffer.
pub struct FrameWriter {
    buffer: FrameBuffer,
    last_pts_ms: u64,
    content_id_hash: u64,
}

impl FrameWriter {
    /// Create a new frame writer with a new shared memory region.
    pub fn create(name: &str, width: u32, height: u32) -> VideoResult<Self> {
        let buffer = FrameBuffer::create(name, width, height)?;
        Ok(Self {
            buffer,
            last_pts_ms: 0,
            content_id_hash: 0,
        })
    }

    /// Create a new frame writer with the default name and 720p resolution.
    pub fn create_default() -> VideoResult<Self> {
        Self::create(DEFAULT_SHMEM_NAME, DEFAULT_WIDTH, DEFAULT_HEIGHT)
    }

    /// Open an existing shared memory region for writing.
    pub fn open(name: &str, width: u32, height: u32) -> VideoResult<Self> {
        let buffer = FrameBuffer::open(name, width, height)?;
        Ok(Self {
            buffer,
            last_pts_ms: 0,
            content_id_hash: 0,
        })
    }

    /// Set the content ID for change detection.
    ///
    /// This should be called when loading a new video.
    /// The hash is used by readers to detect content changes.
    pub fn set_content_id(&mut self, content_id: &str) {
        self.content_id_hash = hash_content_id(content_id);
        debug!(content_id, hash = self.content_id_hash, "content ID set");
    }

    /// Set the total duration in milliseconds.
    ///
    /// This should be called when loading a new video so readers
    /// can display seek bars and time remaining.
    pub fn set_duration_ms(&self, duration_ms: u64) {
        self.buffer.set_duration_ms(duration_ms);
    }

    /// Write a decoded frame to shared memory.
    ///
    /// Uses frame-skip optimization: if the PTS hasn't changed (e.g., video is paused),
    /// the write is skipped to avoid unnecessary memory copies.
    ///
    /// Returns `true` if the frame was written, `false` if skipped.
    pub fn write_frame(&mut self, frame: &DecodedFrame) -> VideoResult<bool> {
        // Frame-skip optimization: don't write if PTS hasn't changed
        if frame.pts_ms == self.last_pts_ms && self.last_pts_ms > 0 {
            trace!(pts_ms = frame.pts_ms, "skipping duplicate frame");
            return Ok(false);
        }

        // Verify frame dimensions match buffer
        let expected_size = (frame.width as usize) * (frame.height as usize) * 4;
        if frame.data.len() != expected_size {
            return Err(VideoError::InvalidFrame(format!(
                "frame size mismatch: expected {} bytes, got {}",
                expected_size,
                frame.data.len()
            )));
        }

        // Write to the shared memory buffer
        unsafe {
            self.buffer
                .write_frame(&frame.data, frame.pts_ms, self.content_id_hash)?;
        }

        self.last_pts_ms = frame.pts_ms;
        trace!(pts_ms = frame.pts_ms, "wrote frame to shmem");
        Ok(true)
    }

    /// Write raw frame data to shared memory.
    ///
    /// This is a lower-level API for when you have raw RGBA data.
    pub fn write_raw(&mut self, data: &[u8], pts_ms: u64) -> VideoResult<bool> {
        // Frame-skip optimization
        if pts_ms == self.last_pts_ms && self.last_pts_ms > 0 {
            return Ok(false);
        }

        unsafe {
            self.buffer.write_frame(data, pts_ms, self.content_id_hash)?;
        }

        self.last_pts_ms = pts_ms;
        Ok(true)
    }

    /// Get the last written PTS in milliseconds.
    pub fn last_pts_ms(&self) -> u64 {
        self.last_pts_ms
    }

    /// Get the content ID hash.
    pub fn content_id_hash(&self) -> u64 {
        self.content_id_hash
    }

    /// Get the frame buffer's width.
    pub fn width(&self) -> u32 {
        self.buffer.width()
    }

    /// Get the frame buffer's height.
    pub fn height(&self) -> u32 {
        self.buffer.height()
    }
}

/// Hash a content ID string to a u64.
fn hash_content_id(content_id: &str) -> u64 {
    use std::collections::hash_map::DefaultHasher;
    let mut hasher = DefaultHasher::new();
    content_id.hash(&mut hasher);
    hasher.finish()
}

/// Frame reader for shared memory input.
///
/// This is used by the overlay to read frames written by the daemon.
pub struct FrameReader {
    buffer: FrameBuffer,
    last_pts_ms: u64,
    frame_data: Vec<u8>,
}

impl FrameReader {
    /// Open an existing shared memory region for reading.
    pub fn open(name: &str, width: u32, height: u32) -> VideoResult<Self> {
        let buffer = FrameBuffer::open(name, width, height)?;
        let frame_size = (width as usize) * (height as usize) * 4;
        Ok(Self {
            buffer,
            last_pts_ms: 0,
            frame_data: vec![0u8; frame_size],
        })
    }

    /// Open with the default name and 720p resolution.
    pub fn open_default() -> VideoResult<Self> {
        Self::open(DEFAULT_SHMEM_NAME, DEFAULT_WIDTH, DEFAULT_HEIGHT)
    }

    /// Try to read the latest frame.
    ///
    /// Returns `Some((pts_ms, data))` if a new frame is available,
    /// `None` if the frame hasn't changed since the last read.
    pub fn read_frame(&mut self) -> VideoResult<Option<(u64, &[u8])>> {
        let (pts_ms, changed) = self.buffer.read_frame(self.last_pts_ms, &mut self.frame_data)?;

        if changed {
            self.last_pts_ms = pts_ms;
            Ok(Some((pts_ms, &self.frame_data)))
        } else {
            Ok(None)
        }
    }

    /// Get the last read PTS in milliseconds.
    pub fn last_pts_ms(&self) -> u64 {
        self.last_pts_ms
    }

    /// Get the frame buffer's width.
    pub fn width(&self) -> u32 {
        self.buffer.width()
    }

    /// Get the frame buffer's height.
    pub fn height(&self) -> u32 {
        self.buffer.height()
    }

    /// Get a reference to the current frame data.
    pub fn current_frame(&self) -> &[u8] {
        &self.frame_data
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_content_id_hash() {
        let hash1 = hash_content_id("test_video.mp4");
        let hash2 = hash_content_id("test_video.mp4");
        let hash3 = hash_content_id("other_video.mp4");

        assert_eq!(hash1, hash2);
        assert_ne!(hash1, hash3);
    }
}
