//! Error types for MCP core.
//!
//! [`MCPError`] is the error type returned by [`Tool::execute`](crate::tool::Tool::execute)
//! and most library APIs. How an error reaches the client depends on where it
//! happens:
//!
//! - Errors returned by a tool from `execute` are reported as a **tool
//!   execution error** (a successful JSON-RPC response whose result has
//!   `isError: true`), as the MCP specification recommends, so the model can
//!   see the message and self-correct.
//! - Protocol-level failures (malformed JSON-RPC, unknown method, unknown tool,
//!   invalid `tools/call` params) are reported as JSON-RPC error objects using
//!   the codes in [`JsonRpcErrorCode`].

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

impl MCPError {
    /// Shorthand for [`MCPError::InvalidParameters`] from anything displayable.
    ///
    /// ```
    /// use mcp_core::MCPError;
    /// let err = MCPError::invalid_params("'limit' must be positive");
    /// assert_eq!(err.to_string(), "Invalid parameters: 'limit' must be positive");
    /// ```
    pub fn invalid_params(msg: impl std::fmt::Display) -> Self {
        Self::InvalidParameters(msg.to_string())
    }

    /// Shorthand for [`MCPError::Internal`] from anything displayable.
    ///
    /// Handy as `.map_err(MCPError::internal)` on foreign error types.
    pub fn internal(msg: impl std::fmt::Display) -> Self {
        Self::Internal(msg.to_string())
    }

    /// Shorthand for [`MCPError::ToolExecutionFailed`] from anything displayable.
    pub fn execution_failed(msg: impl std::fmt::Display) -> Self {
        Self::ToolExecutionFailed(msg.to_string())
    }

    /// The JSON-RPC error code this error maps to when it is reported as a
    /// protocol-level error.
    pub fn json_rpc_code(&self) -> JsonRpcErrorCode {
        JsonRpcErrorCode::from(self)
    }
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

impl From<&MCPError> for JsonRpcErrorCode {
    fn from(err: &MCPError) -> Self {
        match err {
            // The MCP spec reports an unknown tool name in `tools/call` as
            // "Invalid params" (-32602), not "Method not found": the method
            // (`tools/call`) exists, its `name` argument is what is invalid.
            MCPError::ToolNotFound(_) | MCPError::InvalidParameters(_) => Self::InvalidParams,
            MCPError::JsonRpcError(_) => Self::InvalidRequest,
            // A server-side (de)serialization failure is an internal error; the
            // `ParseError` code is reserved for unparseable JSON from the peer.
            _ => Self::InternalError,
        }
    }
}

impl From<MCPError> for JsonRpcErrorCode {
    fn from(err: MCPError) -> Self {
        Self::from(&err)
    }
}

impl From<serde_json::Error> for MCPError {
    fn from(err: serde_json::Error) -> Self {
        MCPError::SerializationError(err.to_string())
    }
}

impl From<std::io::Error> for MCPError {
    fn from(err: std::io::Error) -> Self {
        MCPError::Internal(err.to_string())
    }
}

impl From<anyhow::Error> for MCPError {
    fn from(err: anyhow::Error) -> Self {
        // `{:#}` renders the full context chain on one line
        // ("outer: inner: root cause").
        MCPError::Internal(format!("{err:#}"))
    }
}

/// Result type alias for MCP operations
pub type Result<T> = std::result::Result<T, MCPError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tool_not_found_maps_to_invalid_params() {
        let err = MCPError::ToolNotFound("x".into());
        assert_eq!(err.json_rpc_code(), JsonRpcErrorCode::InvalidParams);
        assert_eq!(JsonRpcErrorCode::from(err).code(), -32602);
    }

    #[test]
    fn serialization_error_is_internal_not_parse_error() {
        let err = MCPError::SerializationError("bad".into());
        assert_eq!(err.json_rpc_code(), JsonRpcErrorCode::InternalError);
    }

    #[test]
    fn anyhow_context_chain_is_preserved() {
        let err = anyhow::anyhow!("root cause").context("while loading");
        let mcp: MCPError = err.into();
        assert_eq!(mcp.to_string(), "Internal error: while loading: root cause");
    }

    #[test]
    fn io_error_converts_with_question_mark() {
        fn inner() -> Result<()> {
            Err(std::io::Error::other("disk on fire"))?;
            Ok(())
        }
        assert!(inner().unwrap_err().to_string().contains("disk on fire"));
    }
}
