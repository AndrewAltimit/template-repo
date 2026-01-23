//! Video Frame Reader
//!
//! Reads video frames from shared memory written by the daemon.

use itk_shmem::FrameBuffer;
use tracing::debug;

/// Name of the shared memory buffer for video frames
const VIDEO_BUFFER_NAME: &str = "itk_video_frames";

/// Default video dimensions (720p)
const DEFAULT_WIDTH: u32 = 1280;
const DEFAULT_HEIGHT: u32 = 720;

/// Video frame reader - reads frames from shared memory
pub struct VideoFrameReader {
    /// Frame buffer connection
    buffer: Option<FrameBuffer>,
    /// Last frame data (kept for returning reference)
    last_frame: Vec<u8>,
    /// Last presentation timestamp
    last_pts: u64,
    /// Whether we've attempted connection
    connection_attempted: bool,
}

impl VideoFrameReader {
    /// Create a new video frame reader
    pub fn new() -> Self {
        Self {
            buffer: None,
            last_frame: Vec::new(),
            last_pts: 0,
            connection_attempted: false,
        }
    }

    /// Check if connected to the frame buffer
    pub fn is_connected(&self) -> bool {
        self.buffer.is_some()
    }

    /// Get the last presentation timestamp in milliseconds
    pub fn last_pts_ms(&self) -> u64 {
        self.last_pts
    }

    /// Try to connect to the shared memory buffer
    fn try_connect(&mut self) {
        if self.buffer.is_some() {
            return;
        }

        match FrameBuffer::open(VIDEO_BUFFER_NAME, DEFAULT_WIDTH, DEFAULT_HEIGHT) {
            Ok(buffer) => {
                debug!("Connected to video frame buffer");
                // Pre-allocate frame buffer
                self.last_frame = vec![0u8; buffer.frame_size()];
                self.buffer = Some(buffer);
            }
            Err(e) => {
                if !self.connection_attempted {
                    debug!(?e, "Frame buffer not available yet");
                    self.connection_attempted = true;
                }
            }
        }
    }

    /// Try to read a new frame from shared memory
    ///
    /// Returns Some(&[u8]) if a new frame is available, None otherwise.
    pub fn try_read_frame(&mut self) -> Option<&[u8]> {
        // Try to connect if not connected
        if self.buffer.is_none() {
            self.try_connect();
        }

        // Read frame if connected
        if let Some(ref buffer) = self.buffer {
            match buffer.read_frame(self.last_pts, &mut self.last_frame) {
                Ok((pts_ms, data_changed)) => {
                    if data_changed {
                        self.last_pts = pts_ms;
                        return Some(&self.last_frame);
                    }
                }
                Err(e) => {
                    debug!(?e, "Failed to read frame");
                }
            }
        }

        None
    }
}

impl Default for VideoFrameReader {
    fn default() -> Self {
        Self::new()
    }
}
