//! Error type shared by the lab state machine and the MCP tool layer.

use bioforge_types::error::BioForgeError;
use mcp_core::MCPError;
use mcp_core::ToolResult;

/// Why a lab operation did not happen.
///
/// The split matters to MCP clients:
/// * [`LabError::Invalid`] means the request itself was malformed (bad id,
///   unknown protocol name, ...). It surfaces as a JSON-RPC
///   `InvalidParameters` error.
/// * [`LabError::Refused`] means a well-formed request was refused by the
///   safety layer, the e-stop latch, a pending human gate, or failed in the
///   hardware layer. It surfaces as a tool result with `isError: true` so the
///   model sees the reason and can adapt.
#[derive(Debug)]
pub enum LabError {
    /// Malformed request.
    Invalid(String),
    /// Well-formed request refused or failed.
    Refused(BioForgeError),
}

impl std::fmt::Display for LabError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Invalid(msg) => write!(f, "invalid request: {msg}"),
            Self::Refused(e) => write!(f, "refused: {e}"),
        }
    }
}

impl std::error::Error for LabError {}

impl From<BioForgeError> for LabError {
    fn from(e: BioForgeError) -> Self {
        Self::Refused(e)
    }
}

impl LabError {
    /// Convert into the MCP result shape described on the type.
    pub fn into_mcp(self) -> mcp_core::Result<ToolResult> {
        match self {
            Self::Invalid(msg) => Err(MCPError::InvalidParameters(msg)),
            refused @ Self::Refused(_) => Ok(ToolResult::error(refused.to_string())),
        }
    }
}

/// Shorthand for building a [`LabError::Invalid`].
pub fn invalid(msg: impl Into<String>) -> LabError {
    LabError::Invalid(msg.into())
}

/// Result alias for lab operations.
pub type LabResult<T> = std::result::Result<T, LabError>;
