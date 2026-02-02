//! Video frame reader for the overlay.
//!
//! Reads decoded video frames from shared memory written by the daemon.

use itk_shmem::FrameBuffer;
use tracing::{debug, trace, warn};

/// Default shared memory name for video frames.
const SHMEM_NAME: &str = "itk_video_frames";
/// Default video width.
const DEFAULT_WIDTH: u32 = 1280;
/// Default video height.
const DEFAULT_HEIGHT: u32 = 720;

/// Reader for video frames from shared memory.
pub struct VideoFrameReader {
    buffer: Option<FrameBuffer>,
    frame_data: Vec<u8>,
    last_pts_ms: u64,
    width: u32,
    height: u32,
}

impl VideoFrameReader {
    /// Create a new video frame reader.
    ///
    /// Attempts to open the shared memory region created by the daemon.
    /// If the region doesn't exist yet, the reader will retry on each read.
    pub fn new() -> Self {
        let width = DEFAULT_WIDTH;
        let height = DEFAULT_HEIGHT;
        let frame_size = (width as usize) * (height as usize) * 4;

        // Try to open the shared memory region
        let buffer = match FrameBuffer::open(SHMEM_NAME, width, height) {
            Ok(fb) => {
                debug!("Opened video frame buffer");
                Some(fb)
            },
            Err(e) => {
                debug!(
                    ?e,
                    "Frame buffer not available yet (daemon may not be running)"
                );
                None
            },
        };

        Self {
            buffer,
            frame_data: vec![0u8; frame_size],
            last_pts_ms: 0,
            width,
            height,
        }
    }

    /// Try to read the latest frame.
    ///
    /// Returns `Some(data)` if a new frame is available, `None` otherwise.
    /// The returned slice is valid until the next call to `try_read_frame`.
    pub fn try_read_frame(&mut self) -> Option<&[u8]> {
        // Try to open the buffer if we don't have it yet
        if self.buffer.is_none() {
            self.buffer = FrameBuffer::open(SHMEM_NAME, self.width, self.height).ok();
            if self.buffer.is_some() {
                debug!("Connected to video frame buffer");
            }
        }

        let buffer = self.buffer.as_ref()?;

        // Try to read a frame
        match buffer.read_frame(self.last_pts_ms, &mut self.frame_data) {
            Ok((pts_ms, changed)) => {
                if changed {
                    self.last_pts_ms = pts_ms;
                    trace!(pts_ms, "Read new frame");
                    Some(&self.frame_data)
                } else {
                    None
                }
            },
            Err(itk_shmem::ShmemError::SeqlockContention) => {
                // Writer may be slow or crashed, don't spam logs
                trace!("Seqlock contention, will retry");
                None
            },
            Err(e) => {
                warn!(?e, "Failed to read frame");
                // Connection may have been lost, try to reconnect next time
                self.buffer = None;
                None
            },
        }
    }

    /// Get the last presentation timestamp in milliseconds.
    pub fn last_pts_ms(&self) -> u64 {
        self.last_pts_ms
    }

    /// Check if connected to the frame buffer.
    pub fn is_connected(&self) -> bool {
        self.buffer.is_some()
    }

    /// Get the frame dimensions.
    pub fn dimensions(&self) -> (u32, u32) {
        (self.width, self.height)
    }

    /// Get a reference to the current frame data (may be stale).
    pub fn current_frame(&self) -> &[u8] {
        &self.frame_data
    }
}

impl Default for VideoFrameReader {
    fn default() -> Self {
        Self::new()
    }
}
