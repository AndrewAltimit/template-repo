//! Find the real `git` binary, avoiding infinite recursion
//!
//! Delegates to wrapper-common's generic binary finder which checks
//! the hardened location first, then falls back to PATH scanning.

use crate::error::{Error, Result};
use std::path::PathBuf;

/// Get the path to the real git binary (cached after first lookup)
pub fn find_real_git() -> Result<PathBuf> {
    wrapper_common::binary_finder::find_real_binary("git").map_err(|e| match e {
        wrapper_common::error::CommonError::BinaryNotFound { searched_paths, .. } => {
            Error::GitNotFound { searched_paths }
        },
        other => Error::Common(other),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_find_real_git_returns_path() {
        // git should be available in the test environment
        let result = find_real_git();
        // May fail in minimal environments, so just check it doesn't panic
        if let Ok(path) = result {
            assert!(path.exists());
        }
    }
}
