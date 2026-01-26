//! MCP Testing - Test utilities for MCP servers.
//!
//! This crate provides utilities for testing MCP servers:
//!
//! - `TestServer`: A wrapper around an MCP server for testing
//! - `MockTool`: A configurable mock tool for testing
//! - Test helpers for common assertions
//!
//! # Example
//!
//! ```rust,ignore
//! use mcp_testing::{TestServer, MockTool};
//! use serde_json::json;
//!
//! #[tokio::test]
//! async fn test_tool_execution() {
//!     let server = TestServer::new()
//!         .with_tool(MockTool::new("echo")
//!             .with_result(json!({"message": "hello"})));
//!
//!     let result = server.call_tool("echo", json!({})).await.unwrap();
//!     assert!(result.success);
//! }
//! ```

use async_trait::async_trait;
use mcp_core::{
    server::MCPServer,
    tool::{Tool, ToolRegistry, ToolResult},
};
use serde_json::Value;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, RwLock};

/// A configurable mock tool for testing
pub struct MockTool {
    name: String,
    description: String,
    schema: Value,
    result: Arc<RwLock<ToolResult>>,
    call_count: AtomicUsize,
    last_args: Arc<RwLock<Option<Value>>>,
}

impl MockTool {
    /// Create a new mock tool with the given name
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            description: "Mock tool for testing".to_string(),
            schema: serde_json::json!({"type": "object", "properties": {}}),
            result: Arc::new(RwLock::new(ToolResult::text("mock result"))),
            call_count: AtomicUsize::new(0),
            last_args: Arc::new(RwLock::new(None)),
        }
    }

    /// Set the tool description
    pub fn with_description(mut self, description: impl Into<String>) -> Self {
        self.description = description.into();
        self
    }

    /// Set the tool schema
    pub fn with_schema(mut self, schema: Value) -> Self {
        self.schema = schema;
        self
    }

    /// Set the result to return
    pub fn with_result(self, result: Value) -> Self {
        let tool_result = ToolResult::json(&result).unwrap_or_else(|_| ToolResult::text("error"));
        *self.result.write().unwrap() = tool_result;
        self
    }

    /// Set the result to return as text
    pub fn with_text_result(self, text: impl Into<String>) -> Self {
        *self.result.write().unwrap() = ToolResult::text(text);
        self
    }

    /// Set the tool to return an error
    pub fn with_error(self, error: impl Into<String>) -> Self {
        *self.result.write().unwrap() = ToolResult::error(error);
        self
    }

    /// Get the number of times the tool was called
    pub fn call_count(&self) -> usize {
        self.call_count.load(Ordering::SeqCst)
    }

    /// Get the last arguments passed to the tool
    pub fn last_args(&self) -> Option<Value> {
        self.last_args.read().unwrap().clone()
    }

    /// Reset the call count and last args
    pub fn reset(&self) {
        self.call_count.store(0, Ordering::SeqCst);
        *self.last_args.write().unwrap() = None;
    }
}

#[async_trait]
impl Tool for MockTool {
    fn name(&self) -> &str {
        &self.name
    }

    fn description(&self) -> &str {
        &self.description
    }

    fn schema(&self) -> Value {
        self.schema.clone()
    }

    async fn execute(&self, args: Value) -> mcp_core::error::Result<ToolResult> {
        self.call_count.fetch_add(1, Ordering::SeqCst);
        *self.last_args.write().unwrap() = Some(args);
        Ok(self.result.read().unwrap().clone())
    }
}

/// Test server wrapper for testing MCP servers
pub struct TestServer {
    tools: ToolRegistry,
}

impl TestServer {
    /// Create a new test server
    pub fn new() -> Self {
        Self {
            tools: ToolRegistry::new(),
        }
    }

    /// Add a tool to the test server
    pub fn with_tool<T: Tool + 'static>(mut self, tool: T) -> Self {
        self.tools.register(tool);
        self
    }

    /// Build an MCPServer from this test server
    pub fn build(self, name: &str) -> MCPServer {
        let builder = MCPServer::builder(name, "1.0.0");

        // We need to transfer tools - for now just return empty server
        // In practice, tests should use the TestClient approach
        builder.build()
    }

    /// Call a tool directly (without HTTP)
    pub async fn call_tool(&self, name: &str, args: Value) -> Result<ToolResult, String> {
        let tool = self
            .tools
            .get(name)
            .ok_or_else(|| format!("Tool not found: {}", name))?;

        tool.execute(args).await.map_err(|e| e.to_string())
    }

    /// List all registered tools
    pub fn list_tools(&self) -> Vec<&str> {
        self.tools.names()
    }
}

impl Default for TestServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Assertion helpers for testing tool results
pub mod assertions {
    use mcp_core::tool::{Content, ToolResult};

    /// Assert that a tool result is successful
    pub fn assert_success(result: &ToolResult) {
        assert!(!result.is_error, "Expected success but got error");
    }

    /// Assert that a tool result is an error
    pub fn assert_error(result: &ToolResult) {
        assert!(result.is_error, "Expected error but got success");
    }

    /// Assert that a tool result contains text matching the expected value
    pub fn assert_text_contains(result: &ToolResult, expected: &str) {
        let text = result
            .content
            .iter()
            .filter_map(|c| match c {
                Content::Text { text } => Some(text.as_str()),
                _ => None,
            })
            .collect::<Vec<_>>()
            .join("");

        assert!(
            text.contains(expected),
            "Expected text to contain '{}', got: {}",
            expected,
            text
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[tokio::test]
    async fn test_mock_tool() {
        let tool = MockTool::new("test").with_text_result("hello");

        let result = tool.execute(json!({})).await.unwrap();
        assert!(!result.is_error);
        assert_eq!(tool.call_count(), 1);
    }

    #[tokio::test]
    async fn test_test_server() {
        let server = TestServer::new().with_tool(MockTool::new("echo").with_text_result("pong"));

        let result = server.call_tool("echo", json!({})).await.unwrap();
        assert!(!result.is_error);
    }
}
