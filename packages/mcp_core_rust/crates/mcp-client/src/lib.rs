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

use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use thiserror::Error;
use tracing::{debug, error};

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
    pub parameters: Value,
}

/// Tool execution result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
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
        Self {
            base_url: base_url.into(),
            client: Client::new(),
        }
    }

    /// Create a new client with a custom reqwest client
    pub fn with_client(base_url: impl Into<String>, client: Client) -> Self {
        Self {
            base_url: base_url.into(),
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
        let url = format!("{}/mcp/tools", self.base_url);
        debug!("Listing tools: {}", url);

        let response = self.client.get(&url).send().await?;

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
    pub async fn execute_tool(&self, name: &str, arguments: Value) -> Result<ToolResult> {
        let url = format!("{}/mcp/execute", self.base_url);
        debug!("Executing tool {}: {}", name, url);

        let request_body = serde_json::json!({
            "tool": name,
            "arguments": arguments
        });

        let response = self.client.post(&url).json(&request_body).send().await?;

        if !response.status().is_success() {
            let status = response.status();
            let text = response.text().await.unwrap_or_default();
            error!("Failed to execute tool {}: {} - {}", name, status, text);
            return Err(ClientError::BackendError(format!(
                "HTTP {}: {}",
                status, text
            )));
        }

        let result: ToolResult = response.json().await?;
        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_creation() {
        let client = RestToolClient::new("http://localhost:8080");
        assert_eq!(client.base_url(), "http://localhost:8080");
    }
}
