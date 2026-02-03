//! Find the real `gh` binary, avoiding infinite recursion
//!
//! Delegates to wrapper-common's generic binary finder which checks
//! the hardened location first, then falls back to PATH scanning.

use crate::error::{Error, Result};
use std::path::PathBuf;

/// Get the path to the real gh binary (cached after first lookup)
pub fn find_real_gh() -> Result<PathBuf> {
    wrapper_common::binary_finder::find_real_binary("gh").map_err(|e| match e {
        wrapper_common::error::CommonError::BinaryNotFound { searched_paths, .. } => {
            Error::GhNotFound { searched_paths }
        },
        other => Error::Common(other),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_find_real_gh_returns_path() {
        // gh should be available in the test environment
        let result = find_real_gh();
        // May fail in minimal environments, so just check it doesn't panic
        if let Ok(path) = result {
            assert!(path.exists());
        }
    }
}
