//! MCP Testing - Test utilities for MCP servers.
//!
//! This crate provides utilities for testing MCP servers:
//!
//! - [`TestServer`]: registers real tools and calls them directly
//!   ([`TestServer::call_tool`]) or through the full JSON-RPC protocol handler
//!   ([`TestServer::rpc`]), without standing up HTTP or STDIO.
//! - [`MockTool`]: a configurable mock tool that records its calls.
//! - [`assertions`]: helpers for common checks on a [`ToolResult`].
//!
//! # Example
//!
//! ```
//! use mcp_testing::{MockTool, TestServer, assertions};
//! use serde_json::json;
//!
//! # tokio::runtime::Runtime::new().unwrap().block_on(async {
//! let server = TestServer::new()
//!     .with_tool(MockTool::new("echo").with_result(json!({"message": "hello"})));
//!
//! // Direct call through `Tool::execute` (with the production panic boundary).
//! let result = server.call_tool("echo", json!({})).await.unwrap();
//! assertions::assert_success(&result);
//! assertions::assert_text_contains(&result, "hello");
//!
//! // Full protocol round trip.
//! let resp = server.rpc("tools/list", json!({})).await;
//! assert_eq!(resp["result"]["tools"][0]["name"], "echo");
//! # });
//! ```

use async_trait::async_trait;
use mcp_core::{
    server::MCPServer,
    tool::{Tool, ToolRegistry, ToolResult},
    transport::MCPHandler,
};
use serde_json::{Value, json};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, PoisonError, RwLock};

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
            schema: json!({"type": "object", "properties": {}}),
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

    fn set_result(&self, result: ToolResult) {
        *self.result.write().unwrap_or_else(PoisonError::into_inner) = result;
    }

    /// Set the result to return (as pretty-printed JSON text)
    pub fn with_result(self, result: Value) -> Self {
        let tool_result = ToolResult::json(&result).unwrap_or_else(|_| ToolResult::text("error"));
        self.set_result(tool_result);
        self
    }

    /// Set the result to return as text
    pub fn with_text_result(self, text: impl Into<String>) -> Self {
        self.set_result(ToolResult::text(text));
        self
    }

    /// Set the exact [`ToolResult`] to return (e.g. multiple or image blocks)
    pub fn with_tool_result(self, result: ToolResult) -> Self {
        self.set_result(result);
        self
    }

    /// Set the tool to return an error
    pub fn with_error(self, error: impl Into<String>) -> Self {
        self.set_result(ToolResult::error(error));
        self
    }

    /// Get the number of times the tool was called
    pub fn call_count(&self) -> usize {
        self.call_count.load(Ordering::SeqCst)
    }

    /// Get the last arguments passed to the tool
    pub fn last_args(&self) -> Option<Value> {
        self.last_args
            .read()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }

    /// Reset the call count and last args
    pub fn reset(&self) {
        self.call_count.store(0, Ordering::SeqCst);
        *self
            .last_args
            .write()
            .unwrap_or_else(PoisonError::into_inner) = None;
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
        *self
            .last_args
            .write()
            .unwrap_or_else(PoisonError::into_inner) = Some(args);
        Ok(self
            .result
            .read()
            .unwrap_or_else(PoisonError::into_inner)
            .clone())
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

    /// Build an [`MCPServer`] (version `1.0.0`) with this server's tools.
    pub fn build(self, name: &str) -> MCPServer {
        MCPServer::builder(name, "1.0.0")
            .tools_boxed(self.tools.iter().cloned())
            .build()
    }

    /// Call a tool directly (without any transport).
    ///
    /// Runs inside the same panic boundary as production, so a panicking tool
    /// yields an `is_error` result. `Err` carries the tool's own error (or
    /// "Tool not found") as a string.
    pub async fn call_tool(&self, name: &str, args: Value) -> Result<ToolResult, String> {
        self.tools.call(name, args).await.map_err(|e| e.to_string())
    }

    /// List all registered tools
    pub fn list_tools(&self) -> Vec<&str> {
        self.tools.names()
    }

    /// A protocol handler (named `test-server`) over this server's tools.
    ///
    /// Tools are shared, not copied, so state is visible across handlers.
    pub fn handler(&self) -> MCPHandler {
        MCPHandler::new("test-server", "1.0.0", self.tools.clone())
    }

    /// Send one JSON-RPC request (id `1`) through the full protocol handler
    /// and return the raw response object (`{"jsonrpc", "id", "result"|"error"}`).
    ///
    /// Use this to test protocol-level behaviour: error codes, `isError`
    /// mapping of tool failures, schema listing, etc.
    pub async fn rpc(&self, method: &str, params: Value) -> Value {
        self.handler()
            .handle_message(
                json!({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}),
                None,
            )
            .await
            .unwrap_or(Value::Null)
    }
}

impl Default for TestServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Assertion helpers for testing tool results
pub mod assertions {
    use mcp_core::tool::ToolResult;

    /// Assert that a tool result is successful
    pub fn assert_success(result: &ToolResult) {
        assert!(
            !result.is_error,
            "Expected success but got error: {}",
            result.text_content()
        );
    }

    /// Assert that a tool result is an error
    pub fn assert_error(result: &ToolResult) {
        assert!(
            result.is_error,
            "Expected error but got success: {}",
            result.text_content()
        );
    }

    /// Assert that a tool result contains text matching the expected value
    pub fn assert_text_contains(result: &ToolResult, expected: &str) {
        let text = result.text_content();
        assert!(
            text.contains(expected),
            "Expected text to contain '{}', got: {}",
            expected,
            text
        );
    }

    /// Assert that a tool result is an error whose text contains `expected`
    pub fn assert_error_contains(result: &ToolResult, expected: &str) {
        assert_error(result);
        assert_text_contains(result, expected);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[tokio::test]
    async fn test_mock_tool() {
        let tool = MockTool::new("test").with_text_result("hello");

        let result = tool.execute(json!({"a": 1})).await.unwrap();
        assert!(!result.is_error);
        assert_eq!(tool.call_count(), 1);
        assert_eq!(tool.last_args(), Some(json!({"a": 1})));
        tool.reset();
        assert_eq!(tool.call_count(), 0);
        assert_eq!(tool.last_args(), None);
    }

    #[tokio::test]
    async fn test_test_server() {
        let server = TestServer::new().with_tool(MockTool::new("echo").with_text_result("pong"));

        let result = server.call_tool("echo", json!({})).await.unwrap();
        assert!(!result.is_error);
        assert!(server.call_tool("missing", json!({})).await.is_err());
    }

    #[test]
    fn build_keeps_tools() {
        let server = TestServer::new()
            .with_tool(MockTool::new("a"))
            .with_tool(MockTool::new("b"))
            .build("s");
        assert_eq!(server.tools().names(), vec!["a", "b"]);
    }

    #[tokio::test]
    async fn rpc_round_trip_and_error_mapping() {
        let server = TestServer::new().with_tool(MockTool::new("fails").with_error("nope"));
        let resp = server
            .rpc("tools/call", json!({"name": "fails", "arguments": {}}))
            .await;
        assert_eq!(resp["result"]["isError"], true);
        let resp = server.rpc("tools/call", json!({"name": "missing"})).await;
        assert_eq!(resp["error"]["code"], -32602);
        let resp = server.rpc("ping", json!({})).await;
        assert_eq!(resp["result"], json!({}));
    }

    #[tokio::test]
    async fn assertions_work() {
        let server =
            TestServer::new().with_tool(MockTool::new("fails").with_error("boom happened"));
        let result = server.call_tool("fails", json!({})).await.unwrap();
        assertions::assert_error_contains(&result, "boom");
    }
}
