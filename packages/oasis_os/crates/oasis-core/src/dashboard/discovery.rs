//! Application discovery -- scanning directories for EBOOT.PBP files.
//!
//! On PSP this scans `ms0:/PSP/GAME/`, on desktop/Pi it scans a configured
//! apps directory. The scanner uses the VFS trait so it works across all
//! storage backends.

use crate::backend::Color;
use crate::error::Result;
use crate::pbp;
use crate::vfs::{EntryKind, Vfs};

/// A discovered application.
#[derive(Debug, Clone)]
pub struct AppEntry {
    /// Display title (from PBP's SFO or directory name).
    pub title: String,
    /// VFS path to the app directory.
    pub path: String,
    /// Raw ICON0.PNG bytes from PBP (may be empty).
    pub icon_png: Vec<u8>,
    /// Fallback display color when no icon is available.
    pub color: Color,
}

/// Default icon colors cycled for apps without ICON0.
const FALLBACK_COLORS: &[Color] = &[
    Color {
        r: 70,
        g: 130,
        b: 180,
        a: 255,
    },
    Color {
        r: 60,
        g: 179,
        b: 113,
        a: 255,
    },
    Color {
        r: 218,
        g: 165,
        b: 32,
        a: 255,
    },
    Color {
        r: 178,
        g: 102,
        b: 178,
        a: 255,
    },
    Color {
        r: 205,
        g: 92,
        b: 92,
        a: 255,
    },
    Color {
        r: 100,
        g: 149,
        b: 237,
        a: 255,
    },
];

/// Scan a VFS directory for applications.
///
/// Looks for subdirectories containing an `EBOOT.PBP` file. Each found PBP
/// is parsed for title and icon. Directories without a PBP are listed with
/// the directory name as the title.
///
/// `skip_self` is the directory name to exclude (the OS's own directory).
pub fn discover_apps(
    vfs: &dyn Vfs,
    scan_path: &str,
    skip_self: Option<&str>,
) -> Result<Vec<AppEntry>> {
    let entries = vfs.readdir(scan_path)?;
    let mut apps = Vec::new();
    let mut color_idx = 0;

    for entry in &entries {
        if entry.kind != EntryKind::Directory {
            continue;
        }
        if let Some(skip) = skip_self {
            if entry.name == skip {
                continue;
            }
        }

        let dir_path = if scan_path == "/" {
            format!("/{}", entry.name)
        } else {
            format!("{}/{}", scan_path, entry.name)
        };

        let eboot_path = format!("{dir_path}/EBOOT.PBP");
        let color = FALLBACK_COLORS[color_idx % FALLBACK_COLORS.len()];
        color_idx += 1;

        if vfs.exists(&eboot_path) {
            // Try to parse PBP.
            match vfs.read(&eboot_path) {
                Ok(data) => match pbp::parse_pbp(&data) {
                    Ok(info) => {
                        apps.push(AppEntry {
                            title: info.title,
                            path: dir_path,
                            icon_png: info.icon_png,
                            color,
                        });
                        continue;
                    },
                    Err(e) => {
                        log::warn!("Failed to parse PBP at {eboot_path}: {e}");
                    },
                },
                Err(e) => {
                    log::warn!("Failed to read {eboot_path}: {e}");
                },
            }
        }

        // Fallback: use directory name as title.
        apps.push(AppEntry {
            title: entry.name.clone(),
            path: dir_path,
            icon_png: Vec::new(),
            color,
        });
    }

    Ok(apps)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vfs::MemoryVfs;

    fn make_pbp_bytes(title: &str) -> Vec<u8> {
        // Build a minimal PBP with the given title (reuse the test helper
        // approach from the pbp module).
        let sfo = make_sfo(title);
        let icon0 = b"\x89PNG_icon";
        let sfo_offset: u32 = 0x28;
        let icon0_offset: u32 = sfo_offset + sfo.len() as u32;
        let icon1_offset: u32 = icon0_offset + icon0.len() as u32;
        let rest: u32 = icon1_offset;

        let mut buf = Vec::new();
        buf.extend_from_slice(b"\x00PBP");
        buf.extend_from_slice(&0x00010000u32.to_le_bytes());
        buf.extend_from_slice(&sfo_offset.to_le_bytes());
        buf.extend_from_slice(&icon0_offset.to_le_bytes());
        buf.extend_from_slice(&icon1_offset.to_le_bytes());
        buf.extend_from_slice(&rest.to_le_bytes());
        buf.extend_from_slice(&rest.to_le_bytes());
        buf.extend_from_slice(&rest.to_le_bytes());
        buf.extend_from_slice(&rest.to_le_bytes());
        buf.extend_from_slice(&rest.to_le_bytes());
        buf.extend_from_slice(&sfo);
        buf.extend_from_slice(icon0);
        buf
    }

    fn make_sfo(title: &str) -> Vec<u8> {
        let key = b"TITLE\0";
        let mut value = title.as_bytes().to_vec();
        value.push(0);
        let key_table_offset: u32 = 0x14 + 0x10;
        let data_table_offset: u32 = key_table_offset + key.len() as u32;
        let mut sfo = Vec::new();
        sfo.extend_from_slice(b"\x00PSF");
        sfo.extend_from_slice(&0x01010000u32.to_le_bytes());
        sfo.extend_from_slice(&key_table_offset.to_le_bytes());
        sfo.extend_from_slice(&data_table_offset.to_le_bytes());
        sfo.extend_from_slice(&1u32.to_le_bytes());
        sfo.extend_from_slice(&0u16.to_le_bytes());
        sfo.extend_from_slice(&0x0204u16.to_le_bytes());
        sfo.extend_from_slice(&(value.len() as u32).to_le_bytes());
        sfo.extend_from_slice(&(value.len() as u32).to_le_bytes());
        sfo.extend_from_slice(&0u32.to_le_bytes());
        sfo.extend_from_slice(key);
        sfo.extend_from_slice(&value);
        sfo
    }

    #[test]
    fn discover_with_pbp() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/apps").unwrap();
        vfs.mkdir("/apps/game1").unwrap();
        let pbp = make_pbp_bytes("Cool Game");
        vfs.write("/apps/game1/EBOOT.PBP", &pbp).unwrap();

        let apps = discover_apps(&vfs, "/apps", None).unwrap();
        assert_eq!(apps.len(), 1);
        assert_eq!(apps[0].title, "Cool Game");
        assert!(!apps[0].icon_png.is_empty());
    }

    #[test]
    fn discover_without_pbp_uses_dirname() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/apps").unwrap();
        vfs.mkdir("/apps/my_tool").unwrap();

        let apps = discover_apps(&vfs, "/apps", None).unwrap();
        assert_eq!(apps.len(), 1);
        assert_eq!(apps[0].title, "my_tool");
    }

    #[test]
    fn discover_skips_self() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/apps").unwrap();
        vfs.mkdir("/apps/OASISOS").unwrap();
        vfs.mkdir("/apps/game1").unwrap();

        let apps = discover_apps(&vfs, "/apps", Some("OASISOS")).unwrap();
        assert_eq!(apps.len(), 1);
        assert_eq!(apps[0].title, "game1");
    }

    #[test]
    fn discover_skips_files() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/apps").unwrap();
        vfs.write("/apps/readme.txt", b"not an app").unwrap();
        vfs.mkdir("/apps/real_app").unwrap();

        let apps = discover_apps(&vfs, "/apps", None).unwrap();
        assert_eq!(apps.len(), 1);
    }

    #[test]
    fn discover_empty_dir() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/apps").unwrap();
        let apps = discover_apps(&vfs, "/apps", None).unwrap();
        assert!(apps.is_empty());
    }

    #[test]
    fn fallback_colors_cycle() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/apps").unwrap();
        for i in 0..8 {
            vfs.mkdir(&format!("/apps/app{i}")).unwrap();
        }
        let apps = discover_apps(&vfs, "/apps", None).unwrap();
        assert_eq!(apps.len(), 8);
        // Colors should cycle through FALLBACK_COLORS.
        assert_eq!(apps[0].color, apps[6].color);
    }
}
