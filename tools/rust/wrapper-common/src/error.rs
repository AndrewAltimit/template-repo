//! Common error types for CLI wrappers
//!
//! All errors follow fail-closed principle: when in doubt, block the command.

use thiserror::Error;

/// Common error type shared across all wrappers
#[derive(Debug, Error)]
pub enum CommonError {
    /// Real binary not found in PATH or hardened location
    #[error("Real '{binary_name}' binary not found (searched: {searched_paths})")]
    BinaryNotFound {
        binary_name: String,
        searched_paths: String,
    },

    /// Failed to execute the real binary
    #[error("Failed to execute {binary_name}: {source}")]
    ExecFailed {
        binary_name: String,
        #[source]
        source: std::io::Error,
    },

    /// Binary integrity check failed
    #[error("Integrity check failed for {binary_name}: {details}")]
    IntegrityFailure {
        binary_name: String,
        details: String,
    },

    /// Audit logging error (non-fatal, logged to stderr)
    #[error("Audit log error: {details}")]
    AuditLogError { details: String },
}

impl CommonError {
    /// Returns additional help text for specific errors
    pub fn help_text(&self) -> Option<&'static str> {
        match self {
            CommonError::BinaryNotFound { .. } => Some(
                "Ensure the target binary is installed and available.\n\
                 If wrapper-guard setup has been run, check /usr/lib/wrapper-guard/.\n\
                 Otherwise, ensure the binary is in your PATH.",
            ),
            CommonError::IntegrityFailure { .. } => Some(
                "The wrapper binary may have been tampered with.\n\
                 Run: automation/setup/security/verify-wrapper-guard.sh\n\
                 to check the installation integrity.",
            ),
            _ => None,
        }
    }
}

/// Result type alias for common operations
pub type Result<T> = std::result::Result<T, CommonError>;
