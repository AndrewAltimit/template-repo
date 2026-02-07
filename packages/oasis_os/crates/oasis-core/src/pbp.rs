//! PBP (PlayStation Portable Binary Package) parser.
//!
//! Parses the PBP container format used by PSP homebrew EBOOT.PBP files.
//! Extracts the SFO section (which contains the app title) and the ICON0
//! section (which contains the app icon as a PNG).
//!
//! # PBP Header Format
//!
//! ```text
//! Offset  Size  Description
//! 0x00    4     Magic: "\0PBP"
//! 0x04    4     Version (usually 0x00010000 or 0x00010001)
//! 0x08    4     Offset to PARAM.SFO
//! 0x0C    4     Offset to ICON0.PNG
//! 0x10    4     Offset to ICON1.PMF
//! 0x14    4     Offset to PIC0.PNG
//! 0x18    4     Offset to PIC1.PNG
//! 0x1C    4     Offset to SND0.AT3
//! 0x20    4     Offset to DATA.PSP (the actual executable)
//! 0x24    4     Offset to DATA.PSAR
//! ```
//!
//! # SFO Format (simplified)
//!
//! PARAM.SFO is a key-value store. We only need the `TITLE` key.

use crate::error::{OasisError, Result};

const PBP_MAGIC: &[u8; 4] = b"\x00PBP";
const PBP_HEADER_SIZE: usize = 0x28;

/// Parsed content from a PBP file.
#[derive(Debug, Clone)]
pub struct PbpInfo {
    /// Application title from PARAM.SFO's TITLE field.
    pub title: String,
    /// Raw ICON0.PNG bytes (may be empty if section has zero size).
    pub icon_png: Vec<u8>,
}

/// Parse a PBP file from raw bytes.
pub fn parse_pbp(data: &[u8]) -> Result<PbpInfo> {
    if data.len() < PBP_HEADER_SIZE {
        return Err(OasisError::Sdi("PBP too small for header".into()));
    }

    // Check magic.
    if &data[0..4] != PBP_MAGIC {
        return Err(OasisError::Sdi("invalid PBP magic".into()));
    }

    // Read section offsets.
    let sfo_offset = read_u32_le(data, 0x08) as usize;
    let icon0_offset = read_u32_le(data, 0x0C) as usize;
    let icon1_offset = read_u32_le(data, 0x10) as usize;

    // Extract PARAM.SFO section.
    let sfo_size = icon0_offset.saturating_sub(sfo_offset);
    let title = if sfo_size > 0 && sfo_offset + sfo_size <= data.len() {
        parse_sfo_title(&data[sfo_offset..sfo_offset + sfo_size])
            .unwrap_or_else(|| "Unknown".to_string())
    } else {
        "Unknown".to_string()
    };

    // Extract ICON0.PNG section.
    let icon0_size = icon1_offset.saturating_sub(icon0_offset);
    let icon_png = if icon0_size > 0 && icon0_offset + icon0_size <= data.len() {
        data[icon0_offset..icon0_offset + icon0_size].to_vec()
    } else {
        Vec::new()
    };

    Ok(PbpInfo { title, icon_png })
}

/// Parse a PARAM.SFO binary blob to extract the TITLE value.
///
/// SFO format:
/// - Header (0x14 bytes): magic "\0PSF", version, key_table_offset,
///   data_table_offset, entry_count
/// - Index entries (0x10 each): key_offset, data_format, data_size,
///   data_max_size, data_offset
/// - Key table (NUL-terminated strings)
/// - Data table (values)
fn parse_sfo_title(sfo: &[u8]) -> Option<String> {
    if sfo.len() < 0x14 {
        return None;
    }
    // Check SFO magic.
    if &sfo[0..4] != b"\x00PSF" {
        return None;
    }

    let key_table_offset = read_u32_le(sfo, 0x08) as usize;
    let data_table_offset = read_u32_le(sfo, 0x0C) as usize;
    let entry_count = read_u32_le(sfo, 0x10) as usize;

    let index_start = 0x14;
    for i in 0..entry_count {
        let entry_offset = index_start + i * 0x10;
        if entry_offset + 0x10 > sfo.len() {
            break;
        }

        let key_offset = read_u16_le(sfo, entry_offset) as usize;
        let data_size = read_u32_le(sfo, entry_offset + 0x08) as usize;
        let data_offset = read_u32_le(sfo, entry_offset + 0x0C) as usize;

        // Read key name.
        let key_start = key_table_offset + key_offset;
        let key = read_nul_string(sfo, key_start)?;

        if key == "TITLE" {
            let val_start = data_table_offset + data_offset;
            if val_start + data_size <= sfo.len() {
                let raw = &sfo[val_start..val_start + data_size];
                // Trim NUL bytes.
                let text = std::str::from_utf8(raw)
                    .ok()?
                    .trim_end_matches('\0')
                    .to_string();
                return Some(text);
            }
        }
    }
    None
}

fn read_u32_le(data: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes([
        data[offset],
        data[offset + 1],
        data[offset + 2],
        data[offset + 3],
    ])
}

fn read_u16_le(data: &[u8], offset: usize) -> u16 {
    u16::from_le_bytes([data[offset], data[offset + 1]])
}

fn read_nul_string(data: &[u8], start: usize) -> Option<String> {
    if start >= data.len() {
        return None;
    }
    let end = data[start..].iter().position(|&b| b == 0)?;
    std::str::from_utf8(&data[start..start + end])
        .ok()
        .map(String::from)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a minimal valid PBP with a PARAM.SFO containing TITLE="Test App"
    /// and a fake ICON0.PNG section.
    fn make_test_pbp() -> Vec<u8> {
        // Build PARAM.SFO first.
        let sfo = make_test_sfo("Test App");
        let icon0 = b"\x89PNG_fake_icon_data";

        // PBP header: 0x28 bytes.
        let sfo_offset: u32 = PBP_HEADER_SIZE as u32;
        let icon0_offset: u32 = sfo_offset + sfo.len() as u32;
        let icon1_offset: u32 = icon0_offset + icon0.len() as u32;
        // Remaining sections at same offset (zero size).
        let rest_offset: u32 = icon1_offset;

        let mut buf = Vec::new();
        // Magic.
        buf.extend_from_slice(PBP_MAGIC);
        // Version.
        buf.extend_from_slice(&0x00010000u32.to_le_bytes());
        // Offsets: SFO, ICON0, ICON1, PIC0, PIC1, SND0, DATA.PSP, DATA.PSAR.
        buf.extend_from_slice(&sfo_offset.to_le_bytes());
        buf.extend_from_slice(&icon0_offset.to_le_bytes());
        buf.extend_from_slice(&icon1_offset.to_le_bytes());
        buf.extend_from_slice(&rest_offset.to_le_bytes());
        buf.extend_from_slice(&rest_offset.to_le_bytes());
        buf.extend_from_slice(&rest_offset.to_le_bytes());
        buf.extend_from_slice(&rest_offset.to_le_bytes());
        buf.extend_from_slice(&rest_offset.to_le_bytes());
        assert_eq!(buf.len(), PBP_HEADER_SIZE);
        // Sections.
        buf.extend_from_slice(&sfo);
        buf.extend_from_slice(icon0);
        buf
    }

    /// Build a minimal PARAM.SFO with one entry: TITLE=<value>.
    fn make_test_sfo(title: &str) -> Vec<u8> {
        // We'll build a minimal SFO:
        // Header (0x14) + 1 index entry (0x10) + key table + data table.
        let key = b"TITLE\0";
        let mut value = title.as_bytes().to_vec();
        value.push(0); // NUL terminator.

        let key_table_offset: u32 = 0x14 + 0x10; // after header + 1 index.
        let data_table_offset: u32 = key_table_offset + key.len() as u32;

        let mut sfo = Vec::new();
        // Header.
        sfo.extend_from_slice(b"\x00PSF");
        sfo.extend_from_slice(&0x01010000u32.to_le_bytes()); // version.
        sfo.extend_from_slice(&key_table_offset.to_le_bytes());
        sfo.extend_from_slice(&data_table_offset.to_le_bytes());
        sfo.extend_from_slice(&1u32.to_le_bytes()); // entry_count.

        // Index entry.
        sfo.extend_from_slice(&0u16.to_le_bytes()); // key_offset.
        sfo.extend_from_slice(&0x0204u16.to_le_bytes()); // data_format (UTF-8).
        sfo.extend_from_slice(&(value.len() as u32).to_le_bytes()); // data_size.
        sfo.extend_from_slice(&(value.len() as u32).to_le_bytes()); // data_max_size.
        sfo.extend_from_slice(&0u32.to_le_bytes()); // data_offset.

        // Key table.
        sfo.extend_from_slice(key);
        // Data table.
        sfo.extend_from_slice(&value);

        sfo
    }

    #[test]
    fn parse_valid_pbp() {
        let data = make_test_pbp();
        let info = parse_pbp(&data).unwrap();
        assert_eq!(info.title, "Test App");
        assert!(!info.icon_png.is_empty());
        assert!(info.icon_png.starts_with(b"\x89PNG"));
    }

    #[test]
    fn parse_too_small() {
        assert!(parse_pbp(&[0; 10]).is_err());
    }

    #[test]
    fn parse_bad_magic() {
        let mut data = make_test_pbp();
        data[0] = 0xFF;
        assert!(parse_pbp(&data).is_err());
    }

    #[test]
    fn sfo_title_extraction() {
        let sfo = make_test_sfo("Hello World");
        let title = parse_sfo_title(&sfo).unwrap();
        assert_eq!(title, "Hello World");
    }

    #[test]
    fn sfo_empty_returns_none() {
        assert!(parse_sfo_title(&[]).is_none());
    }
}
