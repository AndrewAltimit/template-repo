//! Configuration types for OASIS_OS instances.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

/// Top-level configuration for an OASIS_OS instance.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OasisConfig {
    /// Path to the skin directory to load at startup.
    pub skin_path: PathBuf,
    /// Virtual screen width in pixels.
    pub screen_width: u32,
    /// Virtual screen height in pixels.
    pub screen_height: u32,
    /// Window title (desktop only).
    pub window_title: String,
    /// Remote terminal listen port (0 = disabled).
    pub terminal_port: u16,
}

impl Default for OasisConfig {
    fn default() -> Self {
        Self {
            skin_path: PathBuf::from("skins/classic"),
            screen_width: 480,
            screen_height: 272,
            window_title: String::from("OASIS_OS"),
            terminal_port: 0,
        }
    }
}

impl OasisConfig {
    /// Load configuration from a TOML file, falling back to defaults on error.
    pub fn load(path: &Path) -> Self {
        match std::fs::read_to_string(path) {
            Ok(contents) => match toml::from_str(&contents) {
                Ok(config) => {
                    log::info!("Loaded config from {}", path.display());
                    config
                },
                Err(e) => {
                    log::warn!("Failed to parse config: {e} -- using defaults");
                    Self::default()
                },
            },
            Err(_) => {
                log::info!("No config file at {} -- using defaults", path.display());
                Self::default()
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_are_psp_resolution() {
        let cfg = OasisConfig::default();
        assert_eq!(cfg.screen_width, 480);
        assert_eq!(cfg.screen_height, 272);
    }

    #[test]
    fn load_missing_file_returns_defaults() {
        let cfg = OasisConfig::load(Path::new("/nonexistent/config.toml"));
        assert_eq!(cfg.screen_width, 480);
    }

    #[test]
    fn serde_roundtrip() {
        let cfg = OasisConfig::default();
        let toml_str = toml::to_string(&cfg).unwrap();
        let back: OasisConfig = toml::from_str(&toml_str).unwrap();
        assert_eq!(back.screen_width, cfg.screen_width);
        assert_eq!(back.screen_height, cfg.screen_height);
    }
}
