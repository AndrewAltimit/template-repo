//! In-memory [`ProcessMemory`] implementation for unit tests.

use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};

use super::ProcessMemory;
use crate::explorer::ExplorerError;
use crate::types::{MemoryRegion, ModuleInfo};

/// A fake process: a set of byte regions plus a module list.
pub struct MockMemory {
    regions: Mutex<Vec<(u64, Vec<u8>, bool)>>,
    modules: Vec<ModuleInfo>,
    is_32bit: bool,
    alive: AtomicBool,
    /// Emulate `ReadProcessMemory`: fail the whole read if any byte is unreadable.
    all_or_nothing: bool,
}

impl MockMemory {
    pub fn new() -> Self {
        Self {
            regions: Mutex::new(Vec::new()),
            modules: Vec::new(),
            is_32bit: false,
            alive: AtomicBool::new(true),
            all_or_nothing: true,
        }
    }

    /// Add a readable + writable region.
    pub fn with_region(self, base: u64, data: Vec<u8>) -> Self {
        self.with_region_rw(base, data, true)
    }

    /// Add a readable region, writable or not.
    pub fn with_region_rw(self, base: u64, data: Vec<u8>, writable: bool) -> Self {
        {
            let mut r = self.regions.lock().unwrap();
            r.push((base, data, writable));
            r.sort_by_key(|(b, _, _)| *b);
        }
        self
    }

    pub fn with_module(mut self, name: &str, base: u64, size: u64) -> Self {
        self.modules.push(ModuleInfo {
            name: name.to_string(),
            base_address: base,
            size,
            path: Some(format!("C:\\game\\{}", name)),
        });
        self
    }

    pub fn bits32(mut self, v: bool) -> Self {
        self.is_32bit = v;
        self
    }

    pub fn all_or_nothing(mut self, v: bool) -> Self {
        self.all_or_nothing = v;
        self
    }

    /// Overwrite bytes at `address` (must fall inside a region).
    pub fn poke(&self, address: u64, bytes: &[u8]) {
        let mut regions = self.regions.lock().unwrap();
        for (base, data, _) in regions.iter_mut() {
            if address >= *base && address + bytes.len() as u64 <= *base + data.len() as u64 {
                let off = (address - *base) as usize;
                data[off..off + bytes.len()].copy_from_slice(bytes);
                return;
            }
        }
        panic!("poke outside mock regions at {:#x}", address);
    }

    pub fn kill(&self) {
        self.alive.store(false, Ordering::SeqCst);
    }

    fn byte_at(regions: &[(u64, Vec<u8>, bool)], addr: u64) -> Option<u8> {
        regions.iter().find_map(|(base, data, _)| {
            if addr >= *base && addr < *base + data.len() as u64 {
                Some(data[(addr - base) as usize])
            } else {
                None
            }
        })
    }
}

impl ProcessMemory for MockMemory {
    fn pid(&self) -> u32 {
        4242
    }

    fn is_32bit(&self) -> bool {
        self.is_32bit
    }

    fn is_alive(&self) -> bool {
        self.alive.load(Ordering::SeqCst)
    }

    fn read(&self, address: u64, buf: &mut [u8]) -> Result<usize, ExplorerError> {
        let regions = self.regions.lock().unwrap();
        let mut n = 0;
        for (i, slot) in buf.iter_mut().enumerate() {
            match Self::byte_at(&regions, address.wrapping_add(i as u64)) {
                Some(b) => {
                    *slot = b;
                    n += 1;
                },
                None => break,
            }
        }
        if n == 0 || (self.all_or_nothing && n < buf.len()) {
            return Err(ExplorerError::Read {
                address,
                reason: "mock: unreadable".into(),
            });
        }
        Ok(n)
    }

    fn regions(&self) -> Result<Vec<MemoryRegion>, ExplorerError> {
        let regions = self.regions.lock().unwrap();
        Ok(regions
            .iter()
            .map(|(base, data, writable)| MemoryRegion {
                base: *base,
                size: data.len() as u64,
                readable: true,
                writable: *writable,
                executable: !*writable,
                kind: "private".into(),
            })
            .collect())
    }

    fn modules(&self) -> Result<Vec<ModuleInfo>, ExplorerError> {
        Ok(self.modules.clone())
    }
}

/// Share one mock between the explorer and the test (to `poke`/`kill` it
/// after attaching).
impl ProcessMemory for std::sync::Arc<MockMemory> {
    fn pid(&self) -> u32 {
        self.as_ref().pid()
    }

    fn is_32bit(&self) -> bool {
        self.as_ref().is_32bit()
    }

    fn is_alive(&self) -> bool {
        self.as_ref().is_alive()
    }

    fn read(&self, address: u64, buf: &mut [u8]) -> Result<usize, ExplorerError> {
        self.as_ref().read(address, buf)
    }

    fn regions(&self) -> Result<Vec<MemoryRegion>, ExplorerError> {
        self.as_ref().regions()
    }

    fn modules(&self) -> Result<Vec<ModuleInfo>, ExplorerError> {
        self.as_ref().modules()
    }
}
