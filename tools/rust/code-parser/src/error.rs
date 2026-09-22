//! Error types.

use thiserror::Error;

/// Errors that can occur while parsing or applying AI-generated changes.
#[derive(Error, Debug)]
#[non_exhaustive]
pub enum CodeParserError {
    /// The path is absolute, escapes the base directory, or targets a protected location.
    #[error("Path traversal attempt blocked: {0}")]
    PathTraversal(String),

    /// The filename is empty, malformed, or contains forbidden characters.
    #[error("Invalid filename: {0}")]
    InvalidFilename(String),

    /// I/O error during file operations.
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// The SEARCH / old text of an edit was not found in the target file.
    #[error("search text not found in {file}")]
    SearchNotFound {
        /// File the edit targeted.
        file: String,
    },

    /// The SEARCH / old text of an edit matches more than one location.
    #[error("search text matches {count} locations in {file}; edit is ambiguous")]
    AmbiguousEdit {
        /// File the edit targeted.
        file: String,
        /// Number of matching locations.
        count: usize,
    },

    /// A unified diff could not be parsed.
    #[error("invalid patch: {0}")]
    InvalidPatch(String),

    /// A hunk's context/removed lines could not be located in the target file.
    #[error("hunk {hunk} does not apply to {file}")]
    PatchConflict {
        /// File the patch targeted.
        file: String,
        /// 1-based hunk index.
        hunk: usize,
    },
}

/// Result type for code parser operations.
pub type Result<T> = std::result::Result<T, CodeParserError>;
