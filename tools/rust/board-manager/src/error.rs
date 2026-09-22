//! Error types for board manager.

use thiserror::Error;

/// Board manager errors.
#[derive(Debug, Error)]
pub enum BoardError {
    /// Board or project not found.
    #[error("Board not found: {0}")]
    BoardNotFound(String),

    /// Issue not found (in the repository or on the board).
    #[error("Issue #{0} not found")]
    IssueNotFound(u64),

    /// Issue exists but is not an item on the configured project board.
    #[error("Issue #{0} is not on the project board (add it with `add-to-board`)")]
    NotOnBoard(u64),

    /// GraphQL API error.
    #[error("GraphQL error: {0}")]
    GraphQL(String),

    /// Non-success HTTP response that is not retryable.
    #[error("GitHub API returned HTTP {status}: {message}")]
    Api { status: u16, message: String },

    /// Rate limit exceeded and the reset is too far away to wait for.
    #[error("Rate limit exceeded, retry after {0} seconds")]
    RateLimit(u64),

    /// Configuration error.
    #[error("Configuration error: {0}")]
    Config(String),

    /// Validation error (bad user input).
    #[error("Validation error: {0}")]
    Validation(String),

    /// HTTP transport error.
    #[error("HTTP request failed: {0}")]
    Http(#[from] reqwest::Error),

    /// JSON parsing error.
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    /// IO error.
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// Field not found on project.
    #[error("Field '{0}' not found on project")]
    FieldNotFound(String),

    /// Invalid field value (e.g. single-select option missing on the board).
    #[error("Invalid value '{0}' for field '{1}'")]
    InvalidFieldValue(String, String),

    /// Authentication or authorization error.
    #[error("Authentication failed: {0}")]
    Auth(String),
}

/// Result type for board operations.
pub type Result<T> = std::result::Result<T, BoardError>;
