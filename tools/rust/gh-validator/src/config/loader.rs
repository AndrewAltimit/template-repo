//! Configuration file loader
//!
//! Searches for .secrets.yaml in multiple locations and parses it.
//! Fails closed (blocks all commands) if no config is found.

use crate::config::types::Config;
use crate::error::{Error, Result};
use std::path::PathBuf;

const CONFIG_FILENAME: &str = ".secrets.yaml";

/// Get list of paths to search for configuration file
fn config_search_paths() -> Vec<PathBuf> {
    let mut paths = Vec::new();
    let mut seen = std::collections::HashSet::new();

    // Helper to add path if not already seen
    let mut add_if_new = |path: PathBuf| {
        if let Ok(canonical) = path.canonicalize() {
            if seen.insert(canonical.clone()) {
                paths.push(canonical);
            }
        } else if !seen.contains(&path) {
            seen.insert(path.clone());
            paths.push(path);
        }
    };

    // 1. Search from current working directory upward (find git root)
    if let Ok(cwd) = std::env::current_dir() {
        for ancestor in cwd.ancestors().take(10) {
            let candidate = ancestor.join(CONFIG_FILENAME);
            if candidate.exists() {
                add_if_new(candidate);
                break; // Found config, stop searching upward
            }

            // Also check if we hit a git root
            if ancestor.join(".git").exists() {
                let candidate = ancestor.join(CONFIG_FILENAME);
                add_if_new(candidate);
                break;
            }
        }
    }

    // 2. Search from binary location upward
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            for ancestor in exe_dir.ancestors().take(10) {
                let candidate = ancestor.join(CONFIG_FILENAME);
                if candidate.exists() {
                    add_if_new(candidate);
                    break;
                }

                // Check for git root
                if ancestor.join(".git").exists() {
                    let candidate = ancestor.join(CONFIG_FILENAME);
                    add_if_new(candidate);
                    break;
                }
            }
        }
    }

    // 3. Home directory config (user-wide defaults)
    if let Ok(home) = std::env::var("HOME") {
        add_if_new(PathBuf::from(home).join(CONFIG_FILENAME));
    }

    // 4. XDG config directory
    if let Ok(xdg_config) = std::env::var("XDG_CONFIG_HOME") {
        add_if_new(
            PathBuf::from(xdg_config)
                .join("gh-validator")
                .join(CONFIG_FILENAME),
        );
    } else if let Ok(home) = std::env::var("HOME") {
        add_if_new(
            PathBuf::from(home)
                .join(".config")
                .join("gh-validator")
                .join(CONFIG_FILENAME),
        );
    }

    paths
}

/// Load configuration from the first available config file
///
/// # Errors
///
/// Returns `Error::ConfigNotFound` if no config file is found (fail-closed).
/// Returns `Error::ConfigParse` if the config file is invalid.
pub fn load_config() -> Result<Config> {
    let search_paths = config_search_paths();

    for path in &search_paths {
        if !path.exists() {
            continue;
        }

        let content = std::fs::read_to_string(path).map_err(|e| Error::ConfigParse {
            path: path.clone(),
            details: format!("Failed to read file: {}", e),
        })?;

        let config: Config = serde_yaml::from_str(&content).map_err(|e| Error::ConfigParse {
            path: path.clone(),
            details: e.to_string(),
        })?;

        return Ok(config);
    }

    // FAIL CLOSED: No config = block all commands
    Err(Error::ConfigNotFound)
}

/// Load configuration from a specific path (for testing)
#[allow(dead_code)]
pub fn load_config_from_path(path: &std::path::Path) -> Result<Config> {
    let content = std::fs::read_to_string(path).map_err(|e| Error::ConfigParse {
        path: path.to_path_buf(),
        details: format!("Failed to read file: {}", e),
    })?;

    serde_yaml::from_str(&content).map_err(|e| Error::ConfigParse {
        path: path.to_path_buf(),
        details: e.to_string(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::TempDir;

    #[test]
    fn test_load_config_from_path() {
        let temp_dir = TempDir::new().unwrap();
        let config_path = temp_dir.path().join(".secrets.yaml");

        let config_content = r#"
version: "1.0.0"
environment_variables:
  - GITHUB_TOKEN
  - API_KEY
patterns:
  - name: GITHUB_TOKEN
    pattern: "ghp_[A-Za-z0-9_]{36,}"
auto_detection:
  enabled: true
  include_patterns:
    - "*_TOKEN"
  exclude_patterns:
    - "PUBLIC_*"
settings:
  minimum_secret_length: 4
"#;

        let mut file = std::fs::File::create(&config_path).unwrap();
        file.write_all(config_content.as_bytes()).unwrap();

        let config = load_config_from_path(&config_path).unwrap();

        assert_eq!(config.version, "1.0.0");
        assert_eq!(config.environment_variables.len(), 2);
        assert_eq!(config.patterns.len(), 1);
        assert!(config.auto_detection.enabled);
        assert_eq!(config.settings.minimum_secret_length, 4);
    }

    #[test]
    fn test_config_not_found() {
        // Change to a directory without config
        let temp_dir = TempDir::new().unwrap();
        let original_dir = std::env::current_dir().unwrap();
        std::env::set_current_dir(temp_dir.path()).unwrap();

        let result = load_config();
        assert!(matches!(result, Err(Error::ConfigNotFound)));

        std::env::set_current_dir(original_dir).unwrap();
    }
}
