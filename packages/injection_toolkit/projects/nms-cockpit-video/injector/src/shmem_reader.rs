//! Shared memory frame reader.
//!
//! Opens the daemon's shared memory frame buffer and polls for new video frames.
//! Uses the itk-shmem seqlock for lock-free reads from the triple-buffered region.

use crate::log::vlog;
use itk_shmem::FrameBuffer;

/// Default shared memory name (daemon must create with the same name).
const SHMEM_NAME: &str = "itk_video_frames";

/// Default video dimensions (must match daemon's frame buffer).
const DEFAULT_WIDTH: u32 = 1280;
const DEFAULT_HEIGHT: u32 = 720;

/// Reader that polls shared memory for new video frames.
pub struct ShmemFrameReader {
    fb: FrameBuffer,
    /// Buffer for frame data (reused across reads).
    frame_buf: Vec<u8>,
    /// Last seen PTS (to detect new frames).
    last_pts: u64,
    /// Frame dimensions.
    width: u32,
    height: u32,
}

impl ShmemFrameReader {
    /// Try to open the shared memory frame buffer.
    ///
    /// Returns `Err` if the daemon hasn't created the shared memory yet.
    pub fn open() -> Result<Self, String> {
        Self::open_with_dimensions(DEFAULT_WIDTH, DEFAULT_HEIGHT)
    }

    /// Open with specific dimensions.
    pub fn open_with_dimensions(width: u32, height: u32) -> Result<Self, String> {
        let fb = FrameBuffer::open(SHMEM_NAME, width, height)
            .map_err(|e| format!("Failed to open shmem '{}': {}", SHMEM_NAME, e))?;

        let frame_size = fb.frame_size();
        vlog!(
            "ShmemFrameReader: opened '{}' {}x{} frame_size={}",
            SHMEM_NAME,
            width,
            height,
            frame_size
        );

        Ok(Self {
            fb,
            frame_buf: vec![0u8; frame_size],
            last_pts: u64::MAX, // Sentinel: ensures first frame (PTS=0) is detected as new
            width,
            height,
        })
    }

    /// Poll for a new frame. Returns the RGBA data if a new frame is available.
    ///
    /// This is lock-free and non-blocking. Returns `None` if:
    /// - No new frame since last poll
    /// - Writer is in the middle of writing
    /// - Shared memory is in an inconsistent state
    pub fn poll_frame(&mut self) -> Option<&[u8]> {
        match self.fb.read_frame(self.last_pts, &mut self.frame_buf) {
            Ok((pts, changed)) => {
                if changed {
                    self.last_pts = pts;
                    Some(&self.frame_buf)
                } else {
                    None
                }
            }
            Err(_) => None,
        }
    }

    /// Get the frame width.
    pub fn width(&self) -> u32 {
        self.width
    }

    /// Get the frame height.
    pub fn height(&self) -> u32 {
        self.height
    }

    /// Get frame size in bytes (width * height * 4).
    pub fn frame_size(&self) -> usize {
        self.fb.frame_size()
    }

    /// Get the last PTS seen by this reader.
    pub fn last_pts(&self) -> u64 {
        self.last_pts
    }

    /// Read the current PTS from shared memory header (for diagnostics).
    pub fn shmem_pts(&self) -> u64 {
        self.fb
            .header()
            .pts_ms
            .load(std::sync::atomic::Ordering::Relaxed)
    }
}
