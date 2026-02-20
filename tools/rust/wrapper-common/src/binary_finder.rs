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

/// Environment variable prefix used to detect exec() recursion between
/// multiple wrapper copies. The full variable name includes the binary name
/// (e.g., __WRAPPER_GUARD_RECURSION_GIT) so that git-guard and gh-validator
/// don't interfere with each other (gh calls git internally).
const RECURSION_GUARD_PREFIX: &str = "__WRAPPER_GUARD_RECURSION_";

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

    // 1. Check the hardened location BEFORE the recursion guard.
    //    This is critical for the two-wrapper chain:
    //      ~/.local/bin/gh (non-setgid) -> /usr/bin/gh (setgid) -> gh.real
    //    The non-setgid wrapper sets the recursion guard before exec'ing to
    //    the setgid wrapper. The setgid wrapper CAN access the hardened real
    //    binary, so it should find it here and return -- never reaching the
    //    recursion guard check or PATH scanning.
    let hardened_path =
        PathBuf::from(HARDENED_BASE_DIR).join(format!("{}{}.real", binary_name, EXE_SUFFIX));

    if hardened_path.exists() && is_executable(&hardened_path) {
        if let Ok(canonical) = hardened_path.canonicalize() {
            // Cache and return
            if let Ok(mut cache) = BINARY_CACHE.lock() {
                cache.insert(binary_name.to_string(), canonical.clone());
            }
            return Ok(canonical);
        }
    }

    // 2. Recursion guard: if the binary-specific env var is already set, we
    //    are in an exec() loop between multiple wrapper copies. The hardened
    //    path didn't work (non-setgid wrapper can't access it), so PATH
    //    scanning would just find another wrapper. Abort.
    let guard_var = format!(
        "{}{}",
        RECURSION_GUARD_PREFIX,
        binary_name.to_ascii_uppercase()
    );
    if std::env::var(&guard_var).is_ok() {
        return Err(CommonError::BinaryNotFound {
            binary_name: binary_name.to_string(),
            searched_paths: format!(
                "(recursion detected: {} already set -- \
                 multiple wrapper copies on PATH are exec'ing to each other)",
                guard_var,
            ),
        });
    }

    // 3. Fall back to PATH scanning
    let result = find_in_path(binary_name)?;

    // Cache the result
    if let Ok(mut cache) = BINARY_CACHE.lock() {
        cache.insert(binary_name.to_string(), result.clone());
    }

    Ok(result)
}

/// Set the recursion guard environment variable before exec'ing.
///
/// Call this just before `exec_binary()` so that if the resolved path
/// turns out to be another wrapper copy, it will detect the recursion
/// on the next invocation and abort instead of looping.
///
/// The variable is binary-specific (e.g., `__WRAPPER_GUARD_RECURSION_GIT`)
/// so that gh-validator setting its guard doesn't prevent git-guard from
/// running when the real `gh` binary internally calls `git`.
pub fn set_recursion_guard(binary_name: &str) {
    let var = format!(
        "{}{}",
        RECURSION_GUARD_PREFIX,
        binary_name.to_ascii_uppercase()
    );
    // SAFETY: this is called single-threaded just before exec() replaces
    // the process image, so no other threads are affected.
    unsafe {
        std::env::set_var(var, "1");
    }
}

/// Search PATH for the real binary, skipping ourselves and other wrapper copies
fn find_in_path(binary_name: &str) -> Result<PathBuf> {
    let full_name = format!("{}{}", binary_name, EXE_SUFFIX);

    // Get our own executable path (canonicalized to handle symlinks)
    let self_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.canonicalize().ok());

    // Get our own file size to detect other wrapper copies.
    // Different copies of the same wrapper binary will have the same size
    // (or very close), while the real git/gh binary will be much larger.
    let self_size = self_path
        .as_ref()
        .and_then(|p| p.metadata().ok())
        .map(|m| m.len());

    let path_var = std::env::var("PATH").unwrap_or_default();
    let mut searched_paths = Vec::new();
    let mut skipped_wrappers = Vec::new();

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

        // Skip candidates that look like another wrapper copy:
        // same file size as ourselves AND no setgid bit.
        // A setgid copy (e.g. /usr/bin/git installed by hardened setup)
        // can access the real binary via group permissions even though
        // we can't, so we must NOT skip it.
        if let Some(our_size) = self_size {
            if let Ok(meta) = canonical.metadata() {
                if meta.len() == our_size && !is_setgid(&canonical) {
                    skipped_wrappers.push(canonical.display().to_string());
                    continue;
                }
            }
        }

        return Ok(canonical);
    }

    // Build a helpful error message
    let mut detail = searched_paths.join(", ");
    if !skipped_wrappers.is_empty() {
        detail.push_str(&format!(
            " (skipped likely wrapper copies: {})",
            skipped_wrappers.join(", ")
        ));
    }

    Err(CommonError::BinaryNotFound {
        binary_name: binary_name.to_string(),
        searched_paths: detail,
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

/// Check if a file has the setgid bit set (Unix only; always false on Windows).
/// Setgid binaries run with the file's group as effective GID, which lets
/// the hardened wrapper at /usr/bin access /usr/lib/wrapper-guard/*.real.
#[cfg(unix)]
fn is_setgid(path: &std::path::Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    path.metadata()
        .map(|m| m.permissions().mode() & 0o2000 != 0)
        .unwrap_or(false)
}

#[cfg(not(unix))]
fn is_setgid(_path: &std::path::Path) -> bool {
    false
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
