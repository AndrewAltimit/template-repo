//! Skin loading from TOML configuration files.

use std::collections::HashMap;

use serde::Deserialize;

use crate::error::{OasisError, Result};
use crate::sdi::SdiRegistry;

/// Top-level skin manifest (`skin.toml`).
#[derive(Debug, Clone, Deserialize)]
pub struct SkinManifest {
    pub name: String,
    #[serde(default = "default_version")]
    pub version: String,
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub description: String,
    #[serde(default = "default_width")]
    pub screen_width: u32,
    #[serde(default = "default_height")]
    pub screen_height: u32,
}

fn default_version() -> String {
    "1.0".to_string()
}
fn default_width() -> u32 {
    480
}
fn default_height() -> u32 {
    272
}

/// A single SDI object definition in a layout file.
#[derive(Debug, Clone, Deserialize)]
pub struct SkinObjectDef {
    pub x: Option<i32>,
    pub y: Option<i32>,
    pub w: Option<u32>,
    pub h: Option<u32>,
    pub color: Option<String>,
    pub text: Option<String>,
    pub text_color: Option<String>,
    pub font_size: Option<u16>,
    pub alpha: Option<u8>,
    pub visible: Option<bool>,
}

/// Layout: a named collection of SDI object definitions (`layout.toml`).
#[derive(Debug, Clone, Deserialize)]
pub struct SkinLayout {
    #[serde(flatten)]
    pub objects: HashMap<String, SkinObjectDef>,
}

/// Feature gates controlling which capabilities a skin exposes.
#[derive(Debug, Clone, Deserialize)]
pub struct SkinFeatures {
    /// Whether the dashboard icon grid is shown.
    #[serde(default = "yes")]
    pub dashboard: bool,
    /// Whether the command terminal is accessible.
    #[serde(default = "yes")]
    pub terminal: bool,
    /// Whether the file browser command (ls/cd/cat) is available.
    #[serde(default = "yes")]
    pub file_browser: bool,
    /// Whether the window manager is active (for Desktop skin).
    #[serde(default)]
    pub window_manager: bool,
    /// Number of dashboard pages (for icon grid skins).
    #[serde(default = "default_pages")]
    pub dashboard_pages: u32,
    /// Icons per page (grid capacity).
    #[serde(default = "default_icons_per_page")]
    pub icons_per_page: u32,
    /// Grid columns.
    #[serde(default = "default_grid_cols")]
    pub grid_cols: u32,
    /// Grid rows.
    #[serde(default = "default_grid_rows")]
    pub grid_rows: u32,
    /// Available command categories (empty = all).
    #[serde(default)]
    pub command_categories: Vec<String>,
}

fn yes() -> bool {
    true
}
fn default_pages() -> u32 {
    3
}
fn default_icons_per_page() -> u32 {
    6
}
fn default_grid_cols() -> u32 {
    3
}
fn default_grid_rows() -> u32 {
    2
}

impl Default for SkinFeatures {
    fn default() -> Self {
        Self {
            dashboard: true,
            terminal: true,
            file_browser: true,
            window_manager: false,
            dashboard_pages: 3,
            icons_per_page: 6,
            grid_cols: 3,
            grid_rows: 2,
            command_categories: Vec::new(),
        }
    }
}

/// A fully loaded skin ready for use.
#[derive(Debug, Clone)]
pub struct Skin {
    pub manifest: SkinManifest,
    pub layout: SkinLayout,
    pub features: SkinFeatures,
}

impl Skin {
    /// Load a skin from TOML strings.
    pub fn from_toml(manifest_toml: &str, layout_toml: &str, features_toml: &str) -> Result<Self> {
        let manifest: SkinManifest = toml::from_str(manifest_toml)
            .map_err(|e| OasisError::Config(format!("skin.toml: {e}")))?;
        let layout: SkinLayout = toml::from_str(layout_toml)
            .map_err(|e| OasisError::Config(format!("layout.toml: {e}")))?;
        let features: SkinFeatures = toml::from_str(features_toml)
            .map_err(|e| OasisError::Config(format!("features.toml: {e}")))?;
        Ok(Self {
            manifest,
            layout,
            features,
        })
    }

    /// Apply this skin's layout to an SDI registry. Existing objects are
    /// updated, missing objects are created.
    pub fn apply_layout(&self, sdi: &mut SdiRegistry) {
        for (name, def) in &self.layout.objects {
            if !sdi.contains(name) {
                sdi.create(name);
            }
            if let Ok(obj) = sdi.get_mut(name) {
                if let Some(x) = def.x {
                    obj.x = x;
                }
                if let Some(y) = def.y {
                    obj.y = y;
                }
                if let Some(w) = def.w {
                    obj.w = w;
                }
                if let Some(h) = def.h {
                    obj.h = h;
                }
                if let Some(a) = def.alpha {
                    obj.alpha = a;
                }
                if let Some(v) = def.visible {
                    obj.visible = v;
                }
                if let Some(ref t) = def.text {
                    obj.text = Some(t.clone());
                }
                if let Some(fs) = def.font_size {
                    obj.font_size = fs;
                }
                // Color parsing reuses the same hex format as theme loading.
                if let Some(ref c) = def.color {
                    if let Some(parsed) = parse_hex_color(c) {
                        obj.color = parsed;
                    }
                }
                if let Some(ref c) = def.text_color {
                    if let Some(parsed) = parse_hex_color(c) {
                        obj.text_color = parsed;
                    }
                }
            }
        }
    }
}

/// Parse "#RRGGBB" or "#RRGGBBAA" into a Color.
fn parse_hex_color(s: &str) -> Option<crate::backend::Color> {
    let s = s.strip_prefix('#')?;
    if s.len() == 6 {
        let r = u8::from_str_radix(&s[0..2], 16).ok()?;
        let g = u8::from_str_radix(&s[2..4], 16).ok()?;
        let b = u8::from_str_radix(&s[4..6], 16).ok()?;
        Some(crate::backend::Color::rgb(r, g, b))
    } else if s.len() == 8 {
        let r = u8::from_str_radix(&s[0..2], 16).ok()?;
        let g = u8::from_str_radix(&s[2..4], 16).ok()?;
        let b = u8::from_str_radix(&s[4..6], 16).ok()?;
        let a = u8::from_str_radix(&s[6..8], 16).ok()?;
        Some(crate::backend::Color::rgba(r, g, b, a))
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const MANIFEST: &str = r#"
name = "classic"
version = "1.0"
author = "AndrewAltimit"
description = "PSP-style icon grid dashboard"
screen_width = 480
screen_height = 272
"#;

    const LAYOUT: &str = r##"
[status_bar]
x = 0
y = 0
w = 480
h = 24
color = "#283C5A"

[content_bg]
x = 0
y = 24
w = 480
h = 248
color = "#1A1A2D"
"##;

    const FEATURES: &str = r#"
dashboard = true
terminal = true
file_browser = true
window_manager = false
dashboard_pages = 3
icons_per_page = 6
grid_cols = 3
grid_rows = 2
"#;

    #[test]
    fn load_skin_from_toml() {
        let skin = Skin::from_toml(MANIFEST, LAYOUT, FEATURES).unwrap();
        assert_eq!(skin.manifest.name, "classic");
        assert_eq!(skin.manifest.screen_width, 480);
        assert_eq!(skin.layout.objects.len(), 2);
        assert!(skin.features.dashboard);
        assert!(!skin.features.window_manager);
        assert_eq!(skin.features.grid_cols, 3);
    }

    #[test]
    fn apply_layout_creates_objects() {
        let skin = Skin::from_toml(MANIFEST, LAYOUT, FEATURES).unwrap();
        let mut sdi = SdiRegistry::new();
        skin.apply_layout(&mut sdi);
        assert!(sdi.contains("status_bar"));
        assert!(sdi.contains("content_bg"));
        let bar = sdi.get("status_bar").unwrap();
        assert_eq!(bar.w, 480);
        assert_eq!(bar.h, 24);
    }

    #[test]
    fn apply_layout_updates_existing() {
        let skin = Skin::from_toml(MANIFEST, LAYOUT, FEATURES).unwrap();
        let mut sdi = SdiRegistry::new();
        {
            let obj = sdi.create("status_bar");
            obj.x = 999;
        }
        skin.apply_layout(&mut sdi);
        let bar = sdi.get("status_bar").unwrap();
        assert_eq!(bar.x, 0); // Updated by layout.
    }

    #[test]
    fn default_features() {
        let f = SkinFeatures::default();
        assert!(f.dashboard);
        assert!(f.terminal);
        assert_eq!(f.dashboard_pages, 3);
        assert_eq!(f.icons_per_page, 6);
    }

    #[test]
    fn manifest_defaults() {
        let toml = r#"name = "minimal""#;
        let m: SkinManifest = toml::from_str(toml).unwrap();
        assert_eq!(m.screen_width, 480);
        assert_eq!(m.screen_height, 272);
        assert_eq!(m.version, "1.0");
    }
}
