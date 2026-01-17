//! Error types for pr-monitor
//!
//! All errors follow fail-closed principle with helpful guidance for users.

use thiserror::Error;

/// Main error type for pr-monitor
#[derive(Debug, Error)]
#[allow(dead_code)]
pub enum Error {
    /// PR number is required (reserved for future use)
    #[error("PR number is required")]
    MissingPrNumber,

    /// Invalid PR number (reserved for future use)
    #[error("Invalid PR number: {0}")]
    InvalidPrNumber(String),

    /// Failed to execute gh command
    #[error("Failed to execute gh command: {0}")]
    GhExecution(#[from] std::io::Error),

    /// gh command failed with non-zero exit code
    #[error("gh command failed with exit code {code}: {stderr}")]
    GhFailed { code: i32, stderr: String },

    /// Failed to parse gh output as JSON
    #[error("Failed to parse gh output as JSON: {0}")]
    JsonParse(#[from] serde_json::Error),

    /// Failed to parse timestamp
    #[error("Failed to parse timestamp '{timestamp}': {reason}")]
    TimestampParse { timestamp: String, reason: String },

    /// Failed to get commit timestamp
    #[error("Failed to get commit timestamp for {sha}: {reason}")]
    CommitLookup { sha: String, reason: String },

    /// Timeout with no relevant comments
    #[error("Timeout after {seconds} seconds with no relevant comments")]
    Timeout { seconds: u64 },

    /// Interrupted by user (Ctrl+C)
    #[error("Interrupted by user")]
    Interrupted,
}

impl Error {
    /// Returns additional help text for specific errors
    pub fn help_text(&self) -> Option<&'static str> {
        match self {
            Error::GhExecution(_) | Error::GhFailed { .. } => Some(
                "Ensure gh CLI is installed and authenticated:\n\
                   gh auth login\n\
                   gh auth status",
            ),
            Error::CommitLookup { .. } => Some(
                "The commit SHA may not exist or you may not have access.\n\
                 Verify the commit exists: git log --oneline | grep SHA",
            ),
            Error::Timeout { .. } => Some(
                "No relevant comments were detected within the timeout period.\n\
                 Increase timeout with --timeout flag or check PR manually.",
            ),
            Error::Interrupted => Some("Monitoring was interrupted by Ctrl+C."),
            _ => None,
        }
    }

    /// Exit code for this error
    pub fn exit_code(&self) -> i32 {
        match self {
            Error::Timeout { .. } => 1,
            Error::Interrupted => 130, // Standard for SIGINT
            _ => 1,
        }
    }
}

/// Result type alias for pr-monitor operations
pub type Result<T> = std::result::Result<T, Error>;
