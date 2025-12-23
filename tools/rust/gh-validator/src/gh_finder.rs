//! Find the real `gh` binary in PATH, avoiding infinite recursion
//!
//! This module handles the critical task of finding the actual GitHub CLI
//! binary while avoiding calling ourselves (which would cause infinite recursion).

use crate::error::{Error, Result};
use once_cell::sync::Lazy;
use std::path::PathBuf;

/// Platform-specific PATH separator
#[cfg(windows)]
const PATH_SEPARATOR: char = ';';

#[cfg(not(windows))]
const PATH_SEPARATOR: char = ':';

/// Platform-specific executable name
#[cfg(windows)]
const GH_BINARY_NAME: &str = "gh.exe";

#[cfg(not(windows))]
const GH_BINARY_NAME: &str = "gh";

/// Cached path to the real gh binary (stores Option to avoid cloning Error)
static REAL_GH_PATH: Lazy<Option<PathBuf>> = Lazy::new(|| find_real_gh_internal().ok());

/// Cached error message if gh was not found
static GH_SEARCH_PATHS: Lazy<String> = Lazy::new(get_search_paths);

/// Get the path to the real gh binary (cached)
pub fn find_real_gh() -> Result<PathBuf> {
    REAL_GH_PATH.clone().ok_or_else(|| Error::GhNotFound {
        searched_paths: GH_SEARCH_PATHS.clone(),
    })
}

/// Get the PATH directories that were searched
fn get_search_paths() -> String {
    let path_var = std::env::var("PATH").unwrap_or_default();
    path_var
        .split(PATH_SEPARATOR)
        .filter(|p| !p.is_empty())
        .collect::<Vec<_>>()
        .join(", ")
}

/// Internal implementation of gh binary discovery
fn find_real_gh_internal() -> Result<PathBuf> {
    // Get our own executable path (canonicalized to handle symlinks)
    let self_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.canonicalize().ok());

    // Get PATH environment variable
    let path_var = std::env::var("PATH").unwrap_or_default();
    let mut searched_paths = Vec::new();

    for path_dir in path_var.split(PATH_SEPARATOR) {
        if path_dir.is_empty() {
            continue;
        }

        let candidate = PathBuf::from(path_dir).join(GH_BINARY_NAME);
        searched_paths.push(path_dir.to_string());

        // Check if the candidate exists
        if !candidate.exists() {
            continue;
        }

        // Canonicalize to resolve symlinks
        let canonical = match candidate.canonicalize() {
            Ok(p) => p,
            Err(_) => continue,
        };

        // Skip if this is ourselves
        if let Some(ref self_canonical) = self_path {
            if &canonical == self_canonical {
                continue;
            }
        }

        // Check if it's actually executable
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if let Ok(metadata) = candidate.metadata() {
                let permissions = metadata.permissions();
                if permissions.mode() & 0o111 == 0 {
                    continue; // Not executable
                }
            }
        }

        return Ok(canonical);
    }

    Err(Error::GhNotFound {
        searched_paths: searched_paths.join(", "),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_path_separator() {
        #[cfg(windows)]
        assert_eq!(PATH_SEPARATOR, ';');

        #[cfg(not(windows))]
        assert_eq!(PATH_SEPARATOR, ':');
    }

    #[test]
    fn test_binary_name() {
        #[cfg(windows)]
        assert_eq!(GH_BINARY_NAME, "gh.exe");

        #[cfg(not(windows))]
        assert_eq!(GH_BINARY_NAME, "gh");
    }
}
