//! Pattern scanner for locating game structures by byte signatures.
//!
//! Searches the NMS.exe `.text` section for instruction patterns that
//! reference the cGcCameraManager singleton, making the injector robust
//! across game updates where the RVA may change.

use crate::log::vlog;
use windows::Win32::System::LibraryLoader::GetModuleHandleA;

/// A byte pattern entry: either a specific byte or a wildcard.
#[derive(Clone, Copy)]
enum PatternByte {
    Exact(u8),
    Wildcard,
}

/// Parse an IDA-style pattern string (e.g., "48 8B 05 ?? ?? ?? ?? 48 85 C0").
fn parse_pattern(pattern: &str) -> Vec<PatternByte> {
    pattern
        .split_whitespace()
        .map(|b| {
            if b == "??" || b == "?" {
                PatternByte::Wildcard
            } else {
                PatternByte::Exact(u8::from_str_radix(b, 16).unwrap_or(0))
            }
        })
        .collect()
}

/// Scan a memory region for a byte pattern. Returns the offset from `base` where the
/// pattern starts, or `None` if not found.
unsafe fn scan_region(base: *const u8, size: usize, pattern: &[PatternByte]) -> Option<usize> {
    if pattern.is_empty() || size < pattern.len() {
        return None;
    }

    let end = size - pattern.len();
    for i in 0..=end {
        let mut matched = true;
        for (j, pb) in pattern.iter().enumerate() {
            match pb {
                PatternByte::Exact(expected) => {
                    if *base.add(i + j) != *expected {
                        matched = false;
                        break;
                    }
                }
                PatternByte::Wildcard => {}
            }
        }
        if matched {
            return Some(i);
        }
    }
    None
}

/// Get the NMS.exe module base and size from PE headers.
unsafe fn get_module_text_section() -> Option<(*const u8, usize)> {
    let handle = GetModuleHandleA(windows::core::PCSTR::null()).ok()?;
    let base = handle.0 as *const u8;

    // Parse PE headers to find .text section
    let dos_header = base as *const u16;
    if *dos_header != 0x5A4D {
        // Not a valid MZ header
        return None;
    }

    let e_lfanew = *(base.add(0x3C) as *const u32) as usize;
    let pe_header = base.add(e_lfanew);

    // PE signature check
    if *(pe_header as *const u32) != 0x4550 {
        return None;
    }

    // Optional header starts at PE + 24
    let optional_header = pe_header.add(24);
    let size_of_code = *(optional_header.add(4) as *const u32) as usize;
    let base_of_code = *(optional_header.add(20) as *const u32) as usize;

    let text_start = base.add(base_of_code);
    Some((text_start, size_of_code))
}

/// Known patterns for cGcCameraManager singleton access.
///
/// These patterns match the x64 instruction sequence that loads the global pointer:
///   mov rax/rcx, [rip + disp32]  ; Load cGcCameraManager*
///   test rax/rcx, rax/rcx        ; Null check
///   jz/je ...                    ; Skip if null (loading screen)
///
/// The RIP-relative displacement at offset 3 resolves to the global pointer address.
const CAMERA_PATTERNS: &[(&str, usize)] = &[
    // mov rax, [rip+disp32]; test rax, rax; jz
    ("48 8B 05 ?? ?? ?? ?? 48 85 C0 0F 84", 3),
    // mov rcx, [rip+disp32]; test rcx, rcx; jz
    ("48 8B 0D ?? ?? ?? ?? 48 85 C9 0F 84", 3),
    // mov rax, [rip+disp32]; test rax, rax; je (short)
    ("48 8B 05 ?? ?? ?? ?? 48 85 C0 74", 3),
    // mov rcx, [rip+disp32]; test rcx, rcx; je (short)
    ("48 8B 0D ?? ?? ?? ?? 48 85 C9 74", 3),
];

/// Scan NMS.exe for the cGcCameraManager singleton pointer address.
///
/// Returns the absolute address of the global pointer, or None if not found.
/// The returned address, when dereferenced, gives the cGcCameraManager instance.
pub unsafe fn find_camera_manager_ptr() -> Option<usize> {
    let (text_base, text_size) = get_module_text_section()?;
    let module_base = GetModuleHandleA(windows::core::PCSTR::null()).ok()?.0 as usize;

    vlog!(
        "Pattern scan: text section at 0x{:X}, size=0x{:X}",
        text_base as usize,
        text_size
    );

    for (pattern_str, disp_offset) in CAMERA_PATTERNS {
        let pattern = parse_pattern(pattern_str);

        if let Some(match_offset) = scan_region(text_base, text_size, &pattern) {
            // Calculate the RIP-relative target address
            let instr_addr = text_base.add(match_offset) as usize;
            let disp_addr = instr_addr + disp_offset;
            let disp = *(disp_addr as *const i32);

            // RIP-relative: target = next_instruction + displacement
            // The instruction is 7 bytes (48 8B 05/0D + 4-byte disp)
            let next_instr = instr_addr + 7;
            let target = (next_instr as isize + disp as isize) as usize;

            // Validate: target should be within the module's data sections
            let rva = target.wrapping_sub(module_base);
            if rva > 0x1000 && rva < 0x10000000 {
                // Try to dereference and check for a valid vtable pointer
                let singleton_ptr = *(target as *const usize);
                if singleton_ptr != 0 {
                    let vtable = *(singleton_ptr as *const usize);
                    // Vtable should point within the module
                    let vtable_rva = vtable.wrapping_sub(module_base);
                    if vtable_rva > 0x1000 && vtable_rva < 0x10000000 {
                        vlog!(
                            "Pattern scan: found cGcCameraManager at RVA 0x{:X} (pattern match at 0x{:X})",
                            rva,
                            instr_addr - module_base
                        );
                        return Some(target);
                    }
                } else {
                    // Singleton is null (loading screen) - still valid, just not initialized yet
                    vlog!(
                        "Pattern scan: found likely cGcCameraManager at RVA 0x{:X} (singleton null, loading screen?)",
                        rva
                    );
                    return Some(target);
                }
            }
        }
    }

    vlog!("Pattern scan: no cGcCameraManager pattern matched, using fallback RVA");
    None
}
