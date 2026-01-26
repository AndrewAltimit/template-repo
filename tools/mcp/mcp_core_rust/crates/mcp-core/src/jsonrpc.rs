//! JSON-RPC 2.0 types and handling for MCP protocol.

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::error::JsonRpcErrorCode;

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
            jsonrpc: "2.0".to_string(),
            method: method.into(),
            params,
            id: Some(id.into()),
        }
    }

    /// Create a notification (no response expected)
    pub fn notification(method: impl Into<String>, params: Value) -> Self {
        Self {
            jsonrpc: "2.0".to_string(),
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
            jsonrpc: "2.0".to_string(),
            result: Some(result),
            error: None,
            id,
        }
    }

    /// Create an error response
    pub fn error(id: Value, error: JsonRpcError) -> Self {
        Self {
            jsonrpc: "2.0".to_string(),
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
}

/// Server information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerInfo {
    /// Server name
    pub name: String,
    /// Server version
    pub version: String,
}

/// Server capabilities
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerCapabilities {
    /// Tool capabilities
    #[serde(default)]
    pub tools: ToolCapabilities,
    /// Resource capabilities (not supported yet)
    #[serde(default)]
    pub resources: Value,
    /// Prompt capabilities (not supported yet)
    #[serde(default)]
    pub prompts: Value,
}

impl Default for ServerCapabilities {
    fn default() -> Self {
        Self {
            tools: ToolCapabilities::default(),
            resources: Value::Object(Default::default()),
            prompts: Value::Object(Default::default()),
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
    /// Cursor for pagination (not implemented)
    pub cursor: Option<String>,
}

/// Tools list response result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolsListResult {
    /// List of available tools
    pub tools: Vec<ToolInfo>,
    /// Next cursor for pagination (not implemented)
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
    /// Resource content
    Resource {
        /// Resource URI
        uri: String,
        /// MIME type
        #[serde(rename = "mimeType")]
        mime_type: String,
    },
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
}
