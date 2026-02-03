//! Find real binaries in PATH or hardened locations
//!
//! This module handles the critical task of finding the actual binary
//! while avoiding calling the wrapper itself (which would cause infinite recursion).
//!
//! When wrapper-guard setup has been run, real binaries live at
//! /usr/lib/wrapper-guard/{name}.real with restricted permissions.
//! The finder checks there first before falling back to PATH scanning.

use crate::error::{CommonError, Result};
use once_cell::sync::Lazy;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;

/// Base directory for hardened (relocated) binaries
const HARDENED_BASE_DIR: &str = "/usr/lib/wrapper-guard";

/// Platform-specific PATH separator
#[cfg(windows)]
const PATH_SEPARATOR: char = ';';

#[cfg(not(windows))]
const PATH_SEPARATOR: char = ':';

/// Platform-specific executable suffix
#[cfg(windows)]
const EXE_SUFFIX: &str = ".exe";

#[cfg(not(windows))]
const EXE_SUFFIX: &str = "";

/// Cache for resolved binary paths (binary_name -> resolved_path)
static BINARY_CACHE: Lazy<Mutex<HashMap<String, PathBuf>>> =
    Lazy::new(|| Mutex::new(HashMap::new()));

/// Find the real binary, checking the hardened location first, then PATH.
///
/// The resolved path is cached after the first successful lookup.
///
/// # Arguments
/// * `binary_name` - The base name of the binary (e.g., "git", "gh")
///
/// # Returns
/// * `Ok(PathBuf)` - Canonicalized path to the real binary
/// * `Err(CommonError::BinaryNotFound)` - If no suitable binary was found
pub fn find_real_binary(binary_name: &str) -> Result<PathBuf> {
    // Check cache first
    if let Ok(cache) = BINARY_CACHE.lock() {
        if let Some(cached) = cache.get(binary_name) {
            return Ok(cached.clone());
        }
    }

    let result = find_real_binary_internal(binary_name)?;

    // Cache the result
    if let Ok(mut cache) = BINARY_CACHE.lock() {
        cache.insert(binary_name.to_string(), result.clone());
    }

    Ok(result)
}

/// Internal implementation of binary discovery
fn find_real_binary_internal(binary_name: &str) -> Result<PathBuf> {
    // 1. Check hardened location first (/usr/lib/wrapper-guard/{name}.real)
    let hardened_path =
        PathBuf::from(HARDENED_BASE_DIR).join(format!("{}{}.real", binary_name, EXE_SUFFIX));

    if hardened_path.exists() && is_executable(&hardened_path) {
        // Canonicalize to resolve any symlinks
        if let Ok(canonical) = hardened_path.canonicalize() {
            return Ok(canonical);
        }
    }

    // 2. Fall back to PATH scanning (original behavior)
    find_in_path(binary_name)
}

/// Search PATH for the real binary, skipping ourselves
fn find_in_path(binary_name: &str) -> Result<PathBuf> {
    let full_name = format!("{}{}", binary_name, EXE_SUFFIX);

    // Get our own executable path (canonicalized to handle symlinks)
    let self_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.canonicalize().ok());

    let path_var = std::env::var("PATH").unwrap_or_default();
    let mut searched_paths = Vec::new();

    for path_dir in path_var.split(PATH_SEPARATOR) {
        if path_dir.is_empty() {
            continue;
        }

        let candidate = PathBuf::from(path_dir).join(&full_name);
        searched_paths.push(path_dir.to_string());

        if !candidate.exists() {
            continue;
        }

        // Canonicalize to resolve symlinks
        let canonical = match candidate.canonicalize() {
            Ok(p) => p,
            Err(_) => continue,
        };

        // Skip if this is ourselves (avoid infinite recursion)
        if let Some(ref self_canonical) = self_path {
            if &canonical == self_canonical {
                continue;
            }
        }

        // Check if it's actually executable
        if !is_executable(&candidate) {
            continue;
        }

        return Ok(canonical);
    }

    Err(CommonError::BinaryNotFound {
        binary_name: binary_name.to_string(),
        searched_paths: searched_paths.join(", "),
    })
}

/// Check if a file is executable (Unix only; always true on Windows)
#[cfg(unix)]
fn is_executable(path: &std::path::Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    path.metadata()
        .map(|m| m.permissions().mode() & 0o111 != 0)
        .unwrap_or(false)
}

#[cfg(not(unix))]
fn is_executable(_path: &std::path::Path) -> bool {
    true
}

/// Get the PATH directories as a formatted string (for error messages)
pub fn get_search_paths() -> String {
    let path_var = std::env::var("PATH").unwrap_or_default();
    path_var
        .split(PATH_SEPARATOR)
        .filter(|p| !p.is_empty())
        .collect::<Vec<_>>()
        .join(", ")
}

/// Get the hardened base directory path
pub fn hardened_base_dir() -> &'static str {
    HARDENED_BASE_DIR
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
    fn test_exe_suffix() {
        #[cfg(windows)]
        assert_eq!(EXE_SUFFIX, ".exe");

        #[cfg(not(windows))]
        assert_eq!(EXE_SUFFIX, "");
    }

    #[test]
    fn test_hardened_base_dir() {
        assert_eq!(hardened_base_dir(), "/usr/lib/wrapper-guard");
    }

    #[test]
    fn test_get_search_paths_not_empty() {
        // PATH should be set in any test environment
        let paths = get_search_paths();
        assert!(!paths.is_empty());
    }

    #[test]
    fn test_find_nonexistent_binary() {
        let result = find_real_binary("nonexistent_binary_that_does_not_exist_12345");
        assert!(result.is_err());
        match result.unwrap_err() {
            CommonError::BinaryNotFound { binary_name, .. } => {
                assert_eq!(binary_name, "nonexistent_binary_that_does_not_exist_12345");
            },
            other => panic!("Expected BinaryNotFound, got {:?}", other),
        }
    }

    #[test]
    fn test_find_real_binary_caches() {
        // Finding the same binary twice should use the cache
        // We use "sh" as it exists on all Unix systems
        #[cfg(unix)]
        {
            let first = find_real_binary("sh");
            let second = find_real_binary("sh");
            // Both should succeed and return the same path
            if let (Ok(p1), Ok(p2)) = (first, second) {
                assert_eq!(p1, p2);
            }
        }
    }

    #[cfg(unix)]
    #[test]
    fn test_is_executable() {
        use std::os::unix::fs::PermissionsExt;

        let dir = tempfile::tempdir().unwrap();

        // Create a non-executable file
        let non_exec = dir.path().join("non_exec");
        std::fs::write(&non_exec, "#!/bin/sh").unwrap();
        std::fs::set_permissions(&non_exec, std::fs::Permissions::from_mode(0o644)).unwrap();
        assert!(!is_executable(&non_exec));

        // Create an executable file
        let exec = dir.path().join("exec");
        std::fs::write(&exec, "#!/bin/sh").unwrap();
        std::fs::set_permissions(&exec, std::fs::Permissions::from_mode(0o755)).unwrap();
        assert!(is_executable(&exec));
    }
}
