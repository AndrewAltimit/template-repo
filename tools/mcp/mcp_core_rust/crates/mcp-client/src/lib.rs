//! MCP Client - REST client for proxying tool calls to backend servers.
//!
//! This crate provides the client implementation for MCP servers running
//! in "client" mode, which proxy tool calls to a REST backend. The proxy
//! itself (a `Tool` implementation per backend tool) lives in `mcp-core`'s
//! client mode (`MCPServer` with `ServerMode::Client`); this crate only speaks
//! HTTP to the backend.
//!
//! # Example
//!
//! ```no_run
//! use mcp_client::RestToolClient;
//! use serde_json::json;
//!
//! # async fn demo() -> mcp_client::Result<()> {
//! let client = RestToolClient::new("http://localhost:8080");
//!
//! // List available tools
//! let tools = client.list_tools().await?;
//!
//! // Execute a tool
//! let result = client.execute_tool("echo", json!({"message": "hello"})).await?;
//! assert!(result.success);
//! # Ok(())
//! # }
//! ```
//!
//! Both backend flavours are supported: the REST-only server mode
//! (`GET /tools`, `POST /tools/{name}/call`) and the simple API of the
//! standalone HTTP mode (`GET /mcp/tools`, `POST /mcp/execute`).

use async_trait::async_trait;
use reqwest::{Client, StatusCode};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::sync::Arc;
use std::time::Duration;
use thiserror::Error;
use tracing::{debug, error, info};

/// Connection-establishment timeout for the default client. There is no
/// total request timeout: proxied tools (renders, training jobs) can
/// legitimately run for a long time. Use [`RestToolClient::with_client`] to
/// impose one.
pub const DEFAULT_CONNECT_TIMEOUT: Duration = Duration::from_secs(10);

/// Errors that can occur when communicating with the REST backend
#[derive(Error, Debug)]
pub enum ClientError {
    /// HTTP request failed
    #[error("HTTP error: {0}")]
    HttpError(#[from] reqwest::Error),

    /// Backend returned an error
    #[error("Backend error: {0}")]
    BackendError(String),

    /// Failed to parse response
    #[error("Parse error: {0}")]
    ParseError(#[from] serde_json::Error),

    /// Tool not found
    #[error("Tool not found: {0}")]
    ToolNotFound(String),
}

/// Result type for client operations
pub type Result<T> = std::result::Result<T, ClientError>;

fn default_input_schema() -> Value {
    json!({"type": "object", "properties": {}})
}

/// Tool information from the backend
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolInfo {
    /// Tool name
    pub name: String,
    /// Tool description (empty if the backend omits it)
    #[serde(default)]
    pub description: String,
    /// Input schema (accepts `input_schema`, `inputSchema` or `parameters`;
    /// an empty object schema if the backend omits it)
    #[serde(
        default = "default_input_schema",
        alias = "parameters",
        alias = "inputSchema"
    )]
    pub input_schema: Value,
}

/// Tool execution result from backend
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolExecutionResult {
    /// Whether execution was successful
    pub success: bool,
    /// Result value
    #[serde(default)]
    pub result: Option<Value>,
    /// Error message if failed
    #[serde(default)]
    pub error: Option<String>,
}

/// REST client for communicating with MCP tool backends
#[derive(Clone, Debug)]
pub struct RestToolClient {
    base_url: String,
    client: Client,
}

impl RestToolClient {
    /// Create a new REST tool client with a [`DEFAULT_CONNECT_TIMEOUT`].
    pub fn new(base_url: impl Into<String>) -> Self {
        let client = Client::builder()
            .connect_timeout(DEFAULT_CONNECT_TIMEOUT)
            .build()
            .unwrap_or_else(|_| Client::new());
        Self::with_client(base_url, client)
    }

    /// Create a new client with a custom reqwest client
    pub fn with_client(base_url: impl Into<String>, client: Client) -> Self {
        let base = base_url.into();
        // Remove trailing slash if present
        let base = base.trim_end_matches('/').to_string();
        Self {
            base_url: base,
            client,
        }
    }

    /// Get the backend URL
    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    /// Check if the backend is healthy
    pub async fn health_check(&self) -> Result<bool> {
        let url = format!("{}/health", self.base_url);
        debug!("Health check: {}", url);

        let response = self.client.get(&url).send().await?;

        Ok(response.status().is_success())
    }

    /// List available tools from the backend.
    ///
    /// Tries the REST endpoint (`/tools`) first and falls back to the simple
    /// API (`/mcp/tools`). A response without a `tools` array is an error
    /// rather than an empty list, so a misconfigured backend URL is noticed.
    pub async fn list_tools(&self) -> Result<Vec<ToolInfo>> {
        let rest_url = format!("{}/tools", self.base_url);
        let mcp_url = format!("{}/mcp/tools", self.base_url);

        debug!("Listing tools from: {}", rest_url);

        let response = match self.client.get(&rest_url).send().await {
            Ok(r) if r.status().is_success() => r,
            _ => {
                debug!("REST endpoint failed, trying MCP endpoint: {}", mcp_url);
                self.client.get(&mcp_url).send().await?
            },
        };

        if !response.status().is_success() {
            let status = response.status();
            let text = response.text().await.unwrap_or_default();
            error!("Failed to list tools: {} - {}", status, text);
            return Err(ClientError::BackendError(format!("HTTP {status}: {text}")));
        }

        let mut body: Value = response.json().await?;
        let tools = body.get_mut("tools").map(Value::take).ok_or_else(|| {
            ClientError::BackendError("tool list response has no 'tools' field".to_string())
        })?;
        Ok(serde_json::from_value(tools)?)
    }

    /// POST `body` to `url`; `Some` when the response body is a
    /// [`ToolExecutionResult`] (whatever the status), `None` when it is not
    /// (e.g. the endpoint does not exist on this backend flavour).
    async fn try_execute(
        &self,
        url: &str,
        body: &Value,
    ) -> Result<Option<(StatusCode, ToolExecutionResult)>> {
        let response = self.client.post(url).json(body).send().await?;
        let status = response.status();
        let text = response.text().await?;
        Ok(serde_json::from_str::<ToolExecutionResult>(&text)
            .ok()
            .map(|r| (status, r)))
    }

    /// Execute a tool on the backend.
    ///
    /// Tries `POST /tools/{name}/call` (REST server mode) and falls back to
    /// `POST /mcp/execute` (standalone simple API) when the first endpoint is
    /// unreachable or does not answer with an execution result. A backend
    /// tool failure (`success: false`, even with HTTP 500) is returned as
    /// `Ok` so its error text reaches the model; an unknown tool is
    /// [`ClientError::ToolNotFound`].
    pub async fn execute_tool(&self, name: &str, arguments: Value) -> Result<ToolExecutionResult> {
        let rest_url = format!("{}/tools/{}/call", self.base_url, name);
        let mcp_url = format!("{}/mcp/execute", self.base_url);

        debug!("Executing tool {} on backend", name);

        let rest_body = json!({ "arguments": &arguments });
        match self.try_execute(&rest_url, &rest_body).await {
            Ok(Some((status, result))) => return Self::finish(name, status, result),
            Ok(None) => debug!("REST endpoint did not return a result, trying MCP endpoint"),
            Err(e) => debug!("REST endpoint failed ({}), trying MCP endpoint", e),
        }

        let mcp_body = json!({ "tool": name, "arguments": arguments });
        let response = self.client.post(&mcp_url).json(&mcp_body).send().await?;
        let status = response.status();
        let text = response.text().await?;
        match serde_json::from_str::<ToolExecutionResult>(&text) {
            Ok(result) => Self::finish(name, status, result),
            Err(_) => {
                error!("Failed to execute tool {}: {} - {}", name, status, text);
                Err(ClientError::BackendError(format!("HTTP {status}: {text}")))
            },
        }
    }

    fn finish(
        name: &str,
        status: StatusCode,
        result: ToolExecutionResult,
    ) -> Result<ToolExecutionResult> {
        if status == StatusCode::NOT_FOUND
            && !result.success
            && result
                .error
                .as_ref()
                .is_some_and(|e| e.contains("not found"))
        {
            return Err(ClientError::ToolNotFound(name.to_string()));
        }
        Ok(result)
    }
}

// ============================================================================
// Proxy Tool - legacy standalone proxy types
// ============================================================================

/// A proxy tool that forwards execution to a REST backend
#[deprecated(
    since = "0.1.0",
    note = "cannot implement mcp_core::Tool from this crate; use MCPServer client mode (ServerMode::Client), which builds proxy tools itself"
)]
pub struct ProxyTool {
    name: String,
    description: String,
    input_schema: Value,
    client: Arc<RestToolClient>,
}

#[allow(deprecated)]
impl ProxyTool {
    /// Create a new proxy tool
    pub fn new(info: &ToolInfo, client: Arc<RestToolClient>) -> Self {
        Self {
            name: info.name.clone(),
            description: info.description.clone(),
            input_schema: info.input_schema.clone(),
            client,
        }
    }
}

/// Tool-like trait implemented by [`ProxyTool`].
#[deprecated(
    since = "0.1.0",
    note = "use MCPServer client mode (ServerMode::Client)"
)]
#[async_trait]
pub trait ProxyToolTrait: Send + Sync {
    /// Tool name
    fn name(&self) -> &str;
    /// Tool description
    fn description(&self) -> &str;
    /// Input schema
    fn schema(&self) -> Value;
    /// Execute on the backend
    async fn execute(&self, args: Value) -> std::result::Result<ProxyToolResult, String>;
}

/// Result type for proxy tool execution
#[derive(Debug, Clone)]
pub struct ProxyToolResult {
    /// Content blocks
    pub content: Vec<ProxyContent>,
    /// Whether the result is an error
    pub is_error: bool,
}

/// Content types for proxy tool results
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum ProxyContent {
    /// Text content
    Text {
        /// The text
        text: String,
    },
    /// Base64 image content
    Image {
        /// Base64 data
        data: String,
        /// MIME type
        mime_type: String,
    },
    /// Resource reference
    Resource {
        /// Resource URI
        uri: String,
        /// MIME type
        mime_type: String,
    },
}

#[allow(deprecated)]
#[async_trait]
impl ProxyToolTrait for ProxyTool {
    fn name(&self) -> &str {
        &self.name
    }

    fn description(&self) -> &str {
        &self.description
    }

    fn schema(&self) -> Value {
        self.input_schema.clone()
    }

    async fn execute(&self, args: Value) -> std::result::Result<ProxyToolResult, String> {
        info!(
            "Proxying tool call: {} to {}",
            self.name,
            self.client.base_url()
        );

        let result = self
            .client
            .execute_tool(&self.name, args)
            .await
            .map_err(|e| e.to_string())?;

        let texts: Option<Vec<ProxyContent>> = result.result.as_ref().and_then(|res| {
            res.get("content").and_then(Value::as_array).map(|arr| {
                arr.iter()
                    .filter_map(|c| {
                        c.get("text")
                            .and_then(Value::as_str)
                            .map(|text| ProxyContent::Text {
                                text: text.to_string(),
                            })
                    })
                    .collect()
            })
        });

        let content = match (result.success, texts, result.result) {
            (_, Some(texts), _) if !texts.is_empty() => texts,
            (true, _, Some(res)) => vec![ProxyContent::Text {
                text: serde_json::to_string_pretty(&res).unwrap_or_else(|_| res.to_string()),
            }],
            (true, _, None) => vec![ProxyContent::Text {
                text: "OK".to_string(),
            }],
            (false, _, _) => vec![ProxyContent::Text {
                text: result.error.unwrap_or_else(|| "Unknown error".to_string()),
            }],
        };

        Ok(ProxyToolResult {
            content,
            is_error: !result.success,
        })
    }
}

/// Create proxy tools from a backend URL
#[deprecated(
    since = "0.1.0",
    note = "use MCPServer client mode (ServerMode::Client)"
)]
#[allow(deprecated)]
pub async fn create_proxy_tools(
    backend_url: &str,
) -> Result<(Arc<RestToolClient>, Vec<ProxyTool>)> {
    let client = Arc::new(RestToolClient::new(backend_url));

    info!("Fetching tools from backend: {}", backend_url);

    // Verify backend is healthy
    if !client.health_check().await? {
        return Err(ClientError::BackendError(
            "Backend health check failed".to_string(),
        ));
    }

    // Fetch tool list
    let tool_infos = client.list_tools().await?;
    info!("Found {} tools on backend", tool_infos.len());

    // Create proxy tools
    let proxy_tools: Vec<ProxyTool> = tool_infos
        .iter()
        .map(|info| ProxyTool::new(info, Arc::clone(&client)))
        .collect();

    Ok((client, proxy_tools))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_creation() {
        let client = RestToolClient::new("http://localhost:8080");
        assert_eq!(client.base_url(), "http://localhost:8080");
    }

    #[test]
    fn test_client_trailing_slash() {
        let client = RestToolClient::new("http://localhost:8080/");
        assert_eq!(client.base_url(), "http://localhost:8080");
    }

    #[test]
    #[allow(deprecated)]
    fn test_proxy_tool_creation() {
        let info = ToolInfo {
            name: "test".to_string(),
            description: "A test tool".to_string(),
            input_schema: serde_json::json!({"type": "object"}),
        };
        let client = Arc::new(RestToolClient::new("http://localhost:8080"));
        let proxy = ProxyTool::new(&info, client);

        assert_eq!(proxy.name(), "test");
        assert_eq!(proxy.description(), "A test tool");
    }

    #[test]
    fn tool_info_is_lenient() {
        let info: ToolInfo = serde_json::from_value(json!({"name": "x"})).unwrap();
        assert_eq!(info.description, "");
        assert_eq!(info.input_schema["type"], "object");
        for key in ["parameters", "inputSchema", "input_schema"] {
            let info: ToolInfo =
                serde_json::from_value(json!({"name": "x", key: {"type": "object", "k": 1}}))
                    .unwrap();
            assert_eq!(info.input_schema["k"], 1, "{key}");
        }
    }

    #[test]
    fn not_found_detection() {
        let r = ToolExecutionResult {
            success: false,
            result: None,
            error: Some("Tool 'x' not found".into()),
        };
        assert!(matches!(
            RestToolClient::finish("x", StatusCode::NOT_FOUND, r.clone()),
            Err(ClientError::ToolNotFound(_))
        ));
        assert!(RestToolClient::finish("x", StatusCode::INTERNAL_SERVER_ERROR, r).is_ok());
    }
}
