//! Windows shared memory implementation using CreateFileMappingW

use super::{Result, SharedMemory, ShmemError};
use std::ffi::OsStr;
use std::os::windows::ffi::OsStrExt;
use windows::Win32::Foundation::{CloseHandle, GetLastError, ERROR_ALREADY_EXISTS, HANDLE};
use windows::Win32::System::Memory::{
    CreateFileMappingW, MapViewOfFile, OpenFileMappingW, UnmapViewOfFile, VirtualQuery,
    FILE_MAP_ALL_ACCESS, MEMORY_BASIC_INFORMATION, MEMORY_MAPPED_VIEW_ADDRESS, PAGE_READWRITE,
};

/// Convert a Rust string to a Windows wide string
fn to_wide_string(s: &str) -> Vec<u16> {
    OsStr::new(s).encode_wide().chain(Some(0)).collect()
}

/// Validate and create the shared memory name (Local\ namespace for same-session access).
///
/// For security, this function:
/// - Rejects names with path traversal sequences (..)
/// - Rejects names that look like full object paths (starting with Local\ or Global\)
/// - Rejects names with path separators
/// - Creates names only in Local\itk_* namespace
fn make_name(name: &str) -> Result<String> {
    // Reject path traversal attempts
    if name.contains("..") {
        return Err(ShmemError::InvalidName(
            "name cannot contain path traversal sequences".into(),
        ));
    }

    // Reject names that look like they're trying to specify a full object path
    if name.starts_with("Local\\") || name.starts_with("Global\\") {
        return Err(ShmemError::InvalidName(
            "name cannot be a full object path".into(),
        ));
    }

    // Reject names with path separators
    if name.contains('\\') || name.contains('/') {
        return Err(ShmemError::InvalidName(
            "name cannot contain path separators".into(),
        ));
    }

    Ok(format!("Local\\itk_{}", name))
}

pub fn create(name: &str, size: usize) -> Result<SharedMemory> {
    let full_name = make_name(name)?;
    let wide_name = to_wide_string(&full_name);

    unsafe {
        // Create file mapping
        let handle = CreateFileMappingW(
            HANDLE::default(), // Use paging file
            None,              // Default security
            PAGE_READWRITE,
            (size >> 32) as u32,
            size as u32,
            windows::core::PCWSTR(wide_name.as_ptr()),
        )
        .map_err(|e| ShmemError::CreateFailed(e.to_string()))?;

        if handle.is_invalid() {
            return Err(ShmemError::CreateFailed("Invalid handle returned".into()));
        }

        // Check if we attached to an existing mapping instead of creating a new one.
        // This prevents silently attaching to a stale region with wrong size/semantics.
        if GetLastError() == ERROR_ALREADY_EXISTS {
            CloseHandle(handle).ok();
            return Err(ShmemError::AlreadyExists);
        }

        // Map view
        let ptr = MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, size);

        if ptr.Value.is_null() {
            CloseHandle(handle).ok();
            return Err(ShmemError::MapFailed("MapViewOfFile returned null".into()));
        }

        Ok(SharedMemory {
            ptr: ptr.Value as *mut u8,
            size,
            name: full_name,
            handle,
            owner: true,
        })
    }
}

pub fn open(name: &str, size: usize) -> Result<SharedMemory> {
    let full_name = make_name(name)?;
    let wide_name = to_wide_string(&full_name);

    unsafe {
        // Open existing file mapping
        let handle = OpenFileMappingW(
            FILE_MAP_ALL_ACCESS.0,
            false,
            windows::core::PCWSTR(wide_name.as_ptr()),
        )
        .map_err(|e| ShmemError::OpenFailed(e.to_string()))?;

        if handle.is_invalid() {
            return Err(ShmemError::NotFound);
        }

        // Map the entire section first (size=0) to query its actual size
        let ptr = MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, 0);

        if ptr.Value.is_null() {
            CloseHandle(handle).ok();
            return Err(ShmemError::MapFailed("MapViewOfFile returned null".into()));
        }

        // Query the actual region size
        let mut mbi: MEMORY_BASIC_INFORMATION = std::mem::zeroed();
        let query_result = VirtualQuery(
            Some(ptr.Value),
            &mut mbi,
            std::mem::size_of::<MEMORY_BASIC_INFORMATION>(),
        );

        if query_result == 0 {
            UnmapViewOfFile(ptr).ok();
            CloseHandle(handle).ok();
            return Err(ShmemError::OpenFailed("VirtualQuery failed".into()));
        }

        let actual_size = mbi.RegionSize;

        if actual_size < size {
            UnmapViewOfFile(ptr).ok();
            CloseHandle(handle).ok();
            return Err(ShmemError::SizeMismatch {
                expected: size,
                actual: actual_size,
            });
        }

        Ok(SharedMemory {
            ptr: ptr.Value as *mut u8,
            size,
            name: full_name,
            handle,
            owner: false,
        })
    }
}

pub fn cleanup(shmem: &mut SharedMemory) {
    unsafe {
        if !shmem.ptr.is_null() {
            let _ = UnmapViewOfFile(MEMORY_MAPPED_VIEW_ADDRESS {
                Value: shmem.ptr as *mut _,
            });
            shmem.ptr = std::ptr::null_mut();
        }

        if !shmem.handle.is_invalid() {
            let _ = CloseHandle(shmem.handle);
            shmem.handle = HANDLE::default();
        }
    }
}
