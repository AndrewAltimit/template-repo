//! Process memory backends.
//!
//! [`ProcessMemory`] is the narrow, read-only boundary between the explorer
//! engine and the operating system. All OS-specific `unsafe` code lives behind
//! it (`windows.rs`, `linux.rs`); everything else (scanning, pointer chains,
//! watches, value refinement) is platform independent and unit tested against
//! the in-memory [`mock::MockMemory`] backend.

use crate::explorer::ExplorerError;
use crate::types::{MemoryRegion, ModuleInfo};

#[cfg(target_os = "linux")]
pub mod linux;
#[cfg(windows)]
pub mod windows;

#[cfg(test)]
pub mod mock;

/// Page granularity used when a large read fails and is retried page by page.
pub const PAGE_SIZE: u64 = 0x1000;

/// Read-only access to another process's address space.
///
/// Implementations must be safe to call from any thread and must never read
/// outside the caller-provided buffer.
pub trait ProcessMemory: Send + Sync {
    /// Process id of the target.
    fn pid(&self) -> u32;

    /// True when the target uses 32-bit pointers.
    fn is_32bit(&self) -> bool;

    /// Whether the target process is still running.
    fn is_alive(&self) -> bool;

    /// Read up to `buf.len()` bytes starting at `address`.
    ///
    /// Returns the number of bytes read, which may be less than requested if
    /// the range runs into unreadable memory. Returns an error when *nothing*
    /// could be read.
    fn read(&self, address: u64, buf: &mut [u8]) -> Result<usize, ExplorerError>;

    /// All committed memory regions (readable or not), sorted by base address.
    fn regions(&self) -> Result<Vec<MemoryRegion>, ExplorerError>;

    /// Loaded modules. The first entry is the main executable when known.
    fn modules(&self) -> Result<Vec<ModuleInfo>, ExplorerError>;
}

/// Read as many bytes as possible from `address`, stopping at the first
/// unreadable page.
///
/// Some OS APIs (notably `ReadProcessMemory`) fail the *whole* request if any
/// page in the range is inaccessible. When a full read fails this falls back to
/// page-sized reads so callers still get the readable prefix. Returns an empty
/// vector only if the very first byte is unreadable, in which case the
/// original error is returned instead.
pub fn read_prefix(
    mem: &dyn ProcessMemory,
    address: u64,
    len: usize,
) -> Result<Vec<u8>, ExplorerError> {
    let mut buf = vec![0u8; len];
    if len == 0 {
        return Ok(buf);
    }
    match mem.read(address, &mut buf) {
        Ok(n) if n == len => return Ok(buf),
        Ok(n) if n > 0 => {
            // Partial read: try to continue from where it stopped (page-wise).
            let more = read_pagewise(mem, address.wrapping_add(n as u64), &mut buf[n..]);
            buf.truncate(n + more);
            return Ok(buf);
        },
        Ok(_) => {},
        Err(e) => {
            let n = read_pagewise(mem, address, &mut buf);
            if n == 0 {
                return Err(e);
            }
            buf.truncate(n);
            return Ok(buf);
        },
    }
    let n = read_pagewise(mem, address, &mut buf);
    if n == 0 {
        return Err(ExplorerError::Read {
            address,
            reason: "no bytes readable".into(),
        });
    }
    buf.truncate(n);
    Ok(buf)
}

/// Fill `buf` page by page; returns the number of contiguous bytes read.
fn read_pagewise(mem: &dyn ProcessMemory, address: u64, buf: &mut [u8]) -> usize {
    let mut done = 0usize;
    while done < buf.len() {
        let cur = address.wrapping_add(done as u64);
        let to_page_end = (PAGE_SIZE - (cur % PAGE_SIZE)) as usize;
        let want = to_page_end.min(buf.len() - done);
        match mem.read(cur, &mut buf[done..done + want]) {
            Ok(n) if n > 0 => {
                done += n;
                if n < want {
                    break;
                }
            },
            _ => break,
        }
    }
    done
}

/// Read exactly `len` bytes or fail with a message naming how many were readable.
pub fn read_exact(
    mem: &dyn ProcessMemory,
    address: u64,
    len: usize,
) -> Result<Vec<u8>, ExplorerError> {
    let data = read_prefix(mem, address, len)?;
    if data.len() < len {
        return Err(ExplorerError::Read {
            address,
            reason: format!(
                "only {} of {} bytes are readable (range crosses into unreadable memory)",
                data.len(),
                len
            ),
        });
    }
    Ok(data)
}

/// Check that `[address, address + len)` does not wrap and fits the target's
/// pointer width.
pub fn check_range(address: u64, len: usize, is_32bit: bool) -> Result<(), ExplorerError> {
    let end = address.checked_add(len as u64).ok_or(ExplorerError::Read {
        address,
        reason: "range wraps past the end of the address space".into(),
    })?;
    if is_32bit && end > (1u64 << 32) {
        return Err(ExplorerError::Read {
            address,
            reason: "address is outside the 32-bit target's address space".into(),
        });
    }
    Ok(())
}

/// Open the platform backend for `pid`.
#[cfg(windows)]
pub fn open(pid: u32) -> Result<Box<dyn ProcessMemory>, ExplorerError> {
    Ok(Box::new(windows::WindowsProcess::open(pid)?))
}

/// Open the platform backend for `pid`.
#[cfg(target_os = "linux")]
pub fn open(pid: u32) -> Result<Box<dyn ProcessMemory>, ExplorerError> {
    Ok(Box::new(linux::LinuxProcess::open(pid)?))
}

/// Open the platform backend for `pid` (unsupported platform).
#[cfg(not(any(windows, target_os = "linux")))]
pub fn open(_pid: u32) -> Result<Box<dyn ProcessMemory>, ExplorerError> {
    Err(ExplorerError::PlatformNotSupported)
}

/// Whether this build can read process memory at all.
pub const MEMORY_ACCESS_SUPPORTED: bool = cfg!(any(windows, target_os = "linux"));

#[cfg(test)]
mod tests {
    use super::mock::MockMemory;
    use super::*;

    #[test]
    fn read_prefix_stops_at_gap() {
        // Readable [0x1000, 0x2000), gap, readable [0x3000, 0x4000).
        let mem = MockMemory::new()
            .with_region(0x1000, vec![1; 0x1000])
            .with_region(0x3000, vec![2; 0x1000])
            .all_or_nothing(true);
        let data = read_prefix(&mem, 0x1800, 0x1000).unwrap();
        assert_eq!(data.len(), 0x800);
        assert!(data.iter().all(|&b| b == 1));
        assert!(read_prefix(&mem, 0x2000, 16).is_err());
        assert!(read_exact(&mem, 0x1ff0, 0x20).is_err());
        assert_eq!(read_exact(&mem, 0x1ff0, 0x10).unwrap().len(), 0x10);
    }

    #[test]
    fn read_prefix_handles_partial_backends() {
        let mem = MockMemory::new()
            .with_region(0x1000, vec![7; 0x2000])
            .all_or_nothing(false);
        let data = read_prefix(&mem, 0x2f00, 0x400).unwrap();
        assert_eq!(data.len(), 0x100);
        assert_eq!(read_prefix(&mem, 0x1000, 0).unwrap().len(), 0);
    }

    #[test]
    fn range_checks() {
        assert!(check_range(u64::MAX - 1, 4, false).is_err());
        assert!(check_range(0xFFFF_FFF0, 0x20, true).is_err());
        assert!(check_range(0xFFFF_FFF0, 0x10, true).is_ok());
        assert!(check_range(0x1_0000_0000, 8, false).is_ok());
    }
}
