//! PSP system memory allocator and C runtime memory functions.

#![allow(unsafe_op_in_unsafe_fn)]

use crate::sys::{self, SceSysMemBlockTypes, SceSysMemPartitionId, SceUid};
use alloc::alloc::{GlobalAlloc, Layout};
use core::{mem, ptr};

/// An allocator that hooks directly into the PSP OS memory allocator.
struct SystemAlloc;

unsafe impl GlobalAlloc for SystemAlloc {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let Some(size) = layout.size()
            // We need to store the memory block ID.
            .checked_add(mem::size_of::<SceUid>())
            // We also store padding bytes, in case the block returned from the
            // system is not aligned. The count of padding bytes is also stored
            // here, in the last byte.
            .and_then(|s| s.checked_add(layout.align()))
        else {
            return ptr::null_mut();
        };

        let id = sys::sceKernelAllocPartitionMemory(
            SceSysMemPartitionId::SceKernelPrimaryUserPartition,
            &b"block\0"[0],
            SceSysMemBlockTypes::Low,
            size as u32,
            ptr::null_mut(),
        );

        if id.0 < 0 {
            return ptr::null_mut();
        }

        let mut ptr: *mut u8 = sys::sceKernelGetBlockHeadAddr(id).cast();
        *ptr.cast() = id;

        ptr = ptr.add(mem::size_of::<SceUid>());

        // We must add at least one, to store this value.
        let align_padding = 1 + ptr.add(1).align_offset(layout.align());
        *ptr.add(align_padding - 1) = align_padding as u8;
        ptr.add(align_padding)
    }

    #[inline(never)]
    unsafe fn dealloc(&self, ptr: *mut u8, _layout: Layout) {
        let align_padding = *ptr.sub(1);

        let id = *ptr.sub(align_padding as usize).cast::<SceUid>().offset(-1);

        sys::sceKernelFreePartitionMemory(id);
    }
}

#[global_allocator]
static ALLOC: SystemAlloc = SystemAlloc;

#[cfg(not(feature = "std"))]
#[alloc_error_handler]
fn aeh(_: Layout) -> ! {
    dprintln!("out of memory");
    loop {
        core::hint::spin_loop()
    }
}

// NOTE: These C runtime functions MUST use manual byte loops, not
// `core::ptr::write_bytes` / `copy_nonoverlapping` / `copy`. Those
// intrinsics lower to calls to memset/memcpy/memmove respectively,
// creating infinite recursion (which on MIPS manifests as a jump to
// an invalid trampoline address).

#[unsafe(no_mangle)]
#[cfg(not(feature = "stub-only"))]
unsafe extern "C" fn memset(ptr: *mut u8, value: u32, num: usize) -> *mut u8 {
    let mut i = 0;
    while i < num {
        *ptr.add(i) = value as u8;
        i += 1;
    }
    ptr
}

#[unsafe(no_mangle)]
#[cfg(not(feature = "stub-only"))]
unsafe extern "C" fn memcpy(dst: *mut u8, src: *const u8, num: isize) -> *mut u8 {
    let mut i = 0isize;
    while i < num {
        *dst.offset(i) = *src.offset(i);
        i += 1;
    }
    dst
}

#[unsafe(no_mangle)]
#[cfg(not(feature = "stub-only"))]
unsafe extern "C" fn memcmp(ptr1: *mut u8, ptr2: *mut u8, num: usize) -> i32 {
    let mut i = 0;
    while i < num {
        let diff = *ptr1.add(i) as i32 - *ptr2.add(i) as i32;
        if diff != 0 {
            return diff;
        }
        i += 1;
    }
    0
}

#[unsafe(no_mangle)]
#[cfg(not(feature = "stub-only"))]
unsafe extern "C" fn memmove(dst: *mut u8, src: *mut u8, num: isize) -> *mut u8 {
    if (dst as usize) < (src as usize) {
        let mut i = 0isize;
        while i < num {
            *dst.offset(i) = *src.offset(i);
            i += 1;
        }
    } else {
        let mut i = num;
        while i > 0 {
            i -= 1;
            *dst.offset(i) = *src.offset(i);
        }
    }
    dst
}

#[unsafe(no_mangle)]
#[cfg(not(feature = "stub-only"))]
unsafe extern "C" fn strlen(s: *mut u8) -> usize {
    let mut len = 0;

    while *s.add(len) != 0 {
        len += 1;
    }

    len
}
