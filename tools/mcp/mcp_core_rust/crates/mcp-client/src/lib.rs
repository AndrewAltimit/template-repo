//! MCP Client - REST client for proxying tool calls to backend servers.
//!
//! This crate provides the client implementation for MCP servers running
//! in "client" mode, which proxy tool calls to a REST backend.
//!
//! # Example
//!
//! ```rust,ignore
//! use mcp_client::RestToolClient;
//!
//! let client = RestToolClient::new("http://localhost:8080");
//!
//! // List available tools
//! let tools = client.list_tools().await?;
//!
//! // Execute a tool
//! let result = client.execute_tool("echo", json!({"message": "hello"})).await?;
//! ```

use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::Arc;
use thiserror::Error;
use tracing::{debug, error, info};

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

/// Tool information from the backend
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolInfo {
    /// Tool name
    pub name: String,
    /// Tool description
    pub description: String,
    /// Input schema
    #[serde(alias = "parameters")]
    pub input_schema: Value,
}

/// Tool execution result from backend
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolExecutionResult {
    /// Whether execution was successful
    pub success: bool,
    /// Result value
    pub result: Option<Value>,
    /// Error message if failed
    pub error: Option<String>,
}

/// REST client for communicating with MCP tool backends
#[derive(Clone)]
pub struct RestToolClient {
    base_url: String,
    client: Client,
}

impl RestToolClient {
    /// Create a new REST tool client
    pub fn new(base_url: impl Into<String>) -> Self {
        let base = base_url.into();
        // Remove trailing slash if present
        let base = base.trim_end_matches('/').to_string();
        Self {
            base_url: base,
            client: Client::new(),
        }
    }

    /// Create a new client with a custom reqwest client
    pub fn with_client(base_url: impl Into<String>, client: Client) -> Self {
        let base = base_url.into();
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

    /// List available tools from the backend
    pub async fn list_tools(&self) -> Result<Vec<ToolInfo>> {
        // Try REST endpoint first, fall back to MCP endpoint
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
            return Err(ClientError::BackendError(format!(
                "HTTP {}: {}",
                status, text
            )));
        }

        let body: Value = response.json().await?;
        let tools = body
            .get("tools")
            .and_then(|t| serde_json::from_value(t.clone()).ok())
            .unwrap_or_default();

        Ok(tools)
    }

    /// Execute a tool on the backend
    pub async fn execute_tool(&self, name: &str, arguments: Value) -> Result<ToolExecutionResult> {
        // Try REST endpoint first, fall back to MCP endpoint
        let rest_url = format!("{}/tools/{}/call", self.base_url, name);
        let mcp_url = format!("{}/mcp/execute", self.base_url);

        debug!("Executing tool {} on backend", name);

        // Try REST-style endpoint first
        let rest_body = serde_json::json!({ "arguments": arguments });
        let response = match self.client.post(&rest_url).json(&rest_body).send().await {
            Ok(r) if r.status().is_success() || r.status() == reqwest::StatusCode::NOT_FOUND => r,
            _ => {
                // Fall back to MCP-style endpoint
                debug!("REST endpoint failed, trying MCP endpoint");
                let mcp_body = serde_json::json!({
                    "tool": name,
                    "arguments": arguments
                });
                self.client.post(&mcp_url).json(&mcp_body).send().await?
            },
        };

        if response.status() == reqwest::StatusCode::NOT_FOUND {
            // Check if it's really not found vs the endpoint doesn't exist
            let result: ToolExecutionResult = response.json().await?;
            if !result.success
                && result
                    .error
                    .as_ref()
                    .is_some_and(|e| e.contains("not found"))
            {
                return Err(ClientError::ToolNotFound(name.to_string()));
            }
            return Ok(result);
        }

        if !response.status().is_success() {
            let status = response.status();
            let text = response.text().await.unwrap_or_default();
            error!("Failed to execute tool {}: {} - {}", name, status, text);
            return Err(ClientError::BackendError(format!(
                "HTTP {}: {}",
                status, text
            )));
        }

        let result: ToolExecutionResult = response.json().await?;
        Ok(result)
    }
}

// ============================================================================
// Proxy Tool - wraps backend tool as local Tool trait impl
// ============================================================================

/// A proxy tool that forwards execution to a REST backend
pub struct ProxyTool {
    name: String,
    description: String,
    input_schema: Value,
    client: Arc<RestToolClient>,
}

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

/// MCP Tool trait implementation for ProxyTool
/// This allows ProxyTool to be used with the MCP server infrastructure
#[async_trait]
pub trait ProxyToolTrait: Send + Sync {
    fn name(&self) -> &str;
    fn description(&self) -> &str;
    fn schema(&self) -> Value;
    async fn execute(&self, args: Value) -> std::result::Result<ProxyToolResult, String>;
}

/// Result type for proxy tool execution
#[derive(Debug, Clone)]
pub struct ProxyToolResult {
    pub content: Vec<ProxyContent>,
    pub is_error: bool,
}

/// Content types for proxy tool results
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum ProxyContent {
    Text { text: String },
    Image { data: String, mime_type: String },
    Resource { uri: String, mime_type: String },
}

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

        match self.client.execute_tool(&self.name, args).await {
            Ok(result) => {
                if result.success {
                    // Extract content from result
                    let content = if let Some(res) = result.result {
                        // Try to extract content array
                        if let Some(content_arr) = res.get("content").and_then(|c| c.as_array()) {
                            content_arr
                                .iter()
                                .filter_map(|c| {
                                    c.get("text").and_then(|t| t.as_str()).map(|text| {
                                        ProxyContent::Text {
                                            text: text.to_string(),
                                        }
                                    })
                                })
                                .collect()
                        } else {
                            // Wrap the result as text
                            vec![ProxyContent::Text {
                                text: serde_json::to_string_pretty(&res)
                                    .unwrap_or_else(|_| res.to_string()),
                            }]
                        }
                    } else {
                        vec![ProxyContent::Text {
                            text: "OK".to_string(),
                        }]
                    };

                    Ok(ProxyToolResult {
                        content,
                        is_error: false,
                    })
                } else {
                    Ok(ProxyToolResult {
                        content: vec![ProxyContent::Text {
                            text: result.error.unwrap_or_else(|| "Unknown error".to_string()),
                        }],
                        is_error: true,
                    })
                }
            },
            Err(e) => Err(e.to_string()),
        }
    }
}

/// Create proxy tools from a backend URL
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
}
