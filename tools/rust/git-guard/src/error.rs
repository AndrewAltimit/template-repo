//! Error types for git-guard
//!
//! All errors follow fail-closed principle: when in doubt, block the command.

use thiserror::Error;

/// Main error type for git-guard
#[derive(Debug, Error)]
pub enum Error {
    /// Real 'git' binary not found in PATH
    #[error("Real 'git' binary not found in PATH (searched: {searched_paths})")]
    GitNotFound { searched_paths: String },

    /// Failed to execute real git binary
    #[error("Failed to execute git: {0}")]
    ExecFailed(#[from] std::io::Error),

    /// Error from wrapper-common shared library
    #[error(transparent)]
    Common(#[from] wrapper_common::error::CommonError),
}

impl Error {
    /// Returns additional help text for specific errors
    pub fn help_text(&self) -> Option<&'static str> {
        match self {
            Error::GitNotFound { .. } => Some(
                "Ensure git is installed and available in your PATH.\n\
                 The git-guard wrapper needs to find the real git binary to function.",
            ),
            Error::Common(e) => e.help_text(),
            _ => None,
        }
    }
}

/// Result type alias for git-guard operations
pub type Result<T> = std::result::Result<T, Error>;
