//! Windows backend: `OpenProcess` + `ReadProcessMemory` + `VirtualQueryEx` +
//! Toolhelp module snapshots.
//!
//! The process is opened with the minimum rights needed for read-only
//! inspection (`PROCESS_VM_READ | PROCESS_QUERY_INFORMATION | SYNCHRONIZE`),
//! never `PROCESS_ALL_ACCESS`. Every kernel handle is owned by an RAII
//! [`OwnedHandle`] so no error path can leak it.

use std::ffi::c_void;

use windows::Win32::Foundation::{CloseHandle, ERROR_BAD_LENGTH, HANDLE, WAIT_TIMEOUT};
use windows::Win32::System::Diagnostics::Debug::ReadProcessMemory;
use windows::Win32::System::Diagnostics::ToolHelp::{
    CreateToolhelp32Snapshot, MODULEENTRY32W, Module32FirstW, Module32NextW, TH32CS_SNAPMODULE,
    TH32CS_SNAPMODULE32,
};
use windows::Win32::System::Memory::{
    MEM_COMMIT, MEM_IMAGE, MEM_MAPPED, MEM_PRIVATE, MEMORY_BASIC_INFORMATION, VirtualQueryEx,
};
use windows::Win32::System::Threading::{
    IsWow64Process, OpenProcess, PROCESS_QUERY_INFORMATION, PROCESS_SYNCHRONIZE, PROCESS_VM_READ,
    WaitForSingleObject,
};
use windows::core::BOOL;

use super::ProcessMemory;
use crate::explorer::ExplorerError;
use crate::types::{MemoryRegion, ModuleInfo};

/// Upper bound on regions returned by one `VirtualQueryEx` walk (defensive
/// against a pathological or racing address space).
const MAX_REGIONS: usize = 1_000_000;

/// A kernel handle closed on drop.
struct OwnedHandle(HANDLE);

impl Drop for OwnedHandle {
    fn drop(&mut self) {
        if !self.0.is_invalid() {
            // SAFETY: we own this handle (obtained from OpenProcess /
            // CreateToolhelp32Snapshot) and close it exactly once.
            unsafe {
                let _ = CloseHandle(self.0);
            }
        }
    }
}

// SAFETY: a process/snapshot HANDLE is an opaque kernel object reference that
// is valid from any thread of this process. The APIs used on it here
// (ReadProcessMemory, VirtualQueryEx, WaitForSingleObject, Toolhelp) are
// thread-safe and never mutate Rust-visible state through the handle.
unsafe impl Send for OwnedHandle {}
// SAFETY: see `Send` above; shared `&OwnedHandle` only permits those
// thread-safe read-only calls.
unsafe impl Sync for OwnedHandle {}

/// An opened target process.
pub struct WindowsProcess {
    handle: OwnedHandle,
    pid: u32,
    is_32bit: bool,
}

impl WindowsProcess {
    /// Open `pid` for read-only inspection.
    pub fn open(pid: u32) -> Result<Self, ExplorerError> {
        let access = PROCESS_VM_READ | PROCESS_QUERY_INFORMATION | PROCESS_SYNCHRONIZE;
        // SAFETY: plain FFI call; the returned handle is immediately wrapped in
        // an owner that closes it.
        let raw = unsafe { OpenProcess(access, false, pid) }.map_err(|e| {
            ExplorerError::OpenProcess(format!(
                "OpenProcess(pid {}) failed: {}. Reading another process's memory requires \
                 the same user (or Administrator) and does not work on protected or \
                 anti-cheat-guarded processes.",
                pid,
                e.message()
            ))
        })?;
        let handle = OwnedHandle(raw);

        let mut wow64 = BOOL::default();
        // SAFETY: `handle` is a valid process handle with QUERY_INFORMATION
        // access; `wow64` is a valid out-pointer for the call's duration.
        let is_wow64 = unsafe { IsWow64Process(handle.0, &mut wow64) }.is_ok() && wow64.as_bool();
        // A 32-bit server can only meaningfully inspect 32-bit targets.
        let is_32bit = cfg!(target_pointer_width = "32") || is_wow64;

        Ok(Self {
            handle,
            pid,
            is_32bit,
        })
    }
}

/// Classify a `PAGE_*` protection value into (readable, writable, executable).
fn classify_protect(protect: u32) -> (bool, bool, bool) {
    const PAGE_NOACCESS: u32 = 0x01;
    const PAGE_GUARD: u32 = 0x100;
    let base = protect & 0xff;
    if protect & PAGE_GUARD != 0 || base & PAGE_NOACCESS != 0 || base == 0 {
        // Guard pages fault on first touch (and would disarm the guard);
        // never read them.
        return (false, false, base & 0xf0 != 0);
    }
    let readable = matches!(base, 0x02 | 0x04 | 0x08 | 0x20 | 0x40 | 0x80);
    let writable = matches!(base, 0x04 | 0x08 | 0x40 | 0x80);
    let executable = matches!(base, 0x10 | 0x20 | 0x40 | 0x80);
    (readable, writable, executable)
}

/// Convert a NUL-terminated UTF-16 buffer to a `String`.
fn wide_to_string(buf: &[u16]) -> String {
    let end = buf.iter().position(|&c| c == 0).unwrap_or(buf.len());
    String::from_utf16_lossy(&buf[..end])
}

impl ProcessMemory for WindowsProcess {
    fn pid(&self) -> u32 {
        self.pid
    }

    fn is_32bit(&self) -> bool {
        self.is_32bit
    }

    fn is_alive(&self) -> bool {
        // SAFETY: valid handle opened with SYNCHRONIZE; a zero timeout never blocks.
        unsafe { WaitForSingleObject(self.handle.0, 0) == WAIT_TIMEOUT }
    }

    fn read(&self, address: u64, buf: &mut [u8]) -> Result<usize, ExplorerError> {
        if buf.is_empty() {
            return Ok(0);
        }
        let remote = usize::try_from(address).map_err(|_| ExplorerError::Read {
            address,
            reason: "address does not fit this build's pointer width".into(),
        })?;
        let mut read = 0usize;
        // SAFETY: `buf` is a valid, exclusively borrowed buffer of exactly
        // `buf.len()` bytes and the OS writes at most `nsize` bytes into it.
        // `remote` is interpreted in the *target's* address space, so any value
        // is memory-safe for this process (bad addresses just fail the call).
        let result = unsafe {
            ReadProcessMemory(
                self.handle.0,
                remote as *const c_void,
                buf.as_mut_ptr().cast::<c_void>(),
                buf.len(),
                Some(&mut read),
            )
        };
        match result {
            Ok(()) => Ok(read.min(buf.len())),
            // ERROR_PARTIAL_COPY may still report a readable prefix.
            Err(_) if read > 0 => Ok(read.min(buf.len())),
            Err(e) => Err(ExplorerError::Read {
                address,
                reason: e.message().trim().to_string(),
            }),
        }
    }

    fn regions(&self) -> Result<Vec<MemoryRegion>, ExplorerError> {
        let mut out = Vec::new();
        let mut addr: u64 = 0;
        while let Ok(query) = usize::try_from(addr) {
            let mut mbi = MEMORY_BASIC_INFORMATION::default();
            // SAFETY: `mbi` is a valid out-buffer of the size we pass; the
            // queried address is in the target's address space.
            let written = unsafe {
                VirtualQueryEx(
                    self.handle.0,
                    Some(query as *const c_void),
                    &mut mbi,
                    std::mem::size_of::<MEMORY_BASIC_INFORMATION>(),
                )
            };
            if written == 0 {
                // End of the user address space (or the process went away).
                break;
            }
            let base = mbi.BaseAddress as usize as u64;
            let size = mbi.RegionSize as u64;
            if mbi.State == MEM_COMMIT {
                let (readable, writable, executable) = classify_protect(mbi.Protect.0);
                let kind = if mbi.Type == MEM_IMAGE {
                    "image"
                } else if mbi.Type == MEM_MAPPED {
                    "mapped"
                } else if mbi.Type == MEM_PRIVATE {
                    "private"
                } else {
                    "unknown"
                };
                out.push(MemoryRegion {
                    base,
                    size,
                    readable,
                    writable,
                    executable,
                    kind: kind.to_string(),
                });
                if out.len() >= MAX_REGIONS {
                    break;
                }
            }
            match base.checked_add(size) {
                Some(next) if next > addr => addr = next,
                _ => break,
            }
        }
        if out.is_empty() && !self.is_alive() {
            return Err(ExplorerError::ProcessExited(self.pid));
        }
        Ok(out)
    }

    fn modules(&self) -> Result<Vec<ModuleInfo>, ExplorerError> {
        // CreateToolhelp32Snapshot can fail transiently with ERROR_BAD_LENGTH
        // while the target is loading/unloading modules; retry a few times.
        let mut attempt = 0;
        let snapshot = loop {
            // SAFETY: plain FFI call; the handle is wrapped immediately.
            match unsafe {
                CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, self.pid)
            } {
                Ok(h) => break OwnedHandle(h),
                Err(e) if e.code() == ERROR_BAD_LENGTH.to_hresult() && attempt < 5 => {
                    attempt += 1;
                    std::thread::sleep(std::time::Duration::from_millis(20));
                },
                Err(e) => {
                    return Err(ExplorerError::OpenProcess(format!(
                        "module snapshot for pid {} failed: {}",
                        self.pid,
                        e.message().trim()
                    )));
                },
            }
        };

        let mut entry = MODULEENTRY32W {
            dwSize: std::mem::size_of::<MODULEENTRY32W>() as u32,
            ..Default::default()
        };
        let mut modules = Vec::new();
        // SAFETY: `snapshot` is a valid Toolhelp snapshot handle and `entry` is
        // a correctly sized MODULEENTRY32W (dwSize set) that outlives each call.
        let mut ok = unsafe { Module32FirstW(snapshot.0, &mut entry) }.is_ok();
        while ok {
            modules.push(ModuleInfo {
                name: wide_to_string(&entry.szModule),
                base_address: entry.modBaseAddr as usize as u64,
                size: entry.modBaseSize as u64,
                path: Some(wide_to_string(&entry.szExePath)),
            });
            // SAFETY: as above.
            ok = unsafe { Module32NextW(snapshot.0, &mut entry) }.is_ok();
        }
        Ok(modules)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn protect_classification() {
        assert_eq!(classify_protect(0x02), (true, false, false)); // READONLY
        assert_eq!(classify_protect(0x04), (true, true, false)); // READWRITE
        assert_eq!(classify_protect(0x20), (true, false, true)); // EXECUTE_READ
        assert_eq!(classify_protect(0x40), (true, true, true)); // EXECUTE_READWRITE
        assert_eq!(classify_protect(0x10), (false, false, true)); // EXECUTE only
        assert_eq!(classify_protect(0x01), (false, false, false)); // NOACCESS
        assert!(!classify_protect(0x104).0, "guard pages are never readable");
    }

    #[test]
    fn wide_strings() {
        let mut buf = [0u16; 8];
        for (i, c) in "a.dll".encode_utf16().enumerate() {
            buf[i] = c;
        }
        assert_eq!(wide_to_string(&buf), "a.dll");
    }
}
