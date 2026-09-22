//! Linux backend: `/proc/<pid>/mem` for reads and `/proc/<pid>/maps` for
//! regions and modules.
//!
//! No `unsafe` is needed: positional reads on `/proc/<pid>/mem` are ordinary
//! file I/O. Access is governed by the kernel's ptrace access mode check, so the
//! server must run as the same user with `kernel.yama.ptrace_scope = 0`, or
//! with `CAP_SYS_PTRACE`. This also covers Wine/Proton games, whose PE images
//! show up as file-backed mappings.

use std::fs::File;
use std::os::unix::fs::FileExt;
use std::path::Path;

use super::ProcessMemory;
use crate::explorer::ExplorerError;
use crate::types::{MemoryRegion, ModuleInfo};

/// An opened target process.
pub struct LinuxProcess {
    mem: File,
    pid: u32,
    is_32bit: bool,
}

impl LinuxProcess {
    /// Open `/proc/<pid>/mem` read-only.
    pub fn open(pid: u32) -> Result<Self, ExplorerError> {
        let path = format!("/proc/{}/mem", pid);
        let mem = File::open(&path).map_err(|e| {
            ExplorerError::OpenProcess(format!(
                "cannot open {}: {}. Reading another process requires the same user with \
                 kernel.yama.ptrace_scope=0, or CAP_SYS_PTRACE.",
                path, e
            ))
        })?;
        Ok(Self {
            mem,
            pid,
            is_32bit: elf_is_32bit(&format!("/proc/{}/exe", pid)),
        })
    }
}

/// Read the ELF class byte of an executable (`1` = 32-bit). Defaults to 64-bit
/// when the file is unreadable or not ELF.
fn elf_is_32bit(path: &str) -> bool {
    let mut header = [0u8; 5];
    File::open(path)
        .and_then(|f| f.read_exact_at(&mut header, 0))
        .map(|_| &header[..4] == b"\x7fELF" && header[4] == 1)
        .unwrap_or(false)
}

/// One parsed `/proc/<pid>/maps` line.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MapsEntry {
    pub start: u64,
    pub end: u64,
    pub perms: String,
    pub path: Option<String>,
}

/// Parse a `/proc/<pid>/maps` line:
/// `55d0c0a00000-55d0c0a21000 r-xp 00000000 08:01 1234  /usr/bin/foo`.
pub fn parse_maps_line(line: &str) -> Option<MapsEntry> {
    let mut parts = line
        .splitn(6, char::is_whitespace)
        .filter(|s| !s.is_empty());
    let range = parts.next()?;
    let perms = parts.next()?.to_string();
    let _offset = parts.next()?;
    let _dev = parts.next()?;
    let _inode = parts.next()?;
    let path = parts
        .next()
        .map(|p| p.trim().to_string())
        .filter(|p| !p.is_empty());
    let (s, e) = range.split_once('-')?;
    let start = u64::from_str_radix(s, 16).ok()?;
    let end = u64::from_str_radix(e, 16).ok()?;
    if end <= start || perms.len() < 4 {
        return None;
    }
    Some(MapsEntry {
        start,
        end,
        perms,
        path,
    })
}

/// Convert maps entries to regions. `[vvar]`/`[vsyscall]` are marked
/// unreadable because reading them via `/proc/<pid>/mem` fails.
pub fn regions_from_maps(entries: &[MapsEntry]) -> Vec<MemoryRegion> {
    entries
        .iter()
        .map(|e| {
            let special = matches!(
                e.path.as_deref(),
                Some("[vvar]" | "[vsyscall]" | "[vvar_vclock]")
            );
            let file_backed = e.path.as_deref().is_some_and(|p| p.starts_with('/'));
            MemoryRegion {
                base: e.start,
                size: e.end - e.start,
                readable: e.perms.as_bytes()[0] == b'r' && !special,
                writable: e.perms.as_bytes()[1] == b'w',
                executable: e.perms.as_bytes()[2] == b'x',
                kind: if file_backed { "image" } else { "private" }.to_string(),
            }
        })
        .collect()
}

/// Group file-backed mappings into modules: base = lowest mapping, size spans
/// to the end of the highest mapping of the same file. Order follows first
/// appearance; `main_exe` (if present) is moved to the front.
pub fn modules_from_maps(entries: &[MapsEntry], main_exe: Option<&str>) -> Vec<ModuleInfo> {
    let mut modules: Vec<ModuleInfo> = Vec::new();
    for e in entries {
        let Some(path) = e.path.as_deref().filter(|p| p.starts_with('/')) else {
            continue;
        };
        let path = path.trim_end_matches(" (deleted)");
        if let Some(m) = modules.iter_mut().find(|m| m.path.as_deref() == Some(path)) {
            let end = m.end().max(e.end);
            m.base_address = m.base_address.min(e.start);
            m.size = end - m.base_address;
        } else {
            let name = Path::new(path)
                .file_name()
                .map(|n| n.to_string_lossy().into_owned())
                .unwrap_or_else(|| path.to_string());
            modules.push(ModuleInfo {
                name,
                base_address: e.start,
                size: e.end - e.start,
                path: Some(path.to_string()),
            });
        }
    }
    if let Some(exe) = main_exe
        && let Some(idx) = modules.iter().position(|m| m.path.as_deref() == Some(exe))
    {
        let m = modules.remove(idx);
        modules.insert(0, m);
    }
    modules
}

impl LinuxProcess {
    fn maps(&self) -> Result<Vec<MapsEntry>, ExplorerError> {
        let text = std::fs::read_to_string(format!("/proc/{}/maps", self.pid)).map_err(|e| {
            if self.is_alive() {
                ExplorerError::OpenProcess(format!("cannot read /proc/{}/maps: {}", self.pid, e))
            } else {
                ExplorerError::ProcessExited(self.pid)
            }
        })?;
        Ok(text.lines().filter_map(parse_maps_line).collect())
    }
}

impl ProcessMemory for LinuxProcess {
    fn pid(&self) -> u32 {
        self.pid
    }

    fn is_32bit(&self) -> bool {
        self.is_32bit
    }

    fn is_alive(&self) -> bool {
        Path::new(&format!("/proc/{}/mem", self.pid)).exists()
    }

    fn read(&self, address: u64, buf: &mut [u8]) -> Result<usize, ExplorerError> {
        let mut done = 0usize;
        while done < buf.len() {
            match self
                .mem
                .read_at(&mut buf[done..], address.wrapping_add(done as u64))
            {
                Ok(0) => break,
                Ok(n) => done += n,
                Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                Err(e) => {
                    if done > 0 {
                        break;
                    }
                    return Err(ExplorerError::Read {
                        address,
                        reason: e.to_string(),
                    });
                },
            }
        }
        if done == 0 && !buf.is_empty() {
            return Err(ExplorerError::Read {
                address,
                reason: "no bytes readable".into(),
            });
        }
        Ok(done)
    }

    fn regions(&self) -> Result<Vec<MemoryRegion>, ExplorerError> {
        Ok(regions_from_maps(&self.maps()?))
    }

    fn modules(&self) -> Result<Vec<ModuleInfo>, ExplorerError> {
        let exe = std::fs::read_link(format!("/proc/{}/exe", self.pid))
            .ok()
            .map(|p| p.to_string_lossy().into_owned());
        Ok(modules_from_maps(&self.maps()?, exe.as_deref()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const MAPS: &str = "\
55d0c0a00000-55d0c0a21000 r--p 00000000 08:01 1234                       /usr/bin/game
55d0c0a21000-55d0c0b00000 r-xp 00021000 08:01 1234                       /usr/bin/game
7f0000000000-7f0000100000 rw-p 00000000 00:00 0                          [heap]
7f1000000000-7f1000010000 r-xp 00000000 08:01 99                         /usr/lib/libc.so.6
7ffd00000000-7ffd00002000 r--p 00000000 00:00 0                          [vvar]
7ffe00000000-7ffe00001000 rw-p 00000000 00:00 0
garbage line
";

    #[test]
    fn parses_maps() {
        let entries: Vec<_> = MAPS.lines().filter_map(parse_maps_line).collect();
        assert_eq!(entries.len(), 6);
        assert_eq!(entries[0].path.as_deref(), Some("/usr/bin/game"));
        assert_eq!(entries[5].path, None);

        let regions = regions_from_maps(&entries);
        assert!(regions[2].writable && regions[2].readable);
        assert!(regions[1].executable);
        assert!(!regions[4].readable, "[vvar] must be skipped");

        let modules = modules_from_maps(&entries, Some("/usr/lib/libc.so.6"));
        assert_eq!(modules.len(), 2);
        assert_eq!(modules[0].name, "libc.so.6");
        assert_eq!(modules[1].name, "game");
        assert_eq!(modules[1].base_address, 0x55d0c0a00000);
        assert_eq!(modules[1].size, 0x55d0c0b00000 - 0x55d0c0a00000);
    }
}
