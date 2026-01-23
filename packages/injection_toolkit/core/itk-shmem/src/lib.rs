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

    #[error("size calculation overflow: dimensions {width}x{height} exceed maximum")]
    SizeOverflow { width: u32, height: u32 },

    #[error("seqlock read contention: writer may have crashed or is holding lock too long")]
    SeqlockContention,
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
    #[allow(dead_code)] // Used for cleanup logic, may be utilized in future
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
        // Use checked_add to prevent overflow bypassing the bounds check
        let end = offset
            .checked_add(buf.len())
            .ok_or(ShmemError::Platform("offset + length overflow".into()))?;

        if end > self.size {
            return Err(ShmemError::SizeMismatch {
                expected: end,
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
        // Use checked_add to prevent overflow bypassing the bounds check
        let end = offset
            .checked_add(buf.len())
            .ok_or(ShmemError::Platform("offset + length overflow".into()))?;

        if end > self.size {
            return Err(ShmemError::SizeMismatch {
                expected: end,
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
/// Uses carefully chosen memory orderings for ARM compatibility.
///
/// # Thread Safety
///
/// **SINGLE-WRITER ONLY**: This seqlock assumes exactly one writer thread/process.
/// Multiple concurrent writers will corrupt the sequence counter and cause
/// undefined behavior. If you need multiple writers, protect the write path
/// with an external mutex.
///
/// Multiple readers are safe and supported - the seqlock is designed for
/// one-writer-many-readers scenarios (e.g., frame buffer synchronization).
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
    /// Total duration in milliseconds (0 if unknown/live)
    pub duration_ms: AtomicU64,
    /// Padding to cache line (64 bytes)
    _padding: [u8; 12],
}

impl SeqlockHeader {
    /// Size of the header in bytes (cache-line aligned)
    pub const SIZE: usize = 64;

    /// Initialize a seqlock header at the given memory location
    ///
    /// # Safety
    /// - The pointer must be valid and aligned for SeqlockHeader.
    /// - The returned reference is only valid while the underlying memory is valid.
    ///   Caller must ensure the memory outlives the returned reference.
    pub unsafe fn init<'a>(ptr: *mut u8) -> &'a Self {
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
        (*header).duration_ms = AtomicU64::new(0);

        &*header
    }

    /// Get a reference to an existing seqlock header
    ///
    /// # Safety
    /// - The pointer must be valid and point to an initialized SeqlockHeader.
    /// - The returned reference is only valid while the underlying memory is valid.
    ///   Caller must ensure the memory outlives the returned reference.
    pub unsafe fn from_ptr<'a>(ptr: *mut u8) -> &'a Self {
        &*(ptr as *const SeqlockHeader)
    }

    /// Begin a write operation (marks sequence as odd)
    ///
    /// Uses Acquire ordering to prevent subsequent data writes from being
    /// reordered before the sequence increment. This ensures readers see
    /// the odd sequence before any new data is written.
    pub fn begin_write(&self) {
        self.seq.fetch_add(1, Ordering::Acquire);
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
    /// Memory ordering for ARM compatibility:
    /// - Acquire on first seq read synchronizes with writer's Release
    /// - Relaxed for data reads (bounded by seqlock)
    /// - Acquire fence before second seq check prevents data reads from
    ///   being reordered past the validation
    pub fn try_read(&self) -> Option<SeqlockState> {
        let seq1 = self.read_seq_acquire();
        if seq1 & 1 != 0 {
            return None; // Write in progress
        }

        // Data reads can be Relaxed - bounded by seqlock fence below
        let state = SeqlockState {
            read_idx: self.read_idx.load(Ordering::Relaxed),
            pts_ms: self.pts_ms.load(Ordering::Relaxed),
            frame_width: self.frame_width.load(Ordering::Relaxed),
            frame_height: self.frame_height.load(Ordering::Relaxed),
            is_playing: self.is_playing.load(Ordering::Relaxed) != 0,
            content_id_hash: self.content_id_hash.load(Ordering::Relaxed),
            duration_ms: self.duration_ms.load(Ordering::Relaxed),
        };

        // Critical: Prevent data loads from sinking past the sequence check.
        // Without this fence, the CPU could reorder seq2 read before data reads,
        // causing us to validate against an old sequence while reading new data.
        std::sync::atomic::fence(Ordering::Acquire);

        // Relaxed is sufficient here - the fence above provides ordering
        let seq2 = self.seq.load(Ordering::Relaxed);
        if seq1 != seq2 {
            return None; // Write happened during read
        }

        Some(state)
    }

    /// Read state, spinning until consistent
    ///
    /// **Warning**: This can spin indefinitely if the writer crashes while holding
    /// the seqlock (seq stuck on odd). Use `read_with_timeout` for bounded waiting.
    pub fn read_blocking(&self) -> SeqlockState {
        loop {
            if let Some(state) = self.try_read() {
                return state;
            }
            std::hint::spin_loop();
        }
    }

    /// Read state with bounded retries to prevent infinite spinning.
    ///
    /// If the writer crashes while holding the seqlock (seq stuck on odd),
    /// this will return `SeqlockContention` after `max_attempts` iterations
    /// instead of spinning forever.
    ///
    /// # Arguments
    /// * `max_attempts` - Maximum number of read attempts before giving up
    ///
    /// # Recommended Values
    /// - 1000 for tight polling loops
    /// - 10000 for looser real-time requirements
    /// - 100000 for batch processing with tolerance for delays
    pub fn read_with_timeout(&self, max_attempts: u32) -> Result<SeqlockState> {
        for _ in 0..max_attempts {
            if let Some(state) = self.try_read() {
                return Ok(state);
            }
            std::hint::spin_loop();
        }
        Err(ShmemError::SeqlockContention)
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
    pub duration_ms: u64,
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
    width: u32,
    height: u32,
}

impl FrameBuffer {
    /// Calculate total shared memory size needed for given frame dimensions
    ///
    /// Returns an error if the dimensions would cause arithmetic overflow.
    pub fn calculate_size(width: u32, height: u32) -> Result<usize> {
        let frame_size = (width as usize)
            .checked_mul(height as usize)
            .and_then(|s| s.checked_mul(4)) // RGBA
            .ok_or(ShmemError::SizeOverflow { width, height })?;

        SeqlockHeader::SIZE
            .checked_add(
                frame_size
                    .checked_mul(3)
                    .ok_or(ShmemError::SizeOverflow { width, height })?,
            )
            .ok_or(ShmemError::SizeOverflow { width, height })
    }

    /// Create a new frame buffer
    pub fn create(name: &str, width: u32, height: u32) -> Result<Self> {
        let frame_size = (width as usize)
            .checked_mul(height as usize)
            .and_then(|s| s.checked_mul(4))
            .ok_or(ShmemError::SizeOverflow { width, height })?;
        let total_size = Self::calculate_size(width, height)?;

        let shmem = SharedMemory::create(name, total_size)?;

        // Initialize the header (Relaxed is fine during init - no readers yet)
        unsafe {
            let header = SeqlockHeader::init(shmem.as_ptr());
            header.frame_width.store(width, Ordering::Relaxed);
            header.frame_height.store(height, Ordering::Relaxed);
        }

        Ok(Self {
            shmem,
            frame_size,
            width,
            height,
        })
    }

    /// Open an existing frame buffer
    pub fn open(name: &str, width: u32, height: u32) -> Result<Self> {
        let frame_size = (width as usize)
            .checked_mul(height as usize)
            .and_then(|s| s.checked_mul(4))
            .ok_or(ShmemError::SizeOverflow { width, height })?;
        let total_size = Self::calculate_size(width, height)?;

        let shmem = SharedMemory::open(name, total_size)?;

        Ok(Self {
            shmem,
            frame_size,
            width,
            height,
        })
    }

    /// Get the frame width
    pub fn width(&self) -> u32 {
        self.width
    }

    /// Get the frame height
    pub fn height(&self) -> u32 {
        self.height
    }

    /// Get the size of a single frame in bytes
    pub fn frame_size(&self) -> usize {
        self.frame_size
    }

    /// Get the seqlock header
    pub fn header(&self) -> &SeqlockHeader {
        unsafe { SeqlockHeader::from_ptr(self.shmem.as_ptr()) }
    }

    /// Set the duration in milliseconds (metadata, not per-frame).
    ///
    /// This is written outside the seqlock since it only changes on load.
    pub fn set_duration_ms(&self, duration_ms: u64) {
        self.header().duration_ms.store(duration_ms, Ordering::Release);
    }

    /// Get the duration in milliseconds.
    pub fn duration_ms(&self) -> u64 {
        self.header().duration_ms.load(Ordering::Acquire)
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

        // Begin critical section - marks seq odd
        // Acquire ordering prevents subsequent data writes from floating up
        header.begin_write();

        // Write buffer data inside the seqlock critical section
        // This ensures proper ordering on weak memory models (ARM)
        let buf_ptr = self.buffer_ptr(write_idx);
        std::ptr::copy_nonoverlapping(data.as_ptr(), buf_ptr, data.len());

        // Update header fields
        header.read_idx.store(write_idx, Ordering::Relaxed);
        header.pts_ms.store(pts_ms, Ordering::Relaxed);
        header
            .content_id_hash
            .store(content_id_hash, Ordering::Relaxed);

        // End critical section - marks seq even
        // Release ordering ensures all writes are visible before this
        header.end_write();

        Ok(())
    }

    /// Maximum retry attempts before returning contention error
    const MAX_READ_ATTEMPTS: u32 = 10000;

    /// Read the current frame (consumer side)
    ///
    /// Returns (pts_ms, data_changed) where data_changed indicates
    /// if this is a new frame since the last read.
    ///
    /// This method has bounded retries to prevent infinite spinning if the
    /// writer crashes or holds the seqlock for too long.
    pub fn read_frame(&self, last_pts: u64, buf: &mut [u8]) -> Result<(u64, bool)> {
        if buf.len() != self.frame_size {
            return Err(ShmemError::SizeMismatch {
                expected: self.frame_size,
                actual: buf.len(),
            });
        }

        for _ in 0..Self::MAX_READ_ATTEMPTS {
            // Use bounded read to prevent spinning on crashed writer
            let state = self.header().read_with_timeout(1000)?;

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

        Err(ShmemError::SeqlockContention)
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
        let size = FrameBuffer::calculate_size(1280, 720).unwrap();
        assert_eq!(size, 64 + (1280 * 720 * 4 * 3));

        // Test overflow detection with extremely large dimensions
        let overflow_result = FrameBuffer::calculate_size(u32::MAX, u32::MAX);
        assert!(overflow_result.is_err());
    }

    /// Aligned storage for SeqlockHeader in tests
    #[repr(C, align(64))]
    struct AlignedHeaderMem([u8; SeqlockHeader::SIZE]);

    #[test]
    fn test_seqlock_write_makes_odd_then_even() {
        let mut header_mem = AlignedHeaderMem([0u8; SeqlockHeader::SIZE]);
        let header = unsafe { SeqlockHeader::init(header_mem.0.as_mut_ptr()) };

        assert_eq!(header.seq.load(Ordering::SeqCst), 0);
        assert!(!header.is_write_in_progress());

        header.begin_write();
        assert_eq!(header.seq.load(Ordering::SeqCst), 1);
        assert!(header.is_write_in_progress());

        header.end_write();
        assert_eq!(header.seq.load(Ordering::SeqCst), 2);
        assert!(!header.is_write_in_progress());
    }

    #[test]
    fn test_seqlock_try_read_returns_none_during_write() {
        let mut header_mem = AlignedHeaderMem([0u8; SeqlockHeader::SIZE]);
        let header = unsafe { SeqlockHeader::init(header_mem.0.as_mut_ptr()) };

        // Set some initial values
        header.read_idx.store(1, Ordering::Relaxed);
        header.pts_ms.store(12345, Ordering::Relaxed);

        // Before write - should succeed
        let state = header.try_read();
        assert!(state.is_some());
        assert_eq!(state.unwrap().read_idx, 1);

        // During write - should fail
        header.begin_write();
        assert!(header.try_read().is_none());

        // After write - should succeed
        header.end_write();
        let state = header.try_read();
        assert!(state.is_some());
    }

    #[test]
    fn test_seqlock_detects_concurrent_modification() {
        let mut header_mem = AlignedHeaderMem([0u8; SeqlockHeader::SIZE]);
        let header = unsafe { SeqlockHeader::init(header_mem.0.as_mut_ptr()) };

        // Simulate a "torn read" scenario:
        // Reader gets seq1, then writer completes a full write cycle
        let seq1 = header.seq.load(Ordering::Acquire);
        assert_eq!(seq1, 0);

        // Writer does a complete write
        header.begin_write();
        header.read_idx.store(42, Ordering::Relaxed);
        header.end_write();

        // seq changed from 0 to 2, so seq1 != seq2
        let seq2 = header.seq.load(Ordering::Acquire);
        assert_ne!(seq1, seq2);
    }
}

/// Loom-based concurrency tests for verifying seqlock correctness
/// Run with: RUSTFLAGS="--cfg loom" cargo test --lib loom_tests
#[cfg(all(test, loom))]
mod loom_tests {
    use loom::sync::atomic::{AtomicU32, AtomicU64, Ordering};
    use loom::sync::Arc;
    use loom::thread;

    /// Simplified seqlock for loom testing
    struct LoomSeqlock {
        seq: AtomicU32,
        value: AtomicU64,
    }

    impl LoomSeqlock {
        fn new() -> Self {
            Self {
                seq: AtomicU32::new(0),
                value: AtomicU64::new(0),
            }
        }

        fn write(&self, val: u64) {
            // Begin write (odd) - Acquire prevents data writes from floating up
            self.seq.fetch_add(1, Ordering::Acquire);

            // Write data
            self.value.store(val, Ordering::Relaxed);

            // End write (even) - Release ensures data writes are visible
            self.seq.fetch_add(1, Ordering::Release);
        }

        fn try_read(&self) -> Option<u64> {
            let seq1 = self.seq.load(Ordering::Acquire);
            if seq1 & 1 != 0 {
                return None; // Write in progress
            }

            let val = self.value.load(Ordering::Relaxed);

            // Fence prevents data loads from sinking past seq2 check
            loom::sync::atomic::fence(Ordering::Acquire);

            let seq2 = self.seq.load(Ordering::Relaxed);
            if seq1 != seq2 {
                return None; // Write happened during read
            }

            Some(val)
        }
    }

    #[test]
    fn loom_seqlock_single_writer_single_reader() {
        loom::model(|| {
            let lock = Arc::new(LoomSeqlock::new());
            let lock2 = Arc::clone(&lock);

            let writer = thread::spawn(move || {
                lock2.write(42);
            });

            // Reader may see 0 (initial) or 42 (written), but never garbage
            loop {
                if let Some(val) = lock.try_read() {
                    assert!(val == 0 || val == 42, "Got unexpected value: {}", val);
                    break;
                }
                // Retry if write was in progress
                loom::thread::yield_now();
            }

            writer.join().unwrap();
        });
    }

    #[test]
    fn loom_seqlock_multiple_writes() {
        loom::model(|| {
            let lock = Arc::new(LoomSeqlock::new());
            let lock2 = Arc::clone(&lock);

            let writer = thread::spawn(move || {
                lock2.write(1);
                lock2.write(2);
            });

            // Reader should only see valid states: 0, 1, or 2
            let mut last_seen = 0;
            for _ in 0..3 {
                if let Some(val) = lock.try_read() {
                    assert!(val == 0 || val == 1 || val == 2, "Invalid value: {}", val);
                    assert!(val >= last_seen, "Values should not decrease");
                    last_seen = val;
                }
                loom::thread::yield_now();
            }

            writer.join().unwrap();
        });
    }
}
