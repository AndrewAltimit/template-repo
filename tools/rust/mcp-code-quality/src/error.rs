//! Error types for the MCP Code Quality server

use serde::Serialize;
use thiserror::Error;

/// Error types that can occur during tool execution
#[derive(Debug, Error)]
pub enum ToolError {
    #[error("Path validation failed: {0}")]
    PathValidation(String),

    #[error("Rate limit exceeded for operation: {0}")]
    RateLimit(String),

    #[error("Command timed out after {0} seconds")]
    Timeout(u64),

    #[error("Tool not found: {0}")]
    ToolNotFound(String),

    #[error("Unsupported language: {0}")]
    UnsupportedLanguage(String),

    #[error("Subprocess execution failed: {0}")]
    SubprocessFailed(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Internal error: {0}")]
    Internal(String),
}

/// Serializable error response for MCP protocol
#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: bool,
    pub error_type: ErrorType,
    pub message: String,
}

/// Error type classification for programmatic handling
#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorType {
    PathValidation,
    RateLimit,
    Timeout,
    ToolNotFound,
    UnsupportedLanguage,
    SubprocessFailed,
    IoError,
    InternalError,
}

impl From<ToolError> for ErrorResponse {
    fn from(err: ToolError) -> Self {
        let (error_type, message) = match &err {
            ToolError::PathValidation(msg) => (ErrorType::PathValidation, msg.clone()),
            ToolError::RateLimit(op) => (
                ErrorType::RateLimit,
                format!("Rate limit exceeded for: {}", op),
            ),
            ToolError::Timeout(secs) => (
                ErrorType::Timeout,
                format!("Command timed out after {} seconds", secs),
            ),
            ToolError::ToolNotFound(tool) => {
                (ErrorType::ToolNotFound, format!("Tool not found: {}", tool))
            }
            ToolError::UnsupportedLanguage(lang) => (
                ErrorType::UnsupportedLanguage,
                format!("Unsupported language: {}", lang),
            ),
            ToolError::SubprocessFailed(msg) => (ErrorType::SubprocessFailed, msg.clone()),
            ToolError::Io(e) => (ErrorType::IoError, e.to_string()),
            ToolError::Internal(msg) => (ErrorType::InternalError, msg.clone()),
        };

        ErrorResponse {
            error: true,
            error_type,
            message,
        }
    }
}

pub type Result<T> = std::result::Result<T, ToolError>;
