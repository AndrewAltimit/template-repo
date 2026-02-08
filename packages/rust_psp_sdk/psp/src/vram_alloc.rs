//! Video RAM bump allocator.
//!
//! Provides a simple bump allocator for PSP VRAM. Allocations are served
//! sequentially from the start of VRAM; call `free_all()` to reset.

use crate::sys::TexturePixelFormat;
use crate::sys::{sceGeEdramGetAddr, sceGeEdramGetSize};
use core::marker::PhantomData;
use core::mem::size_of;
use core::ptr::null_mut;
use core::sync::atomic::{AtomicBool, AtomicU32, Ordering};

type VramAllocator = SimpleVramAllocator;

#[derive(Debug)]
pub struct VramAllocatorInUseError {}

/// Errors returned by VRAM allocation operations.
#[derive(Debug)]
pub enum VramAllocError {
    /// Not enough VRAM remaining for the requested allocation.
    OutOfMemory { requested: u32, available: u32 },
    /// The given texture pixel format is not supported by the allocator.
    UnsupportedPixelFormat,
    /// Integer overflow computing allocation size.
    Overflow,
}

/// Atomic guard ensuring only one VRAM allocator instance exists at a time.
/// Replaces the previous `static mut` singleton with a safe atomic pattern.
static VRAM_TAKEN: AtomicBool = AtomicBool::new(false);

pub fn get_vram_allocator() -> Result<VramAllocator, VramAllocatorInUseError> {
    if VRAM_TAKEN
        .compare_exchange(false, true, Ordering::Acquire, Ordering::Relaxed)
        .is_ok()
    {
        Ok(VramAllocator::new())
    } else {
        Err(VramAllocatorInUseError {})
    }
}

pub struct VramMemChunk<'a> {
    start: u32,
    len: u32,
    // Needed since VramMemChunk has a lifetime, but doesn't contain references
    vram: PhantomData<&'a mut ()>,
}

impl VramMemChunk<'_> {
    fn new(start: u32, len: u32) -> Self {
        Self {
            start,
            len,
            vram: PhantomData,
        }
    }

    pub fn as_mut_ptr_from_zero(&self) -> *mut u8 {
        unsafe { vram_start_addr_zero().add(self.start as usize) }
    }

    pub fn as_mut_ptr_direct_to_vram(&self) -> *mut u8 {
        unsafe { vram_start_addr_direct().add(self.start as usize) }
    }

    pub fn len(&self) -> u32 {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
}

/// A dead-simple VRAM bump allocator.
#[derive(Debug)]
pub struct SimpleVramAllocator {
    offset: AtomicU32,
}

impl SimpleVramAllocator {
    const fn new() -> Self {
        Self {
            offset: AtomicU32::new(0),
        }
    }

    /// Frees all previously allocated VRAM chunks.
    ///
    /// This resets the allocator's counter, but does not change the contents of
    /// VRAM. Since this method requires `&mut Self`, it cannot overlap with any
    /// previously allocated `VramMemChunk`s since they have the lifetime of the
    /// `&Self` that allocated them.
    pub fn free_all(&mut self) {
        self.offset.store(0, Ordering::Relaxed);
    }

    /// Allocates `size` bytes of VRAM.
    ///
    /// Returns `Err(VramAllocError::OutOfMemory)` if the allocation would
    /// exceed total VRAM. The returned chunk has the same lifetime as the
    /// `&self` borrow that allocated it.
    pub fn alloc(&self, size: u32) -> Result<VramMemChunk<'_>, VramAllocError> {
        let old_offset = self.offset.load(Ordering::Relaxed);
        let new_offset = old_offset
            .checked_add(size)
            .ok_or(VramAllocError::Overflow)?;
        let total = self.total_mem();

        if new_offset > total {
            return Err(VramAllocError::OutOfMemory {
                requested: size,
                available: total.saturating_sub(old_offset),
            });
        }

        self.offset.store(new_offset, Ordering::Relaxed);
        Ok(VramMemChunk::new(old_offset, size))
    }

    /// Allocates space for `count` elements of type `T`.
    pub fn alloc_sized<T: Sized>(&self, count: u32) -> Result<VramMemChunk<'_>, VramAllocError> {
        let size = (size_of::<T>() as u32)
            .checked_mul(count)
            .ok_or(VramAllocError::Overflow)?;
        self.alloc(size)
    }

    /// Allocates space for a texture with the given dimensions and pixel format.
    pub fn alloc_texture_pixels(
        &self,
        width: u32,
        height: u32,
        psm: TexturePixelFormat,
    ) -> Result<VramMemChunk<'_>, VramAllocError> {
        let size = get_memory_size(width, height, psm)?;
        self.alloc(size)
    }

    /// Moves `obj` into VRAM and returns a mutable reference to it.
    ///
    /// # Safety
    ///
    /// The caller must ensure the VRAM region is not concurrently accessed
    /// and that the returned reference is not used after `free_all()`.
    pub unsafe fn move_to_vram<T: Sized>(
        &mut self,
        obj: T,
    ) -> Result<&mut T, VramAllocError> {
        let chunk = self.alloc_sized::<T>(1)?;
        let ptr = chunk.as_mut_ptr_direct_to_vram() as *mut T;
        unsafe {
            ptr.write(obj);
            Ok(&mut *ptr)
        }
    }

    fn total_mem(&self) -> u32 {
        total_vram_size()
    }
}

fn total_vram_size() -> u32 {
    unsafe { sceGeEdramGetSize() }
}

// NOTE: VRAM actually starts at 0x4000000, as returned by sceGeEdramGetAddr.
//       The Gu functions take that into account, and start their pointer
//       indices at 0. See GE_EDRAM_ADDRESS in gu.rs for that offset being used.
fn vram_start_addr_zero() -> *mut u8 {
    null_mut()
}

fn vram_start_addr_direct() -> *mut u8 {
    unsafe { sceGeEdramGetAddr() }
}

fn get_memory_size(
    width: u32,
    height: u32,
    psm: TexturePixelFormat,
) -> Result<u32, VramAllocError> {
    match psm {
        TexturePixelFormat::PsmT4 => Ok((width * height) >> 1),
        TexturePixelFormat::PsmT8 => Ok(width * height),

        TexturePixelFormat::Psm5650
        | TexturePixelFormat::Psm5551
        | TexturePixelFormat::Psm4444
        | TexturePixelFormat::PsmT16 => Ok(2 * width * height),

        TexturePixelFormat::Psm8888 | TexturePixelFormat::PsmT32 => Ok(4 * width * height),

        _ => Err(VramAllocError::UnsupportedPixelFormat),
    }
}
