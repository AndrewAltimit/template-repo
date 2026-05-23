//! Shared MCP protocol handler used by both HTTP and STDIO transports.

use std::panic::AssertUnwindSafe;

use futures::FutureExt;
use serde_json::{Value, json};
use tracing::{error, info};

use crate::error::{JsonRpcErrorCode, MCPError};
use crate::jsonrpc::{
    ContentBlock, InitializeParams, InitializeResult, JsonRpcRequest, JsonRpcResponse,
    ServerCapabilities, ServerInfo, ToolCallParams, ToolCallResult, ToolInfo, ToolsListResult,
};
use crate::session::{ClientInfo, SessionManager};
use crate::tool::{Content, ToolRegistry, ToolResult};

/// Extract a human-readable message from a caught panic payload.
fn panic_message(payload: &(dyn std::any::Any + Send)) -> String {
    if let Some(s) = payload.downcast_ref::<&str>() {
        (*s).to_string()
    } else if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else {
        "unknown panic".to_string()
    }
}

/// Shared MCP protocol handler.
///
/// Contains the core JSON-RPC message processing logic used by all transports
/// (HTTP, STDIO, etc.). Each transport wraps this handler with its own I/O layer.
pub struct MCPHandler {
    /// Server name
    pub name: String,
    /// Server version
    pub version: String,
    /// Tool registry
    pub tools: ToolRegistry,
    /// Session manager
    pub sessions: SessionManager,
}

impl MCPHandler {
    /// Create a new handler.
    pub fn new(name: impl Into<String>, version: impl Into<String>, tools: ToolRegistry) -> Self {
        Self {
            name: name.into(),
            version: version.into(),
            tools,
            sessions: SessionManager::new(),
        }
    }

    /// Process a JSON-RPC request and return an optional response.
    ///
    /// Returns `None` for notifications (requests without an ID).
    pub async fn process_request(
        &self,
        request: &JsonRpcRequest,
        session_id: &Option<String>,
    ) -> Option<JsonRpcResponse> {
        let is_notification = request.is_notification();
        let id = request.id.clone().unwrap_or(json!(null));

        info!("JSON-RPC request: method={}, id={:?}", request.method, id);

        let result = match request.method.as_str() {
            "initialize" => self.handle_initialize(&request.params, session_id).await,
            "initialized" => {
                info!("Client sent initialized notification");
                if is_notification {
                    return None;
                }
                Ok(json!({"status": "acknowledged"}))
            },
            "tools/list" => self.handle_tools_list().await,
            "tools/call" => self.handle_tools_call(&request.params).await,
            "ping" => Ok(json!({"pong": true})),
            "completion/complete" => Ok(json!({"error": "Completions not supported"})),
            _ => {
                if is_notification {
                    return None;
                }
                return Some(JsonRpcResponse::error_with_code(
                    id,
                    JsonRpcErrorCode::MethodNotFound,
                    Some(format!("Method not found: {}", request.method)),
                ));
            },
        };

        if is_notification {
            return None;
        }

        Some(match result {
            Ok(value) => JsonRpcResponse::success(id, value),
            Err(e) => JsonRpcResponse::error_with_code(
                id,
                JsonRpcErrorCode::from(e.clone()),
                Some(e.to_string()),
            ),
        })
    }

    /// Handle the `initialize` method.
    pub async fn handle_initialize(
        &self,
        params: &Value,
        session_id: &Option<String>,
    ) -> Result<Value, MCPError> {
        let init_params: InitializeParams =
            serde_json::from_value(params.clone()).unwrap_or(InitializeParams {
                protocol_version: "2024-11-05".to_string(),
                client_info: None,
                capabilities: json!({}),
            });

        info!(
            "Initialize: client={:?}, protocol={}",
            init_params.client_info, init_params.protocol_version
        );

        // Update session with client info
        if let Some(sid) = session_id
            && let Some(client) = &init_params.client_info
        {
            self.sessions
                .update(sid, |s| {
                    s.client_info = Some(ClientInfo {
                        name: client.name.clone(),
                        version: client.version.clone(),
                    });
                    s.mark_initialized();
                })
                .await;
        }

        let result = InitializeResult {
            protocol_version: init_params.protocol_version,
            server_info: ServerInfo {
                name: self.name.clone(),
                version: self.version.clone(),
            },
            capabilities: ServerCapabilities::default(),
        };

        Ok(serde_json::to_value(result)?)
    }

    /// Handle the `tools/list` method.
    pub async fn handle_tools_list(&self) -> Result<Value, MCPError> {
        let tools: Vec<ToolInfo> = self
            .tools
            .list()
            .into_iter()
            .map(|t| ToolInfo {
                name: t.name,
                description: t.description,
                input_schema: t.input_schema,
            })
            .collect();

        info!("Returning {} tools", tools.len());

        let result = ToolsListResult {
            tools,
            next_cursor: None,
        };

        Ok(serde_json::to_value(result)?)
    }

    /// Handle the `tools/call` method.
    pub async fn handle_tools_call(&self, params: &Value) -> Result<Value, MCPError> {
        let call_params: ToolCallParams = serde_json::from_value(params.clone())
            .map_err(|e| MCPError::InvalidParameters(e.to_string()))?;

        info!("Calling tool: {}", call_params.name);

        let tool = self
            .tools
            .get(&call_params.name)
            .ok_or_else(|| MCPError::ToolNotFound(call_params.name.clone()))?;

        // Execute the tool inside a panic boundary. A buggy tool that panics on
        // malformed/untrusted arguments must not take down the whole server (or
        // the connection task); instead the panic is converted into an MCP tool
        // error result (`isError: true`), which is the spec-recommended way to
        // surface execution failures so the client/model can recover.
        let result = match AssertUnwindSafe(tool.execute(call_params.arguments))
            .catch_unwind()
            .await
        {
            Ok(Ok(result)) => result,
            Ok(Err(e)) => return Err(e),
            Err(panic) => {
                let msg = panic_message(panic.as_ref());
                error!(
                    "Tool '{}' panicked during execution: {}",
                    call_params.name, msg
                );
                ToolResult::error(format!(
                    "Tool '{}' panicked during execution: {}",
                    call_params.name, msg
                ))
            },
        };

        // Convert internal content to JSON-RPC content blocks
        let content: Vec<ContentBlock> = result
            .content
            .into_iter()
            .map(|c| match c {
                Content::Text { text } => ContentBlock::Text { text },
                Content::Image { data, mime_type } => ContentBlock::Image { data, mime_type },
                Content::Resource { uri, mime_type } => ContentBlock::Resource { uri, mime_type },
            })
            .collect();

        let call_result = ToolCallResult {
            content,
            is_error: result.is_error,
        };

        Ok(serde_json::to_value(call_result)?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tool::ToolResult;
    use async_trait::async_trait;

    struct TestTool;

    #[async_trait]
    impl crate::tool::Tool for TestTool {
        fn name(&self) -> &str {
            "test_tool"
        }
        fn description(&self) -> &str {
            "A test tool"
        }
        fn schema(&self) -> Value {
            json!({
                "type": "object",
                "properties": {}
            })
        }
        async fn execute(&self, _args: Value) -> crate::error::Result<ToolResult> {
            Ok(ToolResult::text("test result"))
        }
    }

    struct PanicTool;

    #[async_trait]
    impl crate::tool::Tool for PanicTool {
        fn name(&self) -> &str {
            "panic_tool"
        }
        fn description(&self) -> &str {
            "A tool that panics, simulating an unwrap() on malformed input"
        }
        fn schema(&self) -> Value {
            json!({"type": "object", "properties": {}})
        }
        async fn execute(&self, _args: Value) -> crate::error::Result<ToolResult> {
            panic!("boom: simulated unwrap on bad arg");
        }
    }

    fn make_handler() -> MCPHandler {
        let mut tools = ToolRegistry::new();
        tools.register(TestTool);
        tools.register(PanicTool);
        MCPHandler::new("test-server", "1.0.0", tools)
    }

    #[tokio::test]
    async fn test_initialize() {
        let handler = make_handler();
        let req = JsonRpcRequest::new("initialize", json!({}), 1);
        let resp = handler.process_request(&req, &None).await.unwrap();
        assert!(resp.result.is_some());
        let result = resp.result.unwrap();
        assert_eq!(result["serverInfo"]["name"], "test-server");
    }

    #[tokio::test]
    async fn test_tools_list() {
        let handler = make_handler();
        let req = JsonRpcRequest::new("tools/list", json!({}), 1);
        let resp = handler.process_request(&req, &None).await.unwrap();
        let result = resp.result.unwrap();
        let tools = result["tools"].as_array().unwrap();
        assert_eq!(tools.len(), 2);
        assert!(tools.iter().any(|t| t["name"] == "test_tool"));
    }

    #[tokio::test]
    async fn test_tool_panic_is_caught() {
        // A panicking tool must not crash the handler; it should be reported as
        // a graceful tool error result (isError: true) with a successful
        // JSON-RPC envelope.
        let handler = make_handler();
        let req = JsonRpcRequest::new(
            "tools/call",
            json!({"name": "panic_tool", "arguments": {}}),
            1,
        );
        let resp = handler.process_request(&req, &None).await.unwrap();
        assert!(
            resp.error.is_none(),
            "panic should not surface as a protocol error"
        );
        let result = resp.result.expect("expected a successful JSON-RPC result");
        assert_eq!(result["isError"], true);
        let text = result["content"][0]["text"].as_str().unwrap();
        assert!(text.contains("panicked"), "got: {text}");
        assert!(
            text.contains("boom"),
            "panic message should be preserved: {text}"
        );

        // The handler must still serve subsequent requests after a panic.
        let req2 = JsonRpcRequest::new("ping", json!({}), 2);
        let resp2 = handler.process_request(&req2, &None).await.unwrap();
        assert_eq!(resp2.result.unwrap()["pong"], true);
    }

    #[tokio::test]
    async fn test_tools_call() {
        let handler = make_handler();
        let req = JsonRpcRequest::new(
            "tools/call",
            json!({"name": "test_tool", "arguments": {}}),
            1,
        );
        let resp = handler.process_request(&req, &None).await.unwrap();
        let result = resp.result.unwrap();
        assert_eq!(result["content"][0]["text"], "test result");
    }

    #[tokio::test]
    async fn test_tool_not_found() {
        let handler = make_handler();
        let req = JsonRpcRequest::new(
            "tools/call",
            json!({"name": "nonexistent", "arguments": {}}),
            1,
        );
        let resp = handler.process_request(&req, &None).await.unwrap();
        assert!(resp.error.is_some());
    }

    #[tokio::test]
    async fn test_method_not_found() {
        let handler = make_handler();
        let req = JsonRpcRequest::new("unknown/method", json!({}), 1);
        let resp = handler.process_request(&req, &None).await.unwrap();
        assert!(resp.error.is_some());
        assert_eq!(resp.error.unwrap().code, -32601);
    }

    #[tokio::test]
    async fn test_notification_no_response() {
        let handler = make_handler();
        let req = JsonRpcRequest::notification("initialized", json!({}));
        let resp = handler.process_request(&req, &None).await;
        assert!(resp.is_none());
    }

    #[tokio::test]
    async fn test_ping() {
        let handler = make_handler();
        let req = JsonRpcRequest::new("ping", json!({}), 1);
        let resp = handler.process_request(&req, &None).await.unwrap();
        let result = resp.result.unwrap();
        assert_eq!(result["pong"], true);
    }
}
