//! Error types for MCP core.

use thiserror::Error;

/// MCP-specific error types
#[derive(Error, Debug, Clone)]
pub enum MCPError {
    /// Tool not found in registry
    #[error("Tool not found: {0}")]
    ToolNotFound(String),

    /// Tool execution failed
    #[error("Tool execution failed: {0}")]
    ToolExecutionFailed(String),

    /// Invalid parameters provided to tool
    #[error("Invalid parameters: {0}")]
    InvalidParameters(String),

    /// JSON-RPC protocol error
    #[error("JSON-RPC error: {0}")]
    JsonRpcError(String),

    /// Session error
    #[error("Session error: {0}")]
    SessionError(String),

    /// Transport error
    #[error("Transport error: {0}")]
    TransportError(String),

    /// Serialization error
    #[error("Serialization error: {0}")]
    SerializationError(String),

    /// Internal server error
    #[error("Internal error: {0}")]
    Internal(String),
}

/// JSON-RPC 2.0 error codes
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JsonRpcErrorCode {
    /// Invalid JSON was received
    ParseError = -32700,
    /// The JSON sent is not a valid Request object
    InvalidRequest = -32600,
    /// The method does not exist / is not available
    MethodNotFound = -32601,
    /// Invalid method parameter(s)
    InvalidParams = -32602,
    /// Internal JSON-RPC error
    InternalError = -32603,
}

impl JsonRpcErrorCode {
    /// Get the error code value
    pub fn code(self) -> i32 {
        self as i32
    }

    /// Get the standard message for this error code
    pub fn message(self) -> &'static str {
        match self {
            Self::ParseError => "Parse error",
            Self::InvalidRequest => "Invalid Request",
            Self::MethodNotFound => "Method not found",
            Self::InvalidParams => "Invalid params",
            Self::InternalError => "Internal error",
        }
    }
}

impl From<MCPError> for JsonRpcErrorCode {
    fn from(err: MCPError) -> Self {
        match err {
            MCPError::ToolNotFound(_) => Self::MethodNotFound,
            MCPError::InvalidParameters(_) => Self::InvalidParams,
            MCPError::SerializationError(_) => Self::ParseError,
            _ => Self::InternalError,
        }
    }
}

impl From<serde_json::Error> for MCPError {
    fn from(err: serde_json::Error) -> Self {
        MCPError::SerializationError(err.to_string())
    }
}

/// Result type alias for MCP operations
pub type Result<T> = std::result::Result<T, MCPError>;
