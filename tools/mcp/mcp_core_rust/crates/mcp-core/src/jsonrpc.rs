//! JSON-RPC 2.0 types and MCP protocol message shapes.
//!
//! These are wire types: field names and optionality follow the JSON-RPC 2.0
//! specification and the MCP schema. Most servers never touch them directly;
//! they are produced and consumed by [`MCPHandler`](crate::transport::MCPHandler).

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::error::{JsonRpcErrorCode, MCPError};
use crate::tool::ToolAnnotations;

/// The JSON-RPC version string every message must carry.
pub const JSONRPC_VERSION: &str = "2.0";

/// The newest MCP protocol revision this library implements.
///
/// Returned from `initialize` when the client asks for a revision this server
/// does not know (per the spec, the client then decides whether to proceed).
pub const LATEST_PROTOCOL_VERSION: &str = "2025-11-25";

/// Every MCP protocol revision this library can speak, newest first.
///
/// For a tools-only server the revisions differ only in optional, additive
/// features, so the server can honour any of them: when a client requests one
/// of these, `initialize` echoes it back unchanged.
pub const SUPPORTED_PROTOCOL_VERSIONS: &[&str] =
    &["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"];

/// Pick the protocol version to answer an `initialize` request with.
///
/// Per the MCP lifecycle spec: if the server supports the requested version it
/// MUST respond with that same version, otherwise it responds with the latest
/// version it supports.
///
/// ```
/// use mcp_core::jsonrpc::{negotiate_protocol_version, LATEST_PROTOCOL_VERSION};
/// assert_eq!(negotiate_protocol_version("2024-11-05"), "2024-11-05");
/// assert_eq!(negotiate_protocol_version("1999-01-01"), LATEST_PROTOCOL_VERSION);
/// ```
pub fn negotiate_protocol_version(requested: &str) -> &'static str {
    SUPPORTED_PROTOCOL_VERSIONS
        .iter()
        .copied()
        .find(|v| *v == requested)
        .unwrap_or(LATEST_PROTOCOL_VERSION)
}

/// JSON-RPC 2.0 request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    /// JSON-RPC version (always "2.0")
    pub jsonrpc: String,
    /// Method name
    pub method: String,
    /// Method parameters
    #[serde(default)]
    pub params: Value,
    /// Request ID (None for notifications)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<Value>,
}

impl JsonRpcRequest {
    /// Create a new request
    pub fn new(method: impl Into<String>, params: Value, id: impl Into<Value>) -> Self {
        Self {
            jsonrpc: JSONRPC_VERSION.to_string(),
            method: method.into(),
            params,
            id: Some(id.into()),
        }
    }

    /// Create a notification (no response expected)
    pub fn notification(method: impl Into<String>, params: Value) -> Self {
        Self {
            jsonrpc: JSONRPC_VERSION.to_string(),
            method: method.into(),
            params,
            id: None,
        }
    }

    /// Check if this is a notification (no ID)
    pub fn is_notification(&self) -> bool {
        self.id.is_none()
    }
}

/// JSON-RPC 2.0 response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    /// JSON-RPC version (always "2.0")
    pub jsonrpc: String,
    /// Result (mutually exclusive with error)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    /// Error (mutually exclusive with result)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
    /// Request ID
    pub id: Value,
}

impl JsonRpcResponse {
    /// Create a success response
    pub fn success(id: Value, result: Value) -> Self {
        Self {
            jsonrpc: JSONRPC_VERSION.to_string(),
            result: Some(result),
            error: None,
            id,
        }
    }

    /// Create an error response
    pub fn error(id: Value, error: JsonRpcError) -> Self {
        Self {
            jsonrpc: JSONRPC_VERSION.to_string(),
            result: None,
            error: Some(error),
            id,
        }
    }

    /// Create an error response from code and message
    pub fn error_with_code(id: Value, code: JsonRpcErrorCode, data: Option<String>) -> Self {
        Self::error(
            id,
            JsonRpcError {
                code: code.code(),
                message: code.message().to_string(),
                data: data.map(Value::String),
            },
        )
    }

    /// Create an error response carrying a specific, human-readable message
    /// (rather than the generic text for `code`).
    pub fn error_with_message(
        id: Value,
        code: JsonRpcErrorCode,
        message: impl Into<String>,
    ) -> Self {
        Self::error(id, JsonRpcError::new(code.code(), message))
    }

    /// Create an error response from an [`MCPError`], using its mapped code
    /// ([`MCPError::json_rpc_code`]) and its display text as the message.
    pub fn from_mcp_error(id: Value, err: &MCPError) -> Self {
        Self::error_with_message(id, err.json_rpc_code(), err.to_string())
    }

    /// Whether this is an error response.
    pub fn is_error(&self) -> bool {
        self.error.is_some()
    }
}

/// JSON-RPC 2.0 error object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcError {
    /// Error code
    pub code: i32,
    /// Error message
    pub message: String,
    /// Additional error data
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
}

impl JsonRpcError {
    /// Create a new error
    pub fn new(code: i32, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            data: None,
        }
    }

    /// Create an error with additional data
    pub fn with_data(code: i32, message: impl Into<String>, data: Value) -> Self {
        Self {
            code,
            message: message.into(),
            data: Some(data),
        }
    }

    /// Create from error code enum
    pub fn from_code(code: JsonRpcErrorCode) -> Self {
        Self::new(code.code(), code.message())
    }

    /// Create from error code with additional data
    pub fn from_code_with_data(code: JsonRpcErrorCode, data: impl Into<String>) -> Self {
        Self::with_data(code.code(), code.message(), Value::String(data.into()))
    }
}

/// MCP Initialize request params
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InitializeParams {
    /// Protocol version requested by client
    #[serde(default = "default_protocol_version")]
    pub protocol_version: String,
    /// Client information
    #[serde(default)]
    pub client_info: Option<ClientInfoParams>,
    /// Client capabilities
    #[serde(default)]
    pub capabilities: Value,
}

impl Default for InitializeParams {
    fn default() -> Self {
        Self {
            protocol_version: default_protocol_version(),
            client_info: None,
            capabilities: Value::Object(serde_json::Map::new()),
        }
    }
}

/// The version assumed when a client omits `protocolVersion` entirely (the
/// first published revision; later clients always send the field).
fn default_protocol_version() -> String {
    "2024-11-05".to_string()
}

/// Client information in initialize request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientInfoParams {
    /// Client name
    pub name: String,
    /// Client version
    pub version: Option<String>,
}

/// MCP Initialize response result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InitializeResult {
    /// Protocol version negotiated
    pub protocol_version: String,
    /// Server information
    pub server_info: ServerInfo,
    /// Server capabilities
    pub capabilities: ServerCapabilities,
    /// Optional usage hints for the client/model (MCP `instructions`).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub instructions: Option<String>,
}

/// Server information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerInfo {
    /// Server name
    pub name: String,
    /// Server version
    pub version: String,
}

/// Server capabilities advertised in the `initialize` result.
///
/// Only capabilities that are actually implemented are serialized: `resources`
/// and `prompts` are omitted while they are `null` (the default), so clients do
/// not try to call `resources/*` or `prompts/*` methods this library does not
/// provide.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerCapabilities {
    /// Tool capabilities
    #[serde(default)]
    pub tools: ToolCapabilities,
    /// Resource capabilities (not supported; omitted from the wire when null)
    #[serde(default, skip_serializing_if = "Value::is_null")]
    pub resources: Value,
    /// Prompt capabilities (not supported; omitted from the wire when null)
    #[serde(default, skip_serializing_if = "Value::is_null")]
    pub prompts: Value,
}

impl Default for ServerCapabilities {
    fn default() -> Self {
        Self {
            tools: ToolCapabilities::default(),
            resources: Value::Null,
            prompts: Value::Null,
        }
    }
}

/// Tool capabilities
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ToolCapabilities {
    /// Whether tool list can change
    #[serde(default)]
    pub list_changed: bool,
}

/// Tools list request params
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ToolsListParams {
    /// Cursor for pagination (the full list is always returned in one page)
    pub cursor: Option<String>,
}

/// Tools list response result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolsListResult {
    /// List of available tools
    pub tools: Vec<ToolInfo>,
    /// Next cursor for pagination (always `None`: the full list fits one page)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub next_cursor: Option<String>,
}

/// Tool information in list response
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolInfo {
    /// Tool name
    pub name: String,
    /// Tool description
    pub description: String,
    /// Input schema (JSON Schema)
    pub input_schema: Value,
    /// Optional human-readable display name
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    /// Optional behavioural hints (read-only, destructive, ...)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub annotations: Option<ToolAnnotations>,
}

/// Tool call request params
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCallParams {
    /// Tool name to call
    pub name: String,
    /// Arguments to pass to the tool
    #[serde(default)]
    pub arguments: Value,
}

/// Tool call response result
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolCallResult {
    /// Content returned by the tool
    pub content: Vec<ContentBlock>,
    /// Whether the result is an error
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub is_error: bool,
}

/// Content block in tool response
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum ContentBlock {
    /// Text content
    Text {
        /// The text content
        text: String,
    },
    /// Image content
    Image {
        /// Base64 encoded image data
        data: String,
        /// MIME type
        #[serde(rename = "mimeType")]
        mime_type: String,
    },
    /// Legacy resource shape (`{"type":"resource","uri","mimeType"}`).
    ///
    /// This is not a valid MCP content block (an embedded resource nests its
    /// fields under `resource` and carries `text` or `blob`). It is kept for
    /// API compatibility only; [`crate::tool::Content::Resource`] is emitted
    /// as [`ContentBlock::ResourceLink`] instead.
    Resource {
        /// Resource URI
        uri: String,
        /// MIME type
        #[serde(rename = "mimeType")]
        mime_type: String,
    },
    /// A link to a resource the client can fetch (`resource_link`).
    #[serde(rename = "resource_link")]
    ResourceLink {
        /// Resource URI
        uri: String,
        /// Resource name (required by the MCP schema)
        name: String,
        /// MIME type
        #[serde(rename = "mimeType", skip_serializing_if = "Option::is_none")]
        mime_type: Option<String>,
    },
}

/// Params of a `notifications/progress` message.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProgressParams {
    /// Token from the originating request's `_meta.progressToken`
    pub progress_token: Value,
    /// Progress so far; must increase with each notification
    pub progress: f64,
    /// Total amount of work, if known
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total: Option<f64>,
    /// Optional human-readable progress message
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Params of a `notifications/cancelled` message.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CancelledParams {
    /// ID of the request to cancel
    pub request_id: Value,
    /// Optional reason
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_request_serialization() {
        let req = JsonRpcRequest::new("tools/list", json!({}), 1);
        let json = serde_json::to_string(&req).unwrap();
        assert!(json.contains("\"jsonrpc\":\"2.0\""));
        assert!(json.contains("\"method\":\"tools/list\""));
    }

    #[test]
    fn test_response_success() {
        let resp = JsonRpcResponse::success(json!(1), json!({"tools": []}));
        let json = serde_json::to_string(&resp).unwrap();
        assert!(json.contains("\"result\""));
        assert!(!json.contains("\"error\""));
    }

    #[test]
    fn test_response_error() {
        let resp = JsonRpcResponse::error_with_code(
            json!(1),
            JsonRpcErrorCode::MethodNotFound,
            Some("test".to_string()),
        );
        let json = serde_json::to_string(&resp).unwrap();
        assert!(json.contains("\"error\""));
        assert!(json.contains("-32601"));
    }

    #[test]
    fn test_notification() {
        let req = JsonRpcRequest::notification("initialized", json!({}));
        assert!(req.is_notification());
        let json = serde_json::to_string(&req).unwrap();
        assert!(!json.contains("\"id\""));
    }

    #[test]
    fn negotiation_echoes_supported_and_falls_back_to_latest() {
        for v in SUPPORTED_PROTOCOL_VERSIONS {
            assert_eq!(negotiate_protocol_version(v), *v);
        }
        assert_eq!(negotiate_protocol_version(""), LATEST_PROTOCOL_VERSION);
        assert_eq!(SUPPORTED_PROTOCOL_VERSIONS[0], LATEST_PROTOCOL_VERSION);
    }

    #[test]
    fn default_capabilities_only_advertise_tools() {
        let caps = serde_json::to_value(ServerCapabilities::default()).unwrap();
        assert_eq!(caps, json!({"tools": {"listChanged": false}}));
    }

    #[test]
    fn tools_list_uses_camel_case_cursor() {
        let r = ToolsListResult {
            tools: vec![],
            next_cursor: Some("c".into()),
        };
        let v = serde_json::to_value(r).unwrap();
        assert_eq!(v["nextCursor"], "c");
    }

    #[test]
    fn resource_link_serializes_per_schema() {
        let block = ContentBlock::ResourceLink {
            uri: "file:///a.png".into(),
            name: "a.png".into(),
            mime_type: Some("image/png".into()),
        };
        assert_eq!(
            serde_json::to_value(block).unwrap(),
            json!({"type": "resource_link", "uri": "file:///a.png", "name": "a.png", "mimeType": "image/png"})
        );
    }
}
