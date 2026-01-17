//! # ITK Shared Memory
//!
//! Cross-platform shared memory primitives for the Injection Toolkit.
//!
//! This crate provides:
//! - Platform-agnostic shared memory regions
//! - Seqlock-based lock-free synchronization
//! - Triple-buffered frame transfer
//!
//! ## Platform Support
//!
//! - **Windows**: Named shared memory via `CreateFileMappingW`
//! - **Linux**: POSIX shared memory via `shm_open`

use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use thiserror::Error;

/// Shared memory errors
#[derive(Error, Debug)]
pub enum ShmemError {
    #[error("failed to create shared memory: {0}")]
    CreateFailed(String),

    #[error("failed to open shared memory: {0}")]
    OpenFailed(String),

    #[error("failed to map shared memory: {0}")]
    MapFailed(String),

    #[error("shared memory size mismatch: expected {expected}, got {actual}")]
    SizeMismatch { expected: usize, actual: usize },

    #[error("invalid shared memory name: {0}")]
    InvalidName(String),

    #[error("shared memory already exists")]
    AlreadyExists,

    #[error("shared memory not found")]
    NotFound,

    #[error("platform error: {0}")]
    Platform(String),
}

/// Result type for shared memory operations
pub type Result<T> = std::result::Result<T, ShmemError>;

/// Shared memory region handle
pub struct SharedMemory {
    ptr: *mut u8,
    size: usize,
    name: String,
    #[cfg(windows)]
    handle: windows::Win32::Foundation::HANDLE,
    #[cfg(unix)]
    fd: std::os::unix::io::RawFd,
    owner: bool,
}

// SAFETY: SharedMemory uses raw pointers but the memory region is process-shared
// and we use atomic operations for synchronization.
unsafe impl Send for SharedMemory {}
unsafe impl Sync for SharedMemory {}

impl SharedMemory {
    /// Create a new shared memory region
    ///
    /// # Arguments
    /// * `name` - Unique identifier for the shared memory
    /// * `size` - Size in bytes
    ///
    /// # Platform Notes
    /// - Windows: Name becomes `Global\{name}` or `Local\{name}`
    /// - Linux: Name becomes `/itk_{name}` in `/dev/shm`
    pub fn create(name: &str, size: usize) -> Result<Self> {
        Self::create_impl(name, size)
    }

    /// Open an existing shared memory region
    pub fn open(name: &str, size: usize) -> Result<Self> {
        Self::open_impl(name, size)
    }

    /// Get a raw pointer to the shared memory
    ///
    /// # Safety
    /// Caller must ensure proper synchronization when accessing the memory.
    pub fn as_ptr(&self) -> *mut u8 {
        self.ptr
    }

    /// Get the size of the shared memory region
    pub fn size(&self) -> usize {
        self.size
    }

    /// Get the name of the shared memory region
    pub fn name(&self) -> &str {
        &self.name
    }

    /// Read bytes from the shared memory
    ///
    /// # Safety
    /// Caller must ensure no concurrent writes or use appropriate synchronization.
    pub unsafe fn read(&self, offset: usize, buf: &mut [u8]) -> Result<()> {
        if offset + buf.len() > self.size {
            return Err(ShmemError::SizeMismatch {
                expected: offset + buf.len(),
                actual: self.size,
            });
        }

        std::ptr::copy_nonoverlapping(self.ptr.add(offset), buf.as_mut_ptr(), buf.len());

        Ok(())
    }

    /// Write bytes to the shared memory
    ///
    /// # Safety
    /// Caller must ensure no concurrent reads or use appropriate synchronization.
    pub unsafe fn write(&self, offset: usize, buf: &[u8]) -> Result<()> {
        if offset + buf.len() > self.size {
            return Err(ShmemError::SizeMismatch {
                expected: offset + buf.len(),
                actual: self.size,
            });
        }

        std::ptr::copy_nonoverlapping(buf.as_ptr(), self.ptr.add(offset), buf.len());

        Ok(())
    }
}

// Platform-specific implementations
cfg_if::cfg_if! {
    if #[cfg(windows)] {
        mod windows_impl;
        use windows_impl::*;

        impl SharedMemory {
            fn create_impl(name: &str, size: usize) -> Result<Self> {
                windows_impl::create(name, size)
            }

            fn open_impl(name: &str, size: usize) -> Result<Self> {
                windows_impl::open(name, size)
            }
        }

        impl Drop for SharedMemory {
            fn drop(&mut self) {
                windows_impl::cleanup(self);
            }
        }
    } else if #[cfg(unix)] {
        mod unix_impl;

        impl SharedMemory {
            fn create_impl(name: &str, size: usize) -> Result<Self> {
                unix_impl::create(name, size)
            }

            fn open_impl(name: &str, size: usize) -> Result<Self> {
                unix_impl::open(name, size)
            }
        }

        impl Drop for SharedMemory {
            fn drop(&mut self) {
                unix_impl::cleanup(self);
            }
        }
    }
}

/// Seqlock header for lock-free synchronization
///
/// This is placed at the start of the shared memory region.
/// All operations use SeqCst ordering for simplicity and correctness.
#[repr(C)]
pub struct SeqlockHeader {
    /// Sequence number (odd = write in progress, even = consistent)
    pub seq: AtomicU32,
    /// Index of the current read buffer (0-2 for triple buffering)
    pub read_idx: AtomicU32,
    /// Presentation timestamp in milliseconds
    pub pts_ms: AtomicU64,
    /// Frame width (for validation)
    pub frame_width: AtomicU32,
    /// Frame height (for validation)
    pub frame_height: AtomicU32,
    /// Playback state (1 = playing, 0 = paused)
    pub is_playing: AtomicU32,
    /// Quick hash of content ID for change detection
    pub content_id_hash: AtomicU64,
    /// Padding to cache line (64 bytes)
    _padding: [u8; 20],
}

impl SeqlockHeader {
    /// Size of the header in bytes (cache-line aligned)
    pub const SIZE: usize = 64;

    /// Initialize a seqlock header at the given memory location
    ///
    /// # Safety
    /// The pointer must be valid and aligned for SeqlockHeader.
    pub unsafe fn init(ptr: *mut u8) -> &'static Self {
        let header = ptr as *mut SeqlockHeader;

        // Zero-initialize
        std::ptr::write_bytes(header, 0, 1);

        // Set initial values
        (*header).seq = AtomicU32::new(0);
        (*header).read_idx = AtomicU32::new(0);
        (*header).pts_ms = AtomicU64::new(0);
        (*header).frame_width = AtomicU32::new(0);
        (*header).frame_height = AtomicU32::new(0);
        (*header).is_playing = AtomicU32::new(0);
        (*header).content_id_hash = AtomicU64::new(0);

        &*header
    }

    /// Get a reference to an existing seqlock header
    ///
    /// # Safety
    /// The pointer must be valid and point to an initialized SeqlockHeader.
    pub unsafe fn from_ptr(ptr: *mut u8) -> &'static Self {
        &*(ptr as *const SeqlockHeader)
    }

    /// Begin a write operation (marks sequence as odd)
    ///
    /// Uses Release ordering to ensure readers see the odd sequence
    /// before any data writes become visible.
    pub fn begin_write(&self) {
        self.seq.fetch_add(1, Ordering::Release);
    }

    /// End a write operation (marks sequence as even)
    ///
    /// Uses Release ordering to ensure all data writes are visible
    /// before the even sequence number.
    pub fn end_write(&self) {
        self.seq.fetch_add(1, Ordering::Release);
    }

    /// Read the current sequence number with Acquire ordering
    fn read_seq_acquire(&self) -> u32 {
        self.seq.load(Ordering::Acquire)
    }

    /// Check if a write is in progress (sequence is odd)
    pub fn is_write_in_progress(&self) -> bool {
        self.read_seq_acquire() & 1 != 0
    }

    /// Try to read consistent state
    ///
    /// Returns None if a write was in progress.
    /// Caller should retry in a loop.
    ///
    /// Uses Acquire/Release semantics for ARM compatibility:
    /// - Acquire on sequence reads synchronizes with writer's Release
    /// - Relaxed for data reads (protected by seqlock)
    pub fn try_read(&self) -> Option<SeqlockState> {
        let seq1 = self.read_seq_acquire();
        if seq1 & 1 != 0 {
            return None; // Write in progress
        }

        // Data reads can be Relaxed - seqlock provides synchronization
        let state = SeqlockState {
            read_idx: self.read_idx.load(Ordering::Relaxed),
            pts_ms: self.pts_ms.load(Ordering::Relaxed),
            frame_width: self.frame_width.load(Ordering::Relaxed),
            frame_height: self.frame_height.load(Ordering::Relaxed),
            is_playing: self.is_playing.load(Ordering::Relaxed) != 0,
            content_id_hash: self.content_id_hash.load(Ordering::Relaxed),
        };

        let seq2 = self.read_seq_acquire();
        if seq1 != seq2 {
            return None; // Write happened during read
        }

        Some(state)
    }

    /// Read state, spinning until consistent
    pub fn read_blocking(&self) -> SeqlockState {
        loop {
            if let Some(state) = self.try_read() {
                return state;
            }
            std::hint::spin_loop();
        }
    }
}

/// Snapshot of seqlock state
#[derive(Debug, Clone)]
pub struct SeqlockState {
    pub read_idx: u32,
    pub pts_ms: u64,
    pub frame_width: u32,
    pub frame_height: u32,
    pub is_playing: bool,
    pub content_id_hash: u64,
}

/// Triple-buffered frame storage
///
/// Layout in shared memory:
/// ```text
/// [SeqlockHeader: 64 bytes]
/// [Buffer 0: width * height * 4 bytes]
/// [Buffer 1: width * height * 4 bytes]
/// [Buffer 2: width * height * 4 bytes]
/// ```
pub struct FrameBuffer {
    shmem: SharedMemory,
    frame_size: usize,
}

impl FrameBuffer {
    /// Calculate total shared memory size needed for given frame dimensions
    pub fn calculate_size(width: u32, height: u32) -> usize {
        let frame_size = (width as usize) * (height as usize) * 4; // RGBA
        SeqlockHeader::SIZE + (frame_size * 3) // Triple buffer
    }

    /// Create a new frame buffer
    pub fn create(name: &str, width: u32, height: u32) -> Result<Self> {
        let frame_size = (width as usize) * (height as usize) * 4;
        let total_size = Self::calculate_size(width, height);

        let shmem = SharedMemory::create(name, total_size)?;

        // Initialize the header (Relaxed is fine during init - no readers yet)
        unsafe {
            let header = SeqlockHeader::init(shmem.as_ptr());
            header.frame_width.store(width, Ordering::Relaxed);
            header.frame_height.store(height, Ordering::Relaxed);
        }

        Ok(Self { shmem, frame_size })
    }

    /// Open an existing frame buffer
    pub fn open(name: &str, width: u32, height: u32) -> Result<Self> {
        let frame_size = (width as usize) * (height as usize) * 4;
        let total_size = Self::calculate_size(width, height);

        let shmem = SharedMemory::open(name, total_size)?;

        Ok(Self { shmem, frame_size })
    }

    /// Get the seqlock header
    pub fn header(&self) -> &SeqlockHeader {
        unsafe { SeqlockHeader::from_ptr(self.shmem.as_ptr()) }
    }

    /// Get a pointer to a specific buffer
    fn buffer_ptr(&self, idx: u32) -> *mut u8 {
        let offset = SeqlockHeader::SIZE + (idx as usize % 3) * self.frame_size;
        unsafe { self.shmem.as_ptr().add(offset) }
    }

    /// Write a frame (producer side)
    ///
    /// # Safety
    /// - `data` must be exactly `frame_size` bytes
    /// - Only one writer should be active
    pub unsafe fn write_frame(&self, data: &[u8], pts_ms: u64, content_id_hash: u64) -> Result<()> {
        if data.len() != self.frame_size {
            return Err(ShmemError::SizeMismatch {
                expected: self.frame_size,
                actual: data.len(),
            });
        }

        let header = self.header();

        // Get next write buffer (round-robin)
        // Relaxed is fine here - we're the only writer
        let current_idx = header.read_idx.load(Ordering::Relaxed);
        let write_idx = (current_idx + 1) % 3;

        // Write to buffer (outside seqlock - buffer not yet visible)
        let buf_ptr = self.buffer_ptr(write_idx);
        std::ptr::copy_nonoverlapping(data.as_ptr(), buf_ptr, data.len());

        // Update header atomically
        // begin_write uses Release, data stores can be Relaxed,
        // end_write uses Release to make everything visible
        header.begin_write();
        header.read_idx.store(write_idx, Ordering::Relaxed);
        header.pts_ms.store(pts_ms, Ordering::Relaxed);
        header.content_id_hash.store(content_id_hash, Ordering::Relaxed);
        header.end_write();

        Ok(())
    }

    /// Read the current frame (consumer side)
    ///
    /// Returns (pts_ms, data_changed) where data_changed indicates
    /// if this is a new frame since the last read.
    pub fn read_frame(&self, last_pts: u64, buf: &mut [u8]) -> Result<(u64, bool)> {
        if buf.len() != self.frame_size {
            return Err(ShmemError::SizeMismatch {
                expected: self.frame_size,
                actual: buf.len(),
            });
        }

        loop {
            let state = self.header().read_blocking();

            // Skip copy if same frame
            if state.pts_ms == last_pts {
                return Ok((state.pts_ms, false));
            }

            // Copy frame data
            let buf_ptr = self.buffer_ptr(state.read_idx);
            unsafe {
                std::ptr::copy_nonoverlapping(buf_ptr, buf.as_mut_ptr(), self.frame_size);
            }

            // Verify consistency after copy
            if let Some(state2) = self.header().try_read() {
                if state2.read_idx == state.read_idx && state2.pts_ms == state.pts_ms {
                    return Ok((state.pts_ms, true));
                }
            }

            // State changed during read, retry
            std::hint::spin_loop();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_seqlock_header_size() {
        assert_eq!(std::mem::size_of::<SeqlockHeader>(), SeqlockHeader::SIZE);
    }

    #[test]
    fn test_calculate_size() {
        // 1280x720 RGBA = 3,686,400 bytes per frame
        // Triple buffered + 64 byte header
        let size = FrameBuffer::calculate_size(1280, 720);
        assert_eq!(size, 64 + (1280 * 720 * 4 * 3));
    }
}
