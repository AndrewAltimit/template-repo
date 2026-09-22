//! Error types for gh-validator.
//!
//! All errors are fail-closed: the command is not run.

use std::path::PathBuf;
use thiserror::Error;

/// Main error type for gh-validator.
#[derive(Debug, Error)]
pub enum Error {
    /// No configuration file was found.
    #[error("Configuration file not found - failing closed for security")]
    ConfigNotFound,

    /// The configuration file is unreadable or invalid.
    #[error("Failed to parse config at {path}: {details}")]
    ConfigParse { path: PathBuf, details: String },

    /// The operation is not allowed at all.
    #[error("Blocked: {reason}")]
    Blocked {
        reason: String,
        help: Option<&'static str>,
    },

    /// Invalid reaction image URL.
    #[error("Invalid URL '{url}': {reason}")]
    InvalidUrl { url: String, reason: String },

    /// Unicode emoji detected.
    #[error("Unicode emoji detected: {char:?} (U+{codepoint:04X}) in {location}")]
    UnicodeEmoji {
        char: char,
        codepoint: u32,
        location: String,
    },

    /// Reaction image passed inline instead of via a file.
    #[error("Formatting violation: {description}")]
    FormattingViolation { description: String },

    /// Reading content from stdin cannot be validated.
    #[error("Reading content from stdin ({flag} -) is blocked for security")]
    StdinBlocked { flag: String },

    /// A content file could not be read, validated, or rewritten.
    #[error("Content file '{path}': {reason}")]
    ContentFile { path: String, reason: String },

    /// Network error while validating a URL.
    #[error("Network error validating URL '{url}': {details}")]
    NetworkError { url: String, details: String },

    /// Error from wrapper-common (binary lookup, exec).
    #[error(transparent)]
    Common(#[from] wrapper_common::error::CommonError),
}

impl Error {
    /// Emoji error for `c` found in `location`.
    pub fn emoji(c: char, location: impl Into<String>) -> Self {
        Error::UnicodeEmoji {
            char: c,
            codepoint: c as u32,
            location: location.into(),
        }
    }

    /// Additional, actionable help text.
    pub fn help_text(&self) -> Option<&'static str> {
        match self {
            Error::ConfigNotFound => Some(
                "Create .secrets.yaml in the repository root (or install\n\
                 /etc/wrapper-guard/.secrets.yaml). Commands that post content\n\
                 are refused without it.",
            ),
            Error::Blocked { help, .. } => *help,
            Error::UnicodeEmoji { .. } => Some(
                "Unicode emoji may display as corrupted characters on GitHub and are\n\
                 not allowed in agent-written content. Use ASCII instead:\n\
                   - Checkmark: [x] or DONE\n\
                   - X mark: [ ] or TODO\n\
                 or use reaction images from the Media repository.",
            ),
            Error::FormattingViolation { .. } => Some(
                "Use the Write tool + --body-file pattern for reaction images:\n\
                 1. Write(\"/tmp/comment.md\", \"Your markdown with ![Reaction](url)\")\n\
                 2. Bash(\"gh pr comment PR_NUMBER --body-file /tmp/comment.md\")",
            ),
            Error::StdinBlocked { .. } => Some(
                "Content read from stdin cannot be validated.\n\
                 Write the content to a file and pass the file path instead.",
            ),
            Error::InvalidUrl { .. } => Some(
                "Available reactions: https://github.com/AndrewAltimit/Media/tree/main/reaction\n\
                 Config with valid reactions: https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml",
            ),
            Error::Common(e) => e.help_text(),
            _ => None,
        }
    }
}

/// Result type alias for gh-validator operations.
pub type Result<T> = std::result::Result<T, Error>;
