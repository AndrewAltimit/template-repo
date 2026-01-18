//! Error types for board manager.

use thiserror::Error;

/// Board manager errors.
#[derive(Debug, Error)]
pub enum BoardError {
    /// Board or project not found.
    #[error("Board not found: {0}")]
    BoardNotFound(String),

    /// Issue not found.
    #[error("Issue #{0} not found")]
    IssueNotFound(u64),

    /// GraphQL API error.
    #[error("GraphQL error: {0}")]
    GraphQL(String),

    /// Rate limit exceeded.
    #[error("Rate limit exceeded, retry after {0} seconds")]
    RateLimit(u64),

    /// Configuration error.
    #[error("Configuration error: {0}")]
    Config(String),

    /// Validation error.
    #[error("Validation error: {0}")]
    Validation(String),

    /// HTTP request error.
    #[error("HTTP request failed: {0}")]
    Http(#[from] reqwest::Error),

    /// JSON parsing error.
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    /// IO error.
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// Claim conflict - issue already claimed.
    #[error("Issue #{0} is already claimed by {1}")]
    #[allow(dead_code)]
    ClaimConflict(u64, String),

    /// Invalid claim - agent doesn't hold the claim.
    #[error("Agent {0} does not hold claim on issue #{1}")]
    #[allow(dead_code)]
    InvalidClaim(String, u64),

    /// Field not found on project.
    #[error("Field '{0}' not found on project")]
    FieldNotFound(String),

    /// Invalid field value.
    #[error("Invalid value '{0}' for field '{1}'")]
    InvalidFieldValue(String, String),

    /// Authentication error.
    #[error("Authentication failed: {0}")]
    Auth(String),
}

/// Result type for board operations.
pub type Result<T> = std::result::Result<T, BoardError>;
