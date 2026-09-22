//! Configuration discovery.
//!
//! Search order (first existing file wins):
//!
//! 1. `/etc/wrapper-guard/.secrets.yaml` - root-owned system config used by
//!    the hardened container / host setup. Checked first so an agent cannot
//!    shadow it with a weaker `.secrets.yaml` in its working directory.
//! 2. The current directory and its ancestors, up to the git root.
//! 3. The wrapper binary's directory and its ancestors, up to a git root.
//! 4. `~/.secrets.yaml`
//! 5. `$XDG_CONFIG_HOME/gh-validator/.secrets.yaml`
//!    (default `~/.config/gh-validator/.secrets.yaml`)
//!
//! No config means fail-closed: content-posting commands are refused.

use crate::config::types::Config;
use crate::error::{Error, Result};
use std::path::{Path, PathBuf};

const CONFIG_FILENAME: &str = ".secrets.yaml";
const SYSTEM_CONFIG: &str = "/etc/wrapper-guard/.secrets.yaml";
/// Upper bound on the config size (it is parsed on every content command).
const MAX_CONFIG_BYTES: u64 = 1024 * 1024;

/// Candidate config paths in priority order.
pub fn config_search_paths() -> Vec<PathBuf> {
    let mut paths = vec![PathBuf::from(SYSTEM_CONFIG)];

    let mut search_upwards = |start: &Path| {
        for dir in start.ancestors().take(16) {
            let candidate = dir.join(CONFIG_FILENAME);
            if candidate.is_file() {
                paths.push(candidate);
                return;
            }
            if dir.join(".git").exists() {
                return;
            }
        }
    };
    if let Ok(cwd) = std::env::current_dir() {
        search_upwards(&cwd);
    }
    if let Some(exe_dir) = std::env::current_exe()
        .ok()
        .and_then(|p| p.canonicalize().ok())
        .and_then(|p| p.parent().map(Path::to_path_buf))
    {
        search_upwards(&exe_dir);
    }

    let home = std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .filter(|h| !h.is_empty())
        .map(PathBuf::from);
    if let Some(home) = &home {
        paths.push(home.join(CONFIG_FILENAME));
    }
    match std::env::var_os("XDG_CONFIG_HOME").filter(|x| !x.is_empty()) {
        Some(xdg) => paths.push(
            PathBuf::from(xdg)
                .join("gh-validator")
                .join(CONFIG_FILENAME),
        ),
        None => {
            if let Some(home) = &home {
                paths.push(
                    home.join(".config")
                        .join("gh-validator")
                        .join(CONFIG_FILENAME),
                );
            }
        },
    }
    paths
}

/// Load the first config found.
///
/// # Errors
/// [`Error::ConfigNotFound`] if none exists (fail-closed),
/// [`Error::ConfigParse`] if the chosen file is unreadable or invalid.
pub fn load_config() -> Result<Config> {
    for path in config_search_paths() {
        if path.is_file() {
            return load_config_from_path(&path);
        }
    }
    Err(Error::ConfigNotFound)
}

/// Load and parse a specific config file.
pub fn load_config_from_path(path: &Path) -> Result<Config> {
    let parse_err = |details: String| Error::ConfigParse {
        path: path.to_path_buf(),
        details,
    };
    let meta = std::fs::metadata(path).map_err(|e| parse_err(format!("cannot stat: {e}")))?;
    if meta.len() > MAX_CONFIG_BYTES {
        return Err(parse_err(format!("larger than {MAX_CONFIG_BYTES} bytes")));
    }
    let content =
        std::fs::read_to_string(path).map_err(|e| parse_err(format!("cannot read: {e}")))?;
    serde_yaml::from_str(&content).map_err(|e| parse_err(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_full_config() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(CONFIG_FILENAME);
        std::fs::write(
            &path,
            r#"
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
allowed_mentions:
  - someone
"#,
        )
        .unwrap();

        let config = load_config_from_path(&path).unwrap();
        assert_eq!(config.version, "1.0.0");
        assert_eq!(config.environment_variables.len(), 2);
        assert_eq!(config.patterns.len(), 1);
        assert!(config.auto_detection.enabled);
        assert_eq!(config.settings.minimum_secret_length, 4);
        assert_eq!(config.allowed_mentions(), vec!["someone".to_string()]);
    }

    #[test]
    fn default_allowed_mentions() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(CONFIG_FILENAME);
        std::fs::write(&path, "version: '1'\n").unwrap();
        let config = load_config_from_path(&path).unwrap();
        assert_eq!(config.allowed_mentions(), vec!["AndrewAltimit".to_string()]);
    }

    #[test]
    fn invalid_yaml_is_an_error() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(CONFIG_FILENAME);
        std::fs::write(&path, "patterns: [unterminated").unwrap();
        assert!(matches!(
            load_config_from_path(&path),
            Err(Error::ConfigParse { .. })
        ));
    }

    #[test]
    fn repository_config_parses() {
        // The real repository config must stay loadable.
        let repo_config = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../.secrets.yaml");
        if repo_config.is_file() {
            let config = load_config_from_path(&repo_config).unwrap();
            assert!(!config.patterns.is_empty());
            assert_eq!(config.compile_patterns().len(), config.patterns.len());
        }
    }

    #[test]
    fn system_config_is_searched_first() {
        assert_eq!(config_search_paths()[0], PathBuf::from(SYSTEM_CONFIG));
    }
}
