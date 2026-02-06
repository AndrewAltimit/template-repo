//! Unix shared memory implementation using POSIX shm_open

use super::{Result, SharedMemory, ShmemError};
use nix::fcntl::OFlag;
use nix::sys::mman::{MapFlags, ProtFlags, mmap, munmap, shm_open, shm_unlink};
use nix::sys::stat::{Mode, fstat};
use nix::unistd::ftruncate;
use std::ffi::CString;
use std::num::NonZeroUsize;
use std::os::fd::{AsRawFd, IntoRawFd};

/// Validate and create the shared memory name (/dev/shm/itk_name on Linux).
///
/// For security, this function:
/// - Rejects names with path traversal sequences (..)
/// - Rejects absolute paths (starting with /)
/// - Rejects names with path separators
/// - Creates names only in /itk_* namespace
fn make_name(name: &str) -> Result<String> {
    // Reject path traversal attempts
    if name.contains("..") {
        return Err(ShmemError::InvalidName(
            "name cannot contain path traversal sequences".into(),
        ));
    }

    // Reject absolute paths
    if name.starts_with('/') {
        return Err(ShmemError::InvalidName(
            "name cannot be an absolute path".into(),
        ));
    }

    // Reject names with path separators
    if name.contains('/') || name.contains('\\') {
        return Err(ShmemError::InvalidName(
            "name cannot contain path separators".into(),
        ));
    }

    Ok(format!("/itk_{}", name))
}

pub fn create(name: &str, size: usize) -> Result<SharedMemory> {
    let full_name = make_name(name)?;
    let c_name = CString::new(full_name.clone())
        .map_err(|_| ShmemError::InvalidName("Name contains null bytes".into()))?;

    // Try to unlink first in case it exists from a previous crash
    let _ = shm_unlink(c_name.as_c_str());

    // Create shared memory object
    let fd = shm_open(
        c_name.as_c_str(),
        OFlag::O_CREAT | OFlag::O_RDWR | OFlag::O_EXCL,
        Mode::S_IRUSR | Mode::S_IWUSR,
    )
    .map_err(|e| ShmemError::CreateFailed(e.to_string()))?;

    // Set size
    if let Err(e) = ftruncate(&fd, size as i64) {
        // OwnedFd will close the fd when dropped, no need to manually close
        // (manual close would cause double-close since OwnedFd also closes on drop)
        let _ = shm_unlink(c_name.as_c_str());
        return Err(ShmemError::CreateFailed(format!("ftruncate failed: {}", e)));
    }

    // Map memory
    let ptr = unsafe {
        mmap(
            None,
            NonZeroUsize::new(size)
                .ok_or_else(|| ShmemError::CreateFailed("Size is zero".into()))?,
            ProtFlags::PROT_READ | ProtFlags::PROT_WRITE,
            MapFlags::MAP_SHARED,
            &fd,
            0,
        )
        .map_err(|e| ShmemError::MapFailed(e.to_string()))?
    };

    // Take ownership of the fd - prevents OwnedFd from closing it on drop
    let raw_fd = fd.into_raw_fd();

    Ok(SharedMemory {
        ptr: ptr.as_ptr() as *mut u8,
        size,
        name: full_name,
        fd: raw_fd,
        owner: true,
    })
}

pub fn open(name: &str, size: usize) -> Result<SharedMemory> {
    let full_name = make_name(name)?;
    let c_name = CString::new(full_name.clone())
        .map_err(|_| ShmemError::InvalidName("Name contains null bytes".into()))?;

    // Open existing shared memory object
    let fd = shm_open(c_name.as_c_str(), OFlag::O_RDWR, Mode::empty())
        .map_err(|e| ShmemError::OpenFailed(e.to_string()))?;

    // Validate the actual size of the shared memory object
    let stat = fstat(fd.as_raw_fd())
        .map_err(|e| ShmemError::OpenFailed(format!("fstat failed: {}", e)))?;
    let actual_size = stat.st_size as usize;

    if actual_size < size {
        // OwnedFd will close the fd when dropped, no need to manually close
        return Err(ShmemError::SizeMismatch {
            expected: size,
            actual: actual_size,
        });
    }

    // Map memory
    let ptr = unsafe {
        mmap(
            None,
            NonZeroUsize::new(size).ok_or_else(|| ShmemError::OpenFailed("Size is zero".into()))?,
            ProtFlags::PROT_READ | ProtFlags::PROT_WRITE,
            MapFlags::MAP_SHARED,
            &fd,
            0,
        )
        .map_err(|e| ShmemError::MapFailed(e.to_string()))?
    };

    // Take ownership of the fd - prevents OwnedFd from closing it on drop
    let raw_fd = fd.into_raw_fd();

    Ok(SharedMemory {
        ptr: ptr.as_ptr() as *mut u8,
        size,
        name: full_name,
        fd: raw_fd,
        owner: false,
    })
}

pub fn cleanup(shmem: &mut SharedMemory) {
    // Unmap memory
    if !shmem.ptr.is_null() {
        unsafe {
            let ptr = std::ptr::NonNull::new(shmem.ptr as *mut _);
            if let Some(ptr) = ptr {
                let _ = munmap(ptr, shmem.size);
            }
        }
        shmem.ptr = std::ptr::null_mut();
    }

    // Close file descriptor
    if shmem.fd >= 0 {
        let _ = nix::unistd::close(shmem.fd);
        shmem.fd = -1;
    }

    // Unlink if owner
    if shmem.owner {
        if let Ok(c_name) = CString::new(shmem.name.clone()) {
            let _ = shm_unlink(c_name.as_c_str());
        }
    }
}
