//! Windows memory scanner implementation.

use serde::Serialize;
use std::env;
use std::mem;
use windows::Win32::Foundation::{CloseHandle, HANDLE};
use windows::Win32::System::Diagnostics::Debug::ReadProcessMemory;
use windows::Win32::System::Memory::{
    VirtualQueryEx, MEMORY_BASIC_INFORMATION, MEM_COMMIT, PAGE_EXECUTE_READ,
    PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY, PAGE_READONLY, PAGE_READWRITE,
    PAGE_PROTECTION_FLAGS, PAGE_WRITECOPY,
};
use windows::Win32::System::Threading::{OpenProcess, PROCESS_QUERY_INFORMATION, PROCESS_VM_READ};

const DEFAULT_MIN_ADDR: u64 = 0x10000;
const DEFAULT_MAX_ADDR: u64 = 0x7FFF_FFFF_FFFF;
const DEFAULT_MAX_RESULTS: usize = 50;
const MAX_REGION_SIZE: usize = 256 * 1024 * 1024; // 256 MB cap per region
const READ_CHUNK_SIZE: usize = 4 * 1024 * 1024; // 4 MB read chunks

#[derive(Serialize)]
struct ScanOutput {
    pid: u32,
    pattern: String,
    count: usize,
    results: Vec<ScanResult>,
    regions_scanned: usize,
    bytes_scanned: u64,
}

#[derive(Serialize)]
struct ScanResult {
    address: String,
}

struct PatternByte {
    value: u8,
    is_wildcard: bool,
}

struct Args {
    pid: u32,
    pattern: String,
    min_addr: u64,
    max_addr: u64,
    max_results: usize,
    output_json: bool,
}

fn parse_args() -> Result<Args, String> {
    let args: Vec<String> = env::args().collect();

    if args.len() < 3 {
        return Err(format!(
            "Usage: {} <pid> <pattern> [--min-addr <hex>] [--max-addr <hex>] [--max-results <n>]",
            args[0]
        ));
    }

    let pid: u32 = args[1].parse().map_err(|e| format!("Invalid PID: {e}"))?;
    let pattern = args[2].clone();

    let mut min_addr = DEFAULT_MIN_ADDR;
    let mut max_addr = DEFAULT_MAX_ADDR;
    let mut max_results = DEFAULT_MAX_RESULTS;
    let mut output_json = true;

    let mut i = 3;
    while i < args.len() {
        match args[i].as_str() {
            "--min-addr" => {
                i += 1;
                let s = args.get(i).ok_or("--min-addr requires a value")?;
                min_addr = parse_hex(s)?;
            }
            "--max-addr" => {
                i += 1;
                let s = args.get(i).ok_or("--max-addr requires a value")?;
                max_addr = parse_hex(s)?;
            }
            "--max-results" => {
                i += 1;
                let s = args.get(i).ok_or("--max-results requires a value")?;
                max_results = s.parse().map_err(|e| format!("Invalid max-results: {e}"))?;
            }
            "--hex" => output_json = false,
            "--json" => output_json = true,
            other => return Err(format!("Unknown option: {other}")),
        }
        i += 1;
    }

    Ok(Args {
        pid,
        pattern,
        min_addr,
        max_addr,
        max_results,
        output_json,
    })
}

fn parse_hex(s: &str) -> Result<u64, String> {
    let s = s.strip_prefix("0x").or_else(|| s.strip_prefix("0X")).unwrap_or(s);
    u64::from_str_radix(s, 16).map_err(|e| format!("Invalid hex '{s}': {e}"))
}

fn parse_pattern(pattern_str: &str) -> Result<Vec<PatternByte>, String> {
    let parts: Vec<&str> = pattern_str.split_whitespace().collect();
    if parts.is_empty() {
        return Err("Empty pattern".to_string());
    }

    let mut pattern = Vec::with_capacity(parts.len());
    for part in parts {
        if part == "??" || part == "?" {
            pattern.push(PatternByte {
                value: 0,
                is_wildcard: true,
            });
        } else {
            let value = u8::from_str_radix(part, 16)
                .map_err(|e| format!("Invalid byte '{part}': {e}"))?;
            pattern.push(PatternByte {
                value,
                is_wildcard: false,
            });
        }
    }
    Ok(pattern)
}

fn is_readable(protect: PAGE_PROTECTION_FLAGS) -> bool {
    matches!(
        protect,
        PAGE_READONLY
            | PAGE_READWRITE
            | PAGE_EXECUTE_READ
            | PAGE_EXECUTE_READWRITE
            | PAGE_WRITECOPY
            | PAGE_EXECUTE_WRITECOPY
    )
}

/// Fast pattern match - finds all occurrences of pattern in data.
/// Uses first non-wildcard byte as anchor for fast scanning.
fn find_pattern(data: &[u8], pattern: &[PatternByte], base_addr: u64, max_results: usize, results: &mut Vec<ScanResult>) {
    if pattern.is_empty() || data.len() < pattern.len() {
        return;
    }

    let pat_len = pattern.len();
    let end = data.len() - pat_len;

    // Find first non-wildcard byte for anchor
    let anchor = pattern.iter().enumerate().find(|(_, b)| !b.is_wildcard);

    if let Some((anchor_idx, anchor_byte)) = anchor {
        // Check if pattern has any wildcards at all
        let has_wildcards = pattern.iter().any(|b| b.is_wildcard);

        if !has_wildcards {
            // No wildcards - use memchr-style search for the whole pattern
            let needle: Vec<u8> = pattern.iter().map(|b| b.value).collect();
            let mut pos = 0;
            while pos <= end && results.len() < max_results {
                // Use slice search for exact patterns
                if let Some(found) = find_bytes(&data[pos..], &needle) {
                    results.push(ScanResult {
                        address: format!("0x{:X}", base_addr + (pos + found) as u64),
                    });
                    pos += found + 1;
                } else {
                    break;
                }
            }
        } else {
            // Has wildcards - anchor on first known byte
            let anchor_val = anchor_byte.value;
            let mut pos = 0;
            while pos <= end && results.len() < max_results {
                // Find next occurrence of anchor byte
                let search_start = pos + anchor_idx;
                if search_start > end {
                    break;
                }
                if let Some(found) = memchr(anchor_val, &data[search_start..=end + anchor_idx]) {
                    let candidate = search_start + found - anchor_idx;
                    if candidate + pat_len <= data.len() {
                        // Verify full pattern
                        let mut matched = true;
                        for (i, pb) in pattern.iter().enumerate() {
                            if !pb.is_wildcard && data[candidate + i] != pb.value {
                                matched = false;
                                break;
                            }
                        }
                        if matched {
                            results.push(ScanResult {
                                address: format!("0x{:X}", base_addr + candidate as u64),
                            });
                        }
                    }
                    pos = candidate + 1;
                } else {
                    break;
                }
            }
        }
    } else {
        // All wildcards - every position matches
        for i in 0..=end.min(max_results.saturating_sub(results.len())) {
            results.push(ScanResult {
                address: format!("0x{:X}", base_addr + i as u64),
            });
        }
    }
}

/// Simple memchr implementation - find first occurrence of byte in slice
#[inline]
fn memchr(needle: u8, haystack: &[u8]) -> Option<usize> {
    haystack.iter().position(|&b| b == needle)
}

/// Find a byte sequence in a larger byte slice
#[inline]
fn find_bytes(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() {
        return Some(0);
    }
    haystack.windows(needle.len()).position(|w| w == needle)
}

fn read_process_memory(handle: HANDLE, address: u64, size: usize) -> Option<Vec<u8>> {
    let mut buffer = vec![0u8; size];
    let mut bytes_read = 0usize;

    let result = unsafe {
        ReadProcessMemory(
            handle,
            address as *const std::ffi::c_void,
            buffer.as_mut_ptr() as *mut std::ffi::c_void,
            size,
            Some(&mut bytes_read),
        )
    };

    if result.is_ok() && bytes_read > 0 {
        buffer.truncate(bytes_read);
        Some(buffer)
    } else {
        None
    }
}

pub fn run() -> Result<(), String> {
    let args = parse_args()?;
    let pattern = parse_pattern(&args.pattern)?;

    // Open process
    let handle = unsafe {
        OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
            false,
            args.pid,
        )
        .map_err(|e| format!("Failed to open process {}: {e}", args.pid))?
    };

    let mut results: Vec<ScanResult> = Vec::new();
    let mut address = args.min_addr;
    let mut regions_scanned = 0u64;
    let mut bytes_scanned = 0u64;

    // Enumerate and scan memory regions
    loop {
        if address >= args.max_addr || results.len() >= args.max_results {
            break;
        }

        let mut mbi: MEMORY_BASIC_INFORMATION = unsafe { mem::zeroed() };
        let mbi_size = mem::size_of::<MEMORY_BASIC_INFORMATION>();

        let ret = unsafe {
            VirtualQueryEx(
                handle,
                Some(address as *const std::ffi::c_void),
                &mut mbi,
                mbi_size,
            )
        };

        if ret == 0 {
            break;
        }

        let region_base = mbi.BaseAddress as u64;
        let region_size = mbi.RegionSize;

        // Only scan committed, readable regions within size cap
        if mbi.State == MEM_COMMIT
            && is_readable(mbi.Protect)
            && region_size > 0
            && region_size <= MAX_REGION_SIZE
        {
            regions_scanned += 1;

            // Read in chunks to handle large regions
            let mut offset = 0;
            while offset < region_size && results.len() < args.max_results {
                let chunk_size = READ_CHUNK_SIZE.min(region_size - offset);
                // Read extra bytes to avoid missing patterns at chunk boundaries
                let overlap = if offset > 0 { pattern.len() - 1 } else { 0 };
                let read_addr = region_base + (offset as u64) - (overlap as u64);
                let read_size = chunk_size + overlap;

                if let Some(data) = read_process_memory(handle, read_addr, read_size) {
                    let search_start = overlap;
                    let search_data = &data[search_start..];
                    let search_base = region_base + offset as u64;
                    find_pattern(search_data, &pattern, search_base, args.max_results, &mut results);
                    bytes_scanned += search_data.len() as u64;
                }

                offset += chunk_size;
            }
        }

        // Advance to next region
        let next = region_base + region_size as u64;
        if next <= address {
            break; // Prevent infinite loop
        }
        address = next;
    }

    // Clean up
    unsafe { let _ = CloseHandle(handle); }

    // Output
    if args.output_json {
        let output = ScanOutput {
            pid: args.pid,
            pattern: args.pattern,
            count: results.len(),
            results,
            regions_scanned: regions_scanned as usize,
            bytes_scanned,
        };
        println!("{}", serde_json::to_string(&output).unwrap());
    } else {
        for r in &results {
            println!("{}", r.address);
        }
    }

    Ok(())
}
