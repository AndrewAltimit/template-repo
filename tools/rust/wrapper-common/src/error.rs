//! Common error types for CLI wrappers.
//!
//! All errors follow the fail-closed principle: when in doubt, the wrapper
//! refuses to run the command.

use thiserror::Error;

/// Error type shared by all wrappers.
#[derive(Debug, Error)]
pub enum CommonError {
    /// Real binary not found in the hardened location or PATH.
    #[error("Real '{binary_name}' binary not found (searched: {searched_paths})")]
    BinaryNotFound {
        binary_name: String,
        searched_paths: String,
    },

    /// Failed to execute the real binary.
    #[error("Failed to execute {binary_name}: {source}")]
    ExecFailed {
        binary_name: String,
        #[source]
        source: std::io::Error,
    },
}

impl CommonError {
    /// Additional, actionable help text for the error.
    pub fn help_text(&self) -> Option<&'static str> {
        match self {
            CommonError::BinaryNotFound { .. } => Some(
                "Ensure the target binary is installed.\n\
                 If wrapper-guard setup has been run, check /usr/lib/wrapper-guard/.\n\
                 Otherwise, ensure the real binary is in an absolute PATH directory\n\
                 (relative PATH entries such as '.' are ignored for safety).",
            ),
            CommonError::ExecFailed { .. } => None,
        }
    }
}

/// Result type alias for common operations.
pub type Result<T> = std::result::Result<T, CommonError>;
