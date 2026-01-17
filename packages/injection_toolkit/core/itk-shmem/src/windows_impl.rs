//! Windows shared memory implementation using CreateFileMappingW

use super::{Result, SharedMemory, ShmemError};
use std::ffi::OsStr;
use std::os::windows::ffi::OsStrExt;
use windows::Win32::Foundation::{CloseHandle, HANDLE};
use windows::Win32::System::Memory::{
    CreateFileMappingW, MapViewOfFile, OpenFileMappingW, UnmapViewOfFile, FILE_MAP_ALL_ACCESS,
    MEMORY_MAPPED_VIEW_ADDRESS, PAGE_READWRITE,
};

/// Convert a Rust string to a Windows wide string
fn to_wide_string(s: &str) -> Vec<u16> {
    OsStr::new(s).encode_wide().chain(Some(0)).collect()
}

/// Create the shared memory name (Local\ namespace for same-session access)
fn make_name(name: &str) -> String {
    format!("Local\\itk_{}", name)
}

pub fn create(name: &str, size: usize) -> Result<SharedMemory> {
    let full_name = make_name(name);
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
    let full_name = make_name(name);
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
