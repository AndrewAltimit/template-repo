//! Error types for gh-validator
//!
//! All errors follow fail-closed principle: when in doubt, block the command.

use std::path::PathBuf;
use thiserror::Error;

/// Main error type for gh-validator
#[derive(Debug, Error)]
#[allow(clippy::enum_variant_names)]
pub enum Error {
    /// Configuration file not found - blocks all commands for security
    #[error("Configuration file not found - failing closed for security")]
    ConfigNotFound,

    /// Configuration file parse error
    #[error("Failed to parse config at {path}: {details}")]
    ConfigParse { path: PathBuf, details: String },

    /// Real 'gh' binary not found in PATH
    #[error("Real 'gh' binary not found in PATH (searched: {searched_paths})")]
    GhNotFound { searched_paths: String },

    /// Secret was detected and masked
    #[error("Secret detected and masked: {pattern_name}")]
    #[allow(dead_code)]
    SecretMasked {
        pattern_name: String,
        masked_value: String,
    },

    /// Invalid reaction image URL
    #[error("Invalid URL '{url}': {reason}")]
    InvalidUrl { url: String, reason: String },

    /// Unicode emoji detected in comment
    #[error("Unicode emoji detected: {char:?} (U+{codepoint:04X})")]
    UnicodeEmoji { char: char, codepoint: u32 },

    /// Formatting violation (heredoc, echo piping, etc.)
    #[error("Formatting violation: {description}")]
    FormattingViolation { description: String },

    /// Reading comment body from stdin is blocked
    #[error("Reading comment body from stdin (--body-file -) is blocked for security")]
    StdinBlocked,

    /// Failed to read body file
    #[error("Failed to read body file '{path}': {reason}")]
    BodyFileRead { path: String, reason: String },

    /// Network error during URL validation
    #[error("Network error validating URL '{url}': {details}")]
    NetworkError { url: String, details: String },

    /// Failed to execute real gh binary
    #[error("Failed to execute gh: {0}")]
    ExecFailed(#[from] std::io::Error),

    /// Argument parsing error
    #[error("Failed to parse command arguments")]
    #[allow(dead_code)]
    ArgParse,
}

impl Error {
    /// Returns additional help text for specific errors
    pub fn help_text(&self) -> Option<&'static str> {
        match self {
            Error::ConfigNotFound => Some(
                "Please ensure .secrets.yaml exists in the repository root or current directory.",
            ),
            Error::UnicodeEmoji { .. } => Some(
                "Unicode emojis may display as corrupted characters in GitHub.\n\
                 Use ASCII alternatives:\n\
                   - Checkmark: [x] or DONE\n\
                   - X mark: [ ] or TODO\n\
                 Or use reaction images from the Media repository.",
            ),
            Error::FormattingViolation { .. } => Some(
                "Use the Write tool + --body-file pattern for reaction images:\n\
                 1. Write(\"/tmp/comment.md\", \"Your markdown with ![Reaction](url)\")\n\
                 2. Bash(\"gh pr comment PR_NUMBER --body-file /tmp/comment.md\")",
            ),
            Error::StdinBlocked => Some(
                "Cannot sanitize content read from stdin.\n\
                 Write content to a temporary file and use --body-file instead.",
            ),
            Error::InvalidUrl { .. } => Some(
                "Available reactions: https://github.com/AndrewAltimit/Media/tree/main/reaction\n\
                 Config with valid reactions: https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml",
            ),
            _ => None,
        }
    }

    /// Check if this error should block command execution
    #[allow(dead_code)]
    pub fn is_blocking(&self) -> bool {
        // All errors except SecretMasked block execution
        // SecretMasked means we modified the command but can still proceed
        !matches!(self, Error::SecretMasked { .. })
    }
}

/// Result type alias for gh-validator operations
pub type Result<T> = std::result::Result<T, Error>;
