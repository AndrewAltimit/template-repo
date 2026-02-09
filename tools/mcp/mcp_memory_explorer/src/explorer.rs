//! Core memory exploration functionality.
//!
//! Windows-only: Uses Windows memory APIs for process memory access.
//! On non-Windows platforms, only process listing is available.

use crate::types::*;
use std::collections::HashMap;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ExplorerError {
    #[error("Not attached to any process. Call attach() first.")]
    NotAttached,

    #[error("Process not found: {0}")]
    ProcessNotFound(String),

    #[error("Module not found: {0}")]
    ModuleNotFound(String),

    #[error("Failed to read memory at {0:#x}: {1}")]
    ReadError(u64, String),

    #[error("Failed to open process: {0}")]
    OpenProcessError(String),

    #[error("Invalid address format: {0}")]
    InvalidAddress(String),

    #[error("Watch not found: {0}")]
    WatchNotFound(String),

    #[error("Platform not supported for this operation")]
    PlatformNotSupported,
}

/// Memory explorer for reverse engineering games.
pub struct MemoryExplorer {
    #[cfg(windows)]
    process_handle: Option<windows::Win32::Foundation::HANDLE>,
    process_id: Option<u32>,
    process_name: Option<String>,
    /// True if the target process is 32-bit (WoW64 on 64-bit Windows).
    is_32bit: bool,
    modules: HashMap<String, ModuleInfo>,
    watches: HashMap<String, WatchedAddress>,
    scan_results: Vec<ScanResult>,
}

impl MemoryExplorer {
    /// Create a new memory explorer.
    pub fn new() -> Self {
        Self {
            #[cfg(windows)]
            process_handle: None,
            process_id: None,
            process_name: None,
            is_32bit: false,
            modules: HashMap::new(),
            watches: HashMap::new(),
            scan_results: Vec::new(),
        }
    }

    /// Check if attached to a process.
    pub fn is_attached(&self) -> bool {
        self.process_id.is_some()
    }

    /// Get the attached process name.
    pub fn process_name(&self) -> Option<&str> {
        self.process_name.as_deref()
    }

    /// List running processes.
    pub fn list_processes(&self, filter: Option<&str>) -> Vec<ProcessInfo> {
        use sysinfo::System;

        let mut sys = System::new_all();
        sys.refresh_all();

        let mut processes: Vec<ProcessInfo> = sys
            .processes()
            .iter()
            .filter_map(|(pid, proc)| {
                let name = proc.name().to_string_lossy().to_string();
                if let Some(f) = filter
                    && !name.to_lowercase().contains(&f.to_lowercase())
                {
                    return None;
                }
                Some(ProcessInfo {
                    name,
                    pid: pid.as_u32(),
                })
            })
            .collect();

        processes.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));
        processes
    }

    /// Get current status.
    pub fn get_status(&self) -> ExplorerStatus {
        ExplorerStatus {
            attached: self.is_attached(),
            process: self.process_name.clone(),
            watches: self.watches.keys().cloned().collect(),
            recent_scans: self.scan_results.len(),
        }
    }

    /// Get watch labels.
    pub fn get_watch_labels(&self) -> Vec<String> {
        self.watches.keys().cloned().collect()
    }

    /// Get scan results count.
    pub fn get_scan_count(&self) -> usize {
        self.scan_results.len()
    }

    // =========================================================================
    // Windows-specific implementations
    // =========================================================================

    #[cfg(windows)]
    pub fn attach(&mut self, process_name: &str) -> Result<AttachResult, ExplorerError> {
        use windows::Win32::Foundation::{CloseHandle, HANDLE};
        use windows::Win32::System::Diagnostics::ToolHelp::{
            CreateToolhelp32Snapshot, PROCESSENTRY32W, Process32FirstW, Process32NextW,
            TH32CS_SNAPPROCESS,
        };
        use windows::Win32::System::Threading::{
            IsWow64Process, OpenProcess, PROCESS_ALL_ACCESS, PROCESS_QUERY_INFORMATION,
        };

        // Detach from current process if attached
        if self.process_handle.is_some() {
            self.detach();
        }

        // Find the process
        let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) }
            .map_err(|e| ExplorerError::OpenProcessError(e.to_string()))?;

        let mut entry = PROCESSENTRY32W {
            dwSize: std::mem::size_of::<PROCESSENTRY32W>() as u32,
            ..Default::default()
        };

        let mut found_pid: Option<u32> = None;
        let target_lower = process_name.to_lowercase();

        unsafe {
            if Process32FirstW(snapshot, &mut entry).is_ok() {
                loop {
                    let name = String::from_utf16_lossy(
                        &entry.szExeFile[..entry
                            .szExeFile
                            .iter()
                            .position(|&c| c == 0)
                            .unwrap_or(entry.szExeFile.len())],
                    );

                    if name.to_lowercase() == target_lower {
                        found_pid = Some(entry.th32ProcessID);
                        break;
                    }

                    if Process32NextW(snapshot, &mut entry).is_err() {
                        break;
                    }
                }
            }
            let _ = CloseHandle(snapshot);
        }

        let pid =
            found_pid.ok_or_else(|| ExplorerError::ProcessNotFound(process_name.to_string()))?;

        // Open the process
        let handle = unsafe { OpenProcess(PROCESS_ALL_ACCESS, false, pid) }
            .map_err(|e| ExplorerError::OpenProcessError(e.to_string()))?;

        // Detect if target process is 32-bit (WoW64)
        let mut is_wow64 = windows::Win32::Foundation::BOOL::default();
        let is_32bit = unsafe {
            if IsWow64Process(handle, &mut is_wow64).is_ok() {
                is_wow64.as_bool()
            } else {
                false // Assume 64-bit if detection fails
            }
        };

        self.process_handle = Some(handle);
        self.process_id = Some(pid);
        self.process_name = Some(process_name.to_string());
        self.is_32bit = is_32bit;

        // Refresh modules
        self.refresh_modules()?;

        let base_address = self
            .modules
            .get(&process_name.to_lowercase())
            .map(|m| m.base_address)
            .unwrap_or(0);

        Ok(AttachResult {
            attached: true,
            process_name: process_name.to_string(),
            pid,
            base_address: format!("{:#x}", base_address),
            module_count: self.modules.len(),
        })
    }

    #[cfg(windows)]
    pub fn detach(&mut self) {
        use windows::Win32::Foundation::CloseHandle;

        if let Some(handle) = self.process_handle.take() {
            unsafe {
                let _ = CloseHandle(handle);
            }
        }
        self.process_id = None;
        self.process_name = None;
        self.is_32bit = false;
        self.modules.clear();
        self.watches.clear();
    }

    #[cfg(windows)]
    fn refresh_modules(&mut self) -> Result<(), ExplorerError> {
        use windows::Win32::Foundation::CloseHandle;
        use windows::Win32::System::Diagnostics::ToolHelp::{
            CreateToolhelp32Snapshot, MODULEENTRY32W, Module32FirstW, Module32NextW,
            TH32CS_SNAPMODULE, TH32CS_SNAPMODULE32,
        };

        let pid = self.process_id.ok_or(ExplorerError::NotAttached)?;

        self.modules.clear();

        let snapshot =
            unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid) }
                .map_err(|e| ExplorerError::OpenProcessError(e.to_string()))?;

        let mut entry = MODULEENTRY32W {
            dwSize: std::mem::size_of::<MODULEENTRY32W>() as u32,
            ..Default::default()
        };

        unsafe {
            if Module32FirstW(snapshot, &mut entry).is_ok() {
                loop {
                    let name = String::from_utf16_lossy(
                        &entry.szModule[..entry
                            .szModule
                            .iter()
                            .position(|&c| c == 0)
                            .unwrap_or(entry.szModule.len())],
                    );

                    let path = String::from_utf16_lossy(
                        &entry.szExePath[..entry
                            .szExePath
                            .iter()
                            .position(|&c| c == 0)
                            .unwrap_or(entry.szExePath.len())],
                    );

                    self.modules.insert(
                        name.to_lowercase(),
                        ModuleInfo {
                            name: name.clone(),
                            base_address: entry.modBaseAddr as u64,
                            size: entry.modBaseSize as u64,
                            path: Some(path),
                        },
                    );

                    if Module32NextW(snapshot, &mut entry).is_err() {
                        break;
                    }
                }
            }
            let _ = CloseHandle(snapshot);
        }

        Ok(())
    }

    #[cfg(windows)]
    pub fn get_modules(&mut self) -> Result<Vec<ModuleInfo>, ExplorerError> {
        self.require_attached()?;
        self.refresh_modules()?;

        let mut modules: Vec<ModuleInfo> = self.modules.values().cloned().collect();
        modules.sort_by_key(|m| m.base_address);
        Ok(modules)
    }

    #[cfg(windows)]
    pub fn get_module_base(&mut self, module_name: &str) -> Result<u64, ExplorerError> {
        self.require_attached()?;

        let key = module_name.to_lowercase();
        if !self.modules.contains_key(&key) {
            self.refresh_modules()?;
        }

        self.modules
            .get(&key)
            .map(|m| m.base_address)
            .ok_or_else(|| ExplorerError::ModuleNotFound(module_name.to_string()))
    }

    #[cfg(windows)]
    pub fn read_bytes(&self, address: u64, size: usize) -> Result<Vec<u8>, ExplorerError> {
        use windows::Win32::System::Diagnostics::Debug::ReadProcessMemory;

        let handle = self.require_attached_handle()?;

        let mut buffer = vec![0u8; size];
        let mut bytes_read = 0usize;

        unsafe {
            ReadProcessMemory(
                handle,
                address as *const std::ffi::c_void,
                buffer.as_mut_ptr() as *mut std::ffi::c_void,
                size,
                Some(&mut bytes_read),
            )
            .map_err(|e| ExplorerError::ReadError(address, e.to_string()))?;
        }

        buffer.truncate(bytes_read);
        Ok(buffer)
    }

    #[cfg(windows)]
    pub fn read_i32(&self, address: u64) -> Result<i32, ExplorerError> {
        let bytes = self.read_bytes(address, 4)?;
        Ok(i32::from_le_bytes(bytes.try_into().unwrap()))
    }

    #[cfg(windows)]
    pub fn read_i64(&self, address: u64) -> Result<i64, ExplorerError> {
        let bytes = self.read_bytes(address, 8)?;
        Ok(i64::from_le_bytes(bytes.try_into().unwrap()))
    }

    #[cfg(windows)]
    pub fn read_u32(&self, address: u64) -> Result<u32, ExplorerError> {
        let bytes = self.read_bytes(address, 4)?;
        Ok(u32::from_le_bytes(bytes.try_into().unwrap()))
    }

    #[cfg(windows)]
    pub fn read_u64(&self, address: u64) -> Result<u64, ExplorerError> {
        let bytes = self.read_bytes(address, 8)?;
        Ok(u64::from_le_bytes(bytes.try_into().unwrap()))
    }

    #[cfg(windows)]
    pub fn read_f32(&self, address: u64) -> Result<f32, ExplorerError> {
        let bytes = self.read_bytes(address, 4)?;
        Ok(f32::from_le_bytes(bytes.try_into().unwrap()))
    }

    #[cfg(windows)]
    pub fn read_f64(&self, address: u64) -> Result<f64, ExplorerError> {
        let bytes = self.read_bytes(address, 8)?;
        Ok(f64::from_le_bytes(bytes.try_into().unwrap()))
    }

    #[cfg(windows)]
    pub fn read_pointer(&self, address: u64) -> Result<u64, ExplorerError> {
        if self.is_32bit {
            // 32-bit process: pointers are 4 bytes
            self.read_u32(address).map(|v| v as u64)
        } else {
            // 64-bit process: pointers are 8 bytes
            self.read_u64(address)
        }
    }

    #[cfg(windows)]
    pub fn read_string(&self, address: u64, max_length: usize) -> Result<String, ExplorerError> {
        let bytes = self.read_bytes(address, max_length)?;
        let null_pos = bytes.iter().position(|&b| b == 0).unwrap_or(bytes.len());
        Ok(String::from_utf8_lossy(&bytes[..null_pos]).to_string())
    }

    #[cfg(windows)]
    pub fn read_vector3(&self, address: u64) -> Result<Vector3, ExplorerError> {
        let bytes = self.read_bytes(address, 12)?;
        Ok(Vector3 {
            x: f32::from_le_bytes(bytes[0..4].try_into().unwrap()),
            y: f32::from_le_bytes(bytes[4..8].try_into().unwrap()),
            z: f32::from_le_bytes(bytes[8..12].try_into().unwrap()),
        })
    }

    #[cfg(windows)]
    pub fn read_vector4(&self, address: u64) -> Result<Vector4, ExplorerError> {
        let bytes = self.read_bytes(address, 16)?;
        Ok(Vector4 {
            x: f32::from_le_bytes(bytes[0..4].try_into().unwrap()),
            y: f32::from_le_bytes(bytes[4..8].try_into().unwrap()),
            z: f32::from_le_bytes(bytes[8..12].try_into().unwrap()),
            w: f32::from_le_bytes(bytes[12..16].try_into().unwrap()),
        })
    }

    #[cfg(windows)]
    pub fn read_matrix4x4(&self, address: u64) -> Result<[[f32; 4]; 4], ExplorerError> {
        let bytes = self.read_bytes(address, 64)?;
        let mut matrix = [[0f32; 4]; 4];

        for row in 0..4 {
            for col in 0..4 {
                let offset = (row * 4 + col) * 4;
                matrix[row][col] =
                    f32::from_le_bytes(bytes[offset..offset + 4].try_into().unwrap());
            }
        }

        Ok(matrix)
    }

    #[cfg(windows)]
    pub fn dump_memory(&self, address: u64, size: usize) -> Result<MemoryDump, ExplorerError> {
        let data = self.read_bytes(address, size)?;

        // Format as hex dump with ASCII
        let mut lines = Vec::new();
        for (i, chunk) in data.chunks(16).enumerate() {
            let offset = i * 16;
            let hex_part: String = chunk.iter().map(|b| format!("{:02X} ", b)).collect();
            let ascii_part: String = chunk
                .iter()
                .map(|&b| {
                    if (32..127).contains(&b) {
                        b as char
                    } else {
                        '.'
                    }
                })
                .collect();
            lines.push(format!(
                "{:016X}  {:<48}  {}",
                address + offset as u64,
                hex_part.trim_end(),
                ascii_part
            ));
        }

        Ok(MemoryDump {
            address: format!("{:#x}", address),
            size: data.len(),
            data: lines.join("\n"),
        })
    }

    #[cfg(windows)]
    pub fn scan_pattern(
        &mut self,
        pattern: &str,
        module_name: Option<&str>,
        return_multiple: bool,
        max_results: usize,
    ) -> Result<Vec<ScanResult>, ExplorerError> {
        self.require_attached()?;

        let (pattern_bytes, mask) = Self::parse_pattern(pattern)?;
        let mut results = Vec::new();

        if let Some(mod_name) = module_name {
            // Scan specific module
            let module = self
                .modules
                .get(&mod_name.to_lowercase())
                .cloned()
                .ok_or_else(|| ExplorerError::ModuleNotFound(mod_name.to_string()))?;

            let matches = self.scan_module(&pattern_bytes, &mask, &module, max_results)?;
            for addr in matches {
                results.push(ScanResult {
                    address: addr,
                    pattern: pattern.to_string(),
                    module: Some(mod_name.to_string()),
                });
                if !return_multiple {
                    break;
                }
            }
        } else {
            // Scan main module
            if let Some(proc_name) = &self.process_name.clone() {
                if let Some(module) = self.modules.get(&proc_name.to_lowercase()).cloned() {
                    let matches = self.scan_module(&pattern_bytes, &mask, &module, max_results)?;
                    for addr in matches {
                        results.push(ScanResult {
                            address: addr,
                            pattern: pattern.to_string(),
                            module: Some(proc_name.clone()),
                        });
                        if !return_multiple {
                            break;
                        }
                    }
                }
            }
        }

        self.scan_results.extend(results.clone());
        Ok(results)
    }

    #[cfg(windows)]
    fn scan_module(
        &self,
        pattern_bytes: &[u8],
        mask: &[bool],
        module: &ModuleInfo,
        max_results: usize,
    ) -> Result<Vec<u64>, ExplorerError> {
        let data = match self.read_bytes(module.base_address, module.size as usize) {
            Ok(d) => d,
            Err(_) => return Ok(Vec::new()), // Skip unreadable regions
        };

        let mut results = Vec::new();
        let pattern_len = pattern_bytes.len();

        if data.len() < pattern_len {
            return Ok(results);
        }

        for pos in 0..=(data.len() - pattern_len) {
            let mut matched = true;
            for (i, (&pb, &m)) in pattern_bytes.iter().zip(mask.iter()).enumerate() {
                if m && data[pos + i] != pb {
                    matched = false;
                    break;
                }
            }

            if matched {
                results.push(module.base_address + pos as u64);
                if results.len() >= max_results {
                    break;
                }
            }
        }

        Ok(results)
    }

    #[cfg(windows)]
    pub fn find_value(
        &mut self,
        value: f64,
        value_type: ValueType,
        module_name: Option<&str>,
        max_results: usize,
    ) -> Result<Vec<ScanResult>, ExplorerError> {
        // Convert value to bytes based on type
        let search_bytes = match value_type {
            ValueType::Int32 => (value as i32).to_le_bytes().to_vec(),
            ValueType::Int64 => (value as i64).to_le_bytes().to_vec(),
            ValueType::Uint32 => (value as u32).to_le_bytes().to_vec(),
            ValueType::Uint64 => (value as u64).to_le_bytes().to_vec(),
            ValueType::Float => (value as f32).to_le_bytes().to_vec(),
            ValueType::Double => value.to_le_bytes().to_vec(),
            _ => {
                return Err(ExplorerError::InvalidAddress(
                    "Unsupported value type for search".to_string(),
                ));
            },
        };

        // Convert to pattern string
        let pattern: String = search_bytes.iter().map(|b| format!("{:02X} ", b)).collect();

        self.scan_pattern(pattern.trim(), module_name, true, max_results)
    }

    #[cfg(windows)]
    pub fn resolve_pointer_chain(
        &self,
        base_address: u64,
        offsets: &[i64],
    ) -> Result<PointerChain, ExplorerError> {
        self.require_attached()?;

        let mut current = base_address;
        let mut values = vec![current];

        for (i, &offset) in offsets.iter().enumerate() {
            if i < offsets.len() - 1 {
                // Read pointer and add offset
                let ptr = self.read_pointer(current)?;
                current = (ptr as i64 + offset) as u64;
            } else {
                // Last offset is just added
                current = (current as i64 + offset) as u64;
            }
            values.push(current);
        }

        Ok(PointerChain {
            base_address,
            offsets: offsets.to_vec(),
            final_address: current,
            values_at_each_step: values,
        })
    }

    #[cfg(windows)]
    pub fn add_watch(
        &mut self,
        label: &str,
        address: u64,
        size: usize,
        value_type: ValueType,
    ) -> Result<WatchResult, ExplorerError> {
        self.require_attached()?;

        self.watches.insert(
            label.to_string(),
            WatchedAddress {
                address,
                size,
                label: label.to_string(),
                last_value: None,
                value_type,
            },
        );

        self.read_watch(label)
    }

    #[cfg(windows)]
    pub fn read_watch(&mut self, label: &str) -> Result<WatchResult, ExplorerError> {
        self.require_attached()?;

        let watch = self
            .watches
            .get(label)
            .ok_or_else(|| ExplorerError::WatchNotFound(label.to_string()))?
            .clone();

        let data = self.read_bytes(watch.address, watch.size)?;

        // Interpret based on type
        let value: serde_json::Value = match watch.value_type {
            ValueType::Int32 if data.len() >= 4 => {
                serde_json::json!(i32::from_le_bytes(data[0..4].try_into().unwrap()))
            },
            ValueType::Int64 if data.len() >= 8 => {
                serde_json::json!(i64::from_le_bytes(data[0..8].try_into().unwrap()))
            },
            ValueType::Uint32 if data.len() >= 4 => {
                serde_json::json!(u32::from_le_bytes(data[0..4].try_into().unwrap()))
            },
            ValueType::Uint64 if data.len() >= 8 => {
                serde_json::json!(u64::from_le_bytes(data[0..8].try_into().unwrap()))
            },
            ValueType::Float if data.len() >= 4 => {
                serde_json::json!(f32::from_le_bytes(data[0..4].try_into().unwrap()))
            },
            ValueType::Double if data.len() >= 8 => {
                serde_json::json!(f64::from_le_bytes(data[0..8].try_into().unwrap()))
            },
            ValueType::String => {
                let null_pos = data.iter().position(|&b| b == 0).unwrap_or(data.len());
                serde_json::json!(String::from_utf8_lossy(&data[..null_pos]).to_string())
            },
            _ => serde_json::json!(hex::encode(&data)),
        };

        let raw_hex = hex::encode(&data);
        let changed = self
            .watches
            .get(label)
            .and_then(|w| w.last_value.as_ref())
            .map(|lv| lv != &data)
            .unwrap_or(false);

        // Update last value
        if let Some(w) = self.watches.get_mut(label) {
            w.last_value = Some(data);
        }

        Ok(WatchResult {
            label: label.to_string(),
            address: format!("{:#x}", watch.address),
            value,
            raw_hex,
            changed,
        })
    }

    #[cfg(windows)]
    pub fn read_all_watches(&mut self) -> Result<Vec<WatchResult>, ExplorerError> {
        let labels: Vec<String> = self.watches.keys().cloned().collect();
        let mut results = Vec::new();
        for label in labels {
            if let Ok(result) = self.read_watch(&label) {
                results.push(result);
            }
        }
        Ok(results)
    }

    pub fn remove_watch(&mut self, label: &str) {
        self.watches.remove(label);
    }

    // =========================================================================
    // Helper methods
    // =========================================================================

    fn require_attached(&self) -> Result<(), ExplorerError> {
        if self.process_id.is_none() {
            return Err(ExplorerError::NotAttached);
        }
        Ok(())
    }

    #[cfg(windows)]
    fn require_attached_handle(&self) -> Result<windows::Win32::Foundation::HANDLE, ExplorerError> {
        self.process_handle.ok_or(ExplorerError::NotAttached)
    }

    fn parse_pattern(pattern: &str) -> Result<(Vec<u8>, Vec<bool>), ExplorerError> {
        let parts: Vec<&str> = pattern.split_whitespace().collect();
        let mut bytes = Vec::new();
        let mut mask = Vec::new();

        for part in parts {
            if part == "??" || part == "?" {
                bytes.push(0);
                mask.push(false); // Wildcard
            } else {
                let byte = u8::from_str_radix(part, 16).map_err(|_| {
                    ExplorerError::InvalidAddress(format!("Invalid byte: {}", part))
                })?;
                bytes.push(byte);
                mask.push(true);
            }
        }

        Ok((bytes, mask))
    }

    /// Parse an address string (hex or decimal) or module name + offset.
    pub fn parse_address(&mut self, addr: &str) -> Result<u64, ExplorerError> {
        let addr = addr.trim();

        // Check if it's a module reference like "NMS.exe+0x1234"
        if let Some((module_name, offset_str)) = addr.split_once('+') {
            let module_name = module_name.trim();
            let offset_str = offset_str.trim();

            let offset: i64 = if offset_str.starts_with("0x") || offset_str.starts_with("0X") {
                i64::from_str_radix(&offset_str[2..], 16)
                    .map_err(|_| ExplorerError::InvalidAddress(offset_str.to_string()))?
            } else {
                offset_str
                    .parse()
                    .map_err(|_| ExplorerError::InvalidAddress(offset_str.to_string()))?
            };

            let base = self.get_module_base(module_name)?;
            return Ok((base as i64 + offset) as u64);
        }

        // Check for just a module name (no hex prefix, not numeric)
        if !addr.starts_with("0x")
            && !addr.starts_with("0X")
            && addr.parse::<u64>().is_err()
            && let Ok(base) = self.get_module_base(addr)
        {
            return Ok(base);
        }

        // Parse as hex or decimal
        if addr.starts_with("0x") || addr.starts_with("0X") {
            u64::from_str_radix(&addr[2..], 16)
                .map_err(|_| ExplorerError::InvalidAddress(addr.to_string()))
        } else {
            addr.parse()
                .map_err(|_| ExplorerError::InvalidAddress(addr.to_string()))
        }
    }

    // =========================================================================
    // Non-Windows stubs
    // =========================================================================

    #[cfg(not(windows))]
    pub fn attach(&mut self, _process_name: &str) -> Result<AttachResult, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn detach(&mut self) {
        self.process_id = None;
        self.process_name = None;
        self.is_32bit = false;
        self.modules.clear();
        self.watches.clear();
    }

    #[cfg(not(windows))]
    pub fn get_modules(&mut self) -> Result<Vec<ModuleInfo>, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn get_module_base(&mut self, _module_name: &str) -> Result<u64, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_bytes(&self, _address: u64, _size: usize) -> Result<Vec<u8>, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_i32(&self, _address: u64) -> Result<i32, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_i64(&self, _address: u64) -> Result<i64, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_u32(&self, _address: u64) -> Result<u32, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_u64(&self, _address: u64) -> Result<u64, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_f32(&self, _address: u64) -> Result<f32, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_f64(&self, _address: u64) -> Result<f64, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_pointer(&self, _address: u64) -> Result<u64, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_string(&self, _address: u64, _max_length: usize) -> Result<String, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_vector3(&self, _address: u64) -> Result<Vector3, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_vector4(&self, _address: u64) -> Result<Vector4, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_matrix4x4(&self, _address: u64) -> Result<[[f32; 4]; 4], ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn dump_memory(&self, _address: u64, _size: usize) -> Result<MemoryDump, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn scan_pattern(
        &mut self,
        _pattern: &str,
        _module_name: Option<&str>,
        _return_multiple: bool,
        _max_results: usize,
    ) -> Result<Vec<ScanResult>, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn find_value(
        &mut self,
        _value: f64,
        _value_type: ValueType,
        _module_name: Option<&str>,
        _max_results: usize,
    ) -> Result<Vec<ScanResult>, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn resolve_pointer_chain(
        &self,
        _base_address: u64,
        _offsets: &[i64],
    ) -> Result<PointerChain, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn add_watch(
        &mut self,
        _label: &str,
        _address: u64,
        _size: usize,
        _value_type: ValueType,
    ) -> Result<WatchResult, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_watch(&mut self, _label: &str) -> Result<WatchResult, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }

    #[cfg(not(windows))]
    pub fn read_all_watches(&mut self) -> Result<Vec<WatchResult>, ExplorerError> {
        Err(ExplorerError::PlatformNotSupported)
    }
}

impl Default for MemoryExplorer {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for MemoryExplorer {
    fn drop(&mut self) {
        self.detach();
    }
}

// We need hex encoding for display
mod hex {
    pub fn encode(data: &[u8]) -> String {
        data.iter().map(|b| format!("{:02x}", b)).collect()
    }
}
