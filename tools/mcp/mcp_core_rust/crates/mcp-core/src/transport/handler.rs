//! Shared MCP protocol handler used by both HTTP and STDIO transports.
//!
//! [`MCPHandler`] owns the protocol semantics (JSON-RPC 2.0 validation,
//! batching, the MCP lifecycle, tool dispatch); transports only move bytes.
//! The main entry points are:
//!
//! - [`MCPHandler::handle_raw`]: bytes in, optional response JSON out
//!   (handles parse errors).
//! - [`MCPHandler::handle_message`]: an already-parsed JSON value (single
//!   message or batch).
//! - [`MCPHandler::process_request`]: a typed [`JsonRpcRequest`] (kept for
//!   callers that construct requests directly).
//!
//! # Error reporting
//!
//! | Situation | Reported as |
//! |-----------|-------------|
//! | Unparseable JSON | `-32700` Parse error |
//! | Not a valid request object / empty batch / bad `id` | `-32600` Invalid Request |
//! | Unknown method | `-32601` Method not found |
//! | Bad `tools/call` params or unknown tool name | `-32602` Invalid params |
//! | Tool returned `Err`, panicked, or timed out | Result with `isError: true` |

use std::time::{Duration, Instant};

use serde::Deserialize;
use serde_json::{Value, json};
use tracing::{debug, info, warn};

use crate::context::{Notifier, RequestContext};
use crate::error::{JsonRpcErrorCode, MCPError};
use crate::jsonrpc::{
    ContentBlock, InitializeParams, InitializeResult, JSONRPC_VERSION, JsonRpcRequest,
    JsonRpcResponse, ServerCapabilities, ServerInfo, ToolCallParams, ToolCallResult, ToolInfo,
    ToolsListResult, negotiate_protocol_version,
};
use crate::session::{ClientInfo, SessionManager};
use crate::tool::{Content, ToolRegistry, ToolResult, call_guarded};

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
    instructions: Option<String>,
    tool_timeout: Option<Duration>,
}

impl std::fmt::Debug for MCPHandler {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("MCPHandler")
            .field("name", &self.name)
            .field("version", &self.version)
            .field("tools", &self.tools)
            .field("tool_timeout", &self.tool_timeout)
            .finish_non_exhaustive()
    }
}

impl MCPHandler {
    /// Create a new handler.
    pub fn new(name: impl Into<String>, version: impl Into<String>, tools: ToolRegistry) -> Self {
        Self {
            name: name.into(),
            version: version.into(),
            tools,
            sessions: SessionManager::new(),
            instructions: None,
            tool_timeout: None,
        }
    }

    /// Set the `instructions` string returned from `initialize` (usage hints
    /// the client may add to the model's context).
    pub fn with_instructions(mut self, instructions: impl Into<String>) -> Self {
        self.instructions = Some(instructions.into());
        self
    }

    /// Bound every tool execution by `timeout`. A tool that exceeds it is
    /// dropped (cancelled at its next `.await`) and reported as an `isError`
    /// result. Unbounded by default.
    pub fn with_tool_timeout(mut self, timeout: Duration) -> Self {
        self.tool_timeout = Some(timeout);
        self
    }

    /// The configured `initialize` instructions, if any.
    pub fn instructions(&self) -> Option<&str> {
        self.instructions.as_deref()
    }

    /// The configured per-tool timeout, if any.
    pub fn tool_timeout(&self) -> Option<Duration> {
        self.tool_timeout
    }

    /// Process a JSON-RPC request and return an optional response.
    ///
    /// Returns `None` for notifications (requests without an ID).
    pub async fn process_request(
        &self,
        request: &JsonRpcRequest,
        session_id: &Option<String>,
    ) -> Option<JsonRpcResponse> {
        self.dispatch(request, session_id.as_deref(), None).await
    }

    /// Handle raw bytes received from a transport.
    ///
    /// Returns the response to send back (a single response object or a batch
    /// array), or `None` when nothing must be sent (notifications, client
    /// responses, all-notification batches). Unparseable input yields a
    /// `-32700` Parse error response with a `null` id.
    pub async fn handle_raw(&self, raw: &[u8], session_id: Option<&str>) -> Option<Value> {
        self.handle_raw_with(raw, session_id, None).await
    }

    pub(crate) async fn handle_raw_with(
        &self,
        raw: &[u8],
        session_id: Option<&str>,
        notifier: Option<&Notifier>,
    ) -> Option<Value> {
        match serde_json::from_slice::<Value>(raw) {
            Ok(message) => {
                self.handle_message_with(message, session_id, notifier)
                    .await
            },
            Err(e) => {
                warn!("Failed to parse JSON-RPC message: {}", e);
                Some(response_value(parse_error(&e)))
            },
        }
    }

    /// Handle one parsed JSON-RPC message or a batch (JSON array).
    ///
    /// Batch members are processed concurrently and their responses returned
    /// as an array (notifications contribute nothing; an all-notification
    /// batch returns `None`). An empty batch is an Invalid Request.
    pub async fn handle_message(&self, message: Value, session_id: Option<&str>) -> Option<Value> {
        self.handle_message_with(message, session_id, None).await
    }

    pub(crate) async fn handle_message_with(
        &self,
        message: Value,
        session_id: Option<&str>,
        notifier: Option<&Notifier>,
    ) -> Option<Value> {
        match message {
            Value::Array(items) if items.is_empty() => Some(response_value(invalid_request(
                Value::Null,
                "Invalid Request: empty batch",
            ))),
            Value::Array(items) => {
                let responses: Vec<Value> = futures::future::join_all(
                    items
                        .into_iter()
                        .map(|m| self.handle_single(m, session_id, notifier)),
                )
                .await
                .into_iter()
                .flatten()
                .map(response_value)
                .collect();
                (!responses.is_empty()).then_some(Value::Array(responses))
            },
            single => self
                .handle_single(single, session_id, notifier)
                .await
                .map(response_value),
        }
    }

    /// Validate one JSON-RPC message and dispatch it.
    async fn handle_single(
        &self,
        message: Value,
        session_id: Option<&str>,
        notifier: Option<&Notifier>,
    ) -> Option<JsonRpcResponse> {
        let Value::Object(mut obj) = message else {
            return Some(invalid_request(
                Value::Null,
                "Invalid Request: message must be a JSON object",
            ));
        };

        let id = obj.remove("id");
        // MCP: ids MUST be a string or integer and MUST NOT be null.
        let id_ok = matches!(id, None | Some(Value::String(_) | Value::Number(_)));
        let reply_id = || match &id {
            Some(v @ (Value::String(_) | Value::Number(_))) => v.clone(),
            _ => Value::Null,
        };

        if !obj.contains_key("method") {
            if obj.contains_key("result") || obj.contains_key("error") {
                // A response to a server-initiated request. This server never
                // issues requests, so there is nothing to correlate it with.
                debug!("Ignoring JSON-RPC response from client (id={:?})", id);
                return None;
            }
            return Some(invalid_request(
                reply_id(),
                "Invalid Request: missing 'method'",
            ));
        }
        if !id_ok {
            return Some(invalid_request(
                Value::Null,
                "Invalid Request: 'id' must be a string or number",
            ));
        }
        if obj.get("jsonrpc").and_then(Value::as_str) != Some(JSONRPC_VERSION) {
            return Some(invalid_request(
                reply_id(),
                "Invalid Request: 'jsonrpc' must be \"2.0\"",
            ));
        }
        let Some(Value::String(method)) = obj.remove("method") else {
            return Some(invalid_request(
                reply_id(),
                "Invalid Request: 'method' must be a string",
            ));
        };
        let params = obj.remove("params").unwrap_or(Value::Null);
        if !(params.is_null() || params.is_object() || params.is_array()) {
            return Some(invalid_request(
                reply_id(),
                "Invalid Request: 'params' must be an object or array",
            ));
        }

        let request = JsonRpcRequest {
            jsonrpc: JSONRPC_VERSION.to_string(),
            method,
            params,
            id,
        };
        self.dispatch(&request, session_id, notifier).await
    }

    /// Route a validated request to its method handler.
    async fn dispatch(
        &self,
        request: &JsonRpcRequest,
        session_id: Option<&str>,
        notifier: Option<&Notifier>,
    ) -> Option<JsonRpcResponse> {
        let method = request.method.as_str();

        let Some(id) = request.id.clone() else {
            self.handle_notification(method, session_id).await;
            return None;
        };

        debug!("JSON-RPC request: method={}, id={}", method, id);

        let result = match method {
            "initialize" => self.initialize_impl(&request.params, session_id).await,
            "ping" => Ok(json!({})),
            "tools/list" => self.handle_tools_list().await,
            "tools/call" => self.call_tool_value(&request.params, &id, notifier).await,
            // Not advertised as capabilities, but answering with empty lists is
            // friendlier than an error for clients that probe unconditionally.
            "resources/list" => Ok(json!({"resources": []})),
            "resources/templates/list" => Ok(json!({"resourceTemplates": []})),
            "prompts/list" => Ok(json!({"prompts": []})),
            // Legacy clients that sent `initialized` as a request.
            "initialized" | "notifications/initialized" => Ok(json!({})),
            _ => {
                return Some(JsonRpcResponse::error_with_message(
                    id,
                    JsonRpcErrorCode::MethodNotFound,
                    format!("Method not found: {method}"),
                ));
            },
        };

        Some(match result {
            Ok(value) => JsonRpcResponse::success(id, value),
            Err(e) => JsonRpcResponse::from_mcp_error(id, &e),
        })
    }

    async fn handle_notification(&self, method: &str, session_id: Option<&str>) {
        match method {
            "notifications/initialized" | "initialized" => {
                debug!("Client sent initialized notification");
                if let Some(sid) = session_id {
                    self.sessions.update(sid, |s| s.mark_initialized()).await;
                }
            },
            // Cancellation needs to reach the in-flight task, so transports
            // that run requests concurrently (STDIO) act on it themselves.
            "notifications/cancelled" => debug!("Client cancelled a request"),
            other => debug!("Ignoring notification: {}", other),
        }
    }

    /// Handle the `initialize` method.
    pub async fn handle_initialize(
        &self,
        params: &Value,
        session_id: &Option<String>,
    ) -> Result<Value, MCPError> {
        self.initialize_impl(params, session_id.as_deref()).await
    }

    async fn initialize_impl(
        &self,
        params: &Value,
        session_id: Option<&str>,
    ) -> Result<Value, MCPError> {
        // Be lenient: a malformed `initialize` still gets a usable answer.
        let init_params = InitializeParams::deserialize(params).unwrap_or_else(|e| {
            warn!("Malformed initialize params ({}); using defaults", e);
            InitializeParams::default()
        });
        let negotiated = negotiate_protocol_version(&init_params.protocol_version);

        info!(
            "Initialize: client={}, requested protocol={}, negotiated={}",
            init_params
                .client_info
                .as_ref()
                .map_or("<unknown>", |c| c.name.as_str()),
            init_params.protocol_version,
            negotiated
        );

        if let Some(sid) = session_id {
            let client = init_params.client_info.as_ref().map(|c| ClientInfo {
                name: c.name.clone(),
                version: c.version.clone(),
            });
            self.sessions
                .update(sid, |s| {
                    s.protocol_version = negotiated.to_string();
                    if client.is_some() {
                        s.client_info = client;
                    }
                    s.mark_initialized();
                })
                .await;
        }

        let result = InitializeResult {
            protocol_version: negotiated.to_string(),
            server_info: ServerInfo {
                name: self.name.clone(),
                version: self.version.clone(),
            },
            capabilities: ServerCapabilities::default(),
            instructions: self.instructions.clone(),
        };

        Ok(serde_json::to_value(result)?)
    }

    /// Handle the `tools/list` method.
    ///
    /// The whole (name-sorted) list is returned in one page; `nextCursor` is
    /// never set.
    pub async fn handle_tools_list(&self) -> Result<Value, MCPError> {
        let tools: Vec<ToolInfo> = self
            .tools
            .iter()
            .map(|t| ToolInfo {
                name: t.name().to_string(),
                description: t.description().to_string(),
                input_schema: t.schema(),
                title: t.title().map(str::to_string),
                annotations: t.annotations(),
            })
            .collect();

        debug!("Returning {} tools", tools.len());

        Ok(serde_json::to_value(ToolsListResult {
            tools,
            next_cursor: None,
        })?)
    }

    /// Handle the `tools/call` method.
    ///
    /// Invalid params or an unknown tool name are `Err` (protocol errors).
    /// Everything that goes wrong *inside* the tool (an `Err` return, a panic,
    /// a timeout) is an `Ok` result with `isError: true`.
    pub async fn handle_tools_call(&self, params: &Value) -> Result<Value, MCPError> {
        self.call_tool_value(params, &Value::Null, None).await
    }

    async fn call_tool_value(
        &self,
        params: &Value,
        request_id: &Value,
        notifier: Option<&Notifier>,
    ) -> Result<Value, MCPError> {
        let call = ToolCallParams::deserialize(params)
            .map_err(|e| MCPError::InvalidParameters(format!("Invalid tools/call params: {e}")))?;

        let tool = self
            .tools
            .get(&call.name)
            .ok_or_else(|| MCPError::ToolNotFound(call.name.clone()))?;

        // Absent `arguments` -> empty object, so tools can always treat the
        // arguments as an object.
        let arguments = if call.arguments.is_null() {
            Value::Object(serde_json::Map::new())
        } else {
            call.arguments
        };

        info!("Calling tool: {}", call.name);
        let started = Instant::now();
        let ctx = RequestContext::new(request_id.clone(), params, notifier.cloned());
        let execution = ctx.scope(call_guarded(tool.as_ref(), arguments));

        let outcome = match self.tool_timeout {
            Some(limit) => match tokio::time::timeout(limit, execution).await {
                Ok(outcome) => outcome,
                Err(_) => {
                    warn!("Tool '{}' timed out after {:?}", call.name, limit);
                    Ok(ToolResult::error(format!(
                        "Tool '{}' timed out after {:.1}s",
                        call.name,
                        limit.as_secs_f64()
                    )))
                },
            },
            None => execution.await,
        };

        let result = outcome.unwrap_or_else(|e| {
            warn!("Tool '{}' failed: {}", call.name, e);
            ToolResult::error(e.to_string())
        });

        info!(
            "Tool '{}' finished in {} ms{}",
            call.name,
            started.elapsed().as_millis(),
            if result.is_error { " (error)" } else { "" }
        );

        Ok(serde_json::to_value(to_call_result(result))?)
    }
}

/// Convert a tool's result into the wire `CallToolResult`.
fn to_call_result(result: ToolResult) -> ToolCallResult {
    let content = result
        .content
        .into_iter()
        .map(|c| match c {
            Content::Text { text } => ContentBlock::Text { text },
            Content::Image { data, mime_type } => ContentBlock::Image { data, mime_type },
            Content::Resource { uri, mime_type } => ContentBlock::ResourceLink {
                name: resource_name(&uri),
                uri,
                mime_type: (!mime_type.is_empty()).then_some(mime_type),
            },
        })
        .collect();
    ToolCallResult {
        content,
        is_error: result.is_error,
    }
}

/// A display name for a resource link: the last non-empty path segment of the
/// URI, falling back to the whole URI.
fn resource_name(uri: &str) -> String {
    uri.split(['/', '\\'])
        .rfind(|s| !s.is_empty())
        .unwrap_or(uri)
        .to_string()
}

fn invalid_request(id: Value, message: &str) -> JsonRpcResponse {
    JsonRpcResponse::error_with_message(id, JsonRpcErrorCode::InvalidRequest, message)
}

fn parse_error(e: &serde_json::Error) -> JsonRpcResponse {
    JsonRpcResponse::error_with_message(
        Value::Null,
        JsonRpcErrorCode::ParseError,
        format!("Parse error: {e}"),
    )
}

/// Serialize a response. Cannot fail for this type (string keys, JSON values),
/// but degrade to a hand-built internal error instead of panicking.
pub(crate) fn response_value(resp: JsonRpcResponse) -> Value {
    serde_json::to_value(&resp).unwrap_or_else(|_| {
        json!({
            "jsonrpc": JSONRPC_VERSION,
            "id": resp.id,
            "error": {"code": JsonRpcErrorCode::InternalError.code(), "message": "Internal error"}
        })
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tool::{Tool, ToolAnnotations, ToolResult};
    use async_trait::async_trait;

    struct TestTool;

    #[async_trait]
    impl Tool for TestTool {
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
        async fn execute(&self, args: Value) -> crate::error::Result<ToolResult> {
            assert!(args.is_object(), "arguments must default to an object");
            Ok(ToolResult::text("test result"))
        }
        fn title(&self) -> Option<&str> {
            Some("Test Tool")
        }
        fn annotations(&self) -> Option<ToolAnnotations> {
            Some(ToolAnnotations::read_only())
        }
    }

    struct PanicTool;

    #[async_trait]
    impl Tool for PanicTool {
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

    struct FailTool;

    #[async_trait]
    impl Tool for FailTool {
        fn name(&self) -> &str {
            "fail_tool"
        }
        fn description(&self) -> &str {
            "Always returns Err"
        }
        fn schema(&self) -> Value {
            json!({"type": "object"})
        }
        async fn execute(&self, _args: Value) -> crate::error::Result<ToolResult> {
            Err(MCPError::invalid_params("'x' is required"))
        }
    }

    struct SlowTool;

    #[async_trait]
    impl Tool for SlowTool {
        fn name(&self) -> &str {
            "slow_tool"
        }
        fn description(&self) -> &str {
            "Sleeps"
        }
        fn schema(&self) -> Value {
            json!({"type": "object"})
        }
        async fn execute(&self, _args: Value) -> crate::error::Result<ToolResult> {
            tokio::time::sleep(Duration::from_secs(30)).await;
            Ok(ToolResult::text("done"))
        }
    }

    struct ResourceTool;

    #[async_trait]
    impl Tool for ResourceTool {
        fn name(&self) -> &str {
            "resource_tool"
        }
        fn description(&self) -> &str {
            "Returns a resource"
        }
        fn schema(&self) -> Value {
            json!({"type": "object"})
        }
        async fn execute(&self, _args: Value) -> crate::error::Result<ToolResult> {
            Ok(ToolResult::with_content(vec![Content::resource(
                "file:///out/render.png",
                "image/png",
            )]))
        }
    }

    fn make_handler() -> MCPHandler {
        let mut tools = ToolRegistry::new();
        tools.register(TestTool);
        tools.register(PanicTool);
        tools.register(FailTool);
        tools.register(SlowTool);
        tools.register(ResourceTool);
        MCPHandler::new("test-server", "1.0.0", tools)
    }

    async fn rpc(handler: &MCPHandler, raw: &str) -> Option<Value> {
        handler.handle_raw(raw.as_bytes(), None).await
    }

    #[tokio::test]
    async fn test_initialize() {
        let handler = make_handler();
        let req = JsonRpcRequest::new("initialize", json!({}), 1);
        let resp = handler.process_request(&req, &None).await.unwrap();
        assert!(resp.result.is_some());
        let result = resp.result.unwrap();
        assert_eq!(result["serverInfo"]["name"], "test-server");
        // Only the tools capability is advertised.
        assert_eq!(
            result["capabilities"],
            json!({"tools": {"listChanged": false}})
        );
        assert!(result.get("instructions").is_none());
    }

    #[tokio::test]
    async fn initialize_negotiates_version() {
        let handler = make_handler();
        for (requested, expected) in [
            ("2025-06-18", "2025-06-18"),
            ("2024-11-05", "2024-11-05"),
            ("2099-01-01", crate::jsonrpc::LATEST_PROTOCOL_VERSION),
        ] {
            let raw = json!({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": requested, "capabilities": {}, "clientInfo": {"name": "c", "version": "1"}}});
            let resp = handler.handle_message(raw, None).await.unwrap();
            assert_eq!(resp["result"]["protocolVersion"], expected);
        }
    }

    #[tokio::test]
    async fn initialize_updates_session_and_returns_instructions() {
        let handler = make_handler().with_instructions("Use the tools wisely");
        let sid = handler.sessions.create_session("pending").await;
        let raw = json!({"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "clientInfo": {"name": "claude"}}});
        let resp = handler.handle_message(raw, Some(&sid)).await.unwrap();
        assert_eq!(resp["result"]["instructions"], "Use the tools wisely");
        let session = handler.sessions.get(&sid).await.unwrap();
        assert_eq!(session.protocol_version, "2025-03-26");
        assert!(session.initialized);
        assert_eq!(session.client_info.unwrap().name, "claude");
    }

    #[tokio::test]
    async fn test_tools_list() {
        let handler = make_handler();
        let req = JsonRpcRequest::new("tools/list", json!({}), 1);
        let resp = handler.process_request(&req, &None).await.unwrap();
        let result = resp.result.unwrap();
        let tools = result["tools"].as_array().unwrap();
        assert_eq!(tools.len(), 5);
        // Sorted by name, deterministic.
        let names: Vec<_> = tools.iter().map(|t| t["name"].as_str().unwrap()).collect();
        let mut sorted = names.clone();
        sorted.sort_unstable();
        assert_eq!(names, sorted);
        let test_tool = tools.iter().find(|t| t["name"] == "test_tool").unwrap();
        assert_eq!(test_tool["title"], "Test Tool");
        assert_eq!(test_tool["annotations"], json!({"readOnlyHint": true}));
        assert!(test_tool["inputSchema"].is_object());
        let panic_tool = tools.iter().find(|t| t["name"] == "panic_tool").unwrap();
        assert!(panic_tool.get("title").is_none());
        assert!(panic_tool.get("annotations").is_none());
        assert!(result.get("nextCursor").is_none());
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
        assert_eq!(resp2.result.unwrap(), json!({}));
    }

    #[tokio::test]
    async fn tool_err_is_reported_as_tool_error_result() {
        let handler = make_handler();
        let resp = rpc(
            &handler,
            r#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"fail_tool"}}"#,
        )
        .await
        .unwrap();
        assert!(resp.get("error").is_none(), "{resp}");
        assert_eq!(resp["result"]["isError"], true);
        assert_eq!(
            resp["result"]["content"][0]["text"],
            "Invalid parameters: 'x' is required"
        );
    }

    #[tokio::test]
    async fn tool_timeout_becomes_tool_error() {
        let handler = make_handler().with_tool_timeout(Duration::from_millis(20));
        let resp = rpc(
            &handler,
            r#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"slow_tool"}}"#,
        )
        .await
        .unwrap();
        assert_eq!(resp["result"]["isError"], true);
        assert!(
            resp["result"]["content"][0]["text"]
                .as_str()
                .unwrap()
                .contains("timed out")
        );
    }

    #[tokio::test]
    async fn resource_content_is_emitted_as_resource_link() {
        let handler = make_handler();
        let resp = rpc(
            &handler,
            r#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"resource_tool"}}"#,
        )
        .await
        .unwrap();
        assert_eq!(
            resp["result"]["content"][0],
            json!({"type": "resource_link", "uri": "file:///out/render.png", "name": "render.png", "mimeType": "image/png"})
        );
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
        assert!(result.get("isError").is_none());
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
        let err = resp.error.unwrap();
        assert_eq!(err.code, -32602);
        assert!(err.message.contains("nonexistent"));
    }

    #[tokio::test]
    async fn tools_call_with_bad_params_is_invalid_params() {
        let handler = make_handler();
        let resp = rpc(
            &handler,
            r#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"arguments":{}}}"#,
        )
        .await
        .unwrap();
        assert_eq!(resp["error"]["code"], -32602);
    }

    #[tokio::test]
    async fn test_method_not_found() {
        let handler = make_handler();
        let req = JsonRpcRequest::new("unknown/method", json!({}), 1);
        let resp = handler.process_request(&req, &None).await.unwrap();
        assert!(resp.error.is_some());
        let err = resp.error.unwrap();
        assert_eq!(err.code, -32601);
        assert!(err.message.contains("unknown/method"));

        // completion/complete is not advertised, so it is not found either.
        let resp = rpc(
            &handler,
            r#"{"jsonrpc":"2.0","id":2,"method":"completion/complete","params":{}}"#,
        )
        .await
        .unwrap();
        assert_eq!(resp["error"]["code"], -32601);
    }

    #[tokio::test]
    async fn test_notification_no_response() {
        let handler = make_handler();
        let req = JsonRpcRequest::notification("initialized", json!({}));
        let resp = handler.process_request(&req, &None).await;
        assert!(resp.is_none());

        for raw in [
            r#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#,
            r#"{"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":1}}"#,
            r#"{"jsonrpc":"2.0","method":"unknown/notification"}"#,
            // A notification for a request-only method is still not answered.
            r#"{"jsonrpc":"2.0","method":"tools/list"}"#,
        ] {
            assert!(rpc(&handler, raw).await.is_none(), "{raw}");
        }
    }

    #[tokio::test]
    async fn test_ping() {
        let handler = make_handler();
        let req = JsonRpcRequest::new("ping", json!({}), 1);
        let resp = handler.process_request(&req, &None).await.unwrap();
        assert_eq!(resp.result.unwrap(), json!({}));
        assert_eq!(resp.id, json!(1));
    }

    #[tokio::test]
    async fn string_ids_are_echoed() {
        let handler = make_handler();
        let resp = rpc(&handler, r#"{"jsonrpc":"2.0","id":"abc","method":"ping"}"#)
            .await
            .unwrap();
        assert_eq!(resp["id"], "abc");
        assert_eq!(resp["result"], json!({}));
    }

    #[tokio::test]
    async fn parse_error_has_null_id() {
        let handler = make_handler();
        let resp = rpc(&handler, "{not json").await.unwrap();
        assert_eq!(resp["error"]["code"], -32700);
        assert_eq!(resp["id"], Value::Null);
    }

    #[tokio::test]
    async fn invalid_requests_are_rejected() {
        let handler = make_handler();
        let cases = [
            (r#"42"#, Value::Null),
            (r#"{"jsonrpc":"2.0","id":1}"#, json!(1)),
            (r#"{"jsonrpc":"1.0","id":2,"method":"ping"}"#, json!(2)),
            (r#"{"id":3,"method":"ping"}"#, json!(3)),
            (
                r#"{"jsonrpc":"2.0","id":null,"method":"ping"}"#,
                Value::Null,
            ),
            (
                r#"{"jsonrpc":"2.0","id":{"a":1},"method":"ping"}"#,
                Value::Null,
            ),
            (r#"{"jsonrpc":"2.0","id":4,"method":5}"#, json!(4)),
            (
                r#"{"jsonrpc":"2.0","id":5,"method":"ping","params":"x"}"#,
                json!(5),
            ),
        ];
        for (raw, expected_id) in cases {
            let resp = rpc(&handler, raw).await.unwrap();
            assert_eq!(resp["error"]["code"], -32600, "{raw}");
            assert_eq!(resp["id"], expected_id, "{raw}");
        }
    }

    #[tokio::test]
    async fn client_responses_are_ignored() {
        let handler = make_handler();
        assert!(
            rpc(&handler, r#"{"jsonrpc":"2.0","id":9,"result":{}}"#)
                .await
                .is_none()
        );
        assert!(
            rpc(
                &handler,
                r#"{"jsonrpc":"2.0","id":9,"error":{"code":1,"message":"x"}}"#
            )
            .await
            .is_none()
        );
    }

    #[tokio::test]
    async fn batch_handling() {
        let handler = make_handler();

        // Empty batch -> single Invalid Request.
        let resp = rpc(&handler, "[]").await.unwrap();
        assert_eq!(resp["error"]["code"], -32600);

        // All notifications -> nothing.
        let resp = rpc(
            &handler,
            r#"[{"jsonrpc":"2.0","method":"notifications/initialized"}]"#,
        )
        .await;
        assert!(resp.is_none());

        // Mixed: responses only for requests and invalid members, in order.
        let resp = rpc(
            &handler,
            r#"[
                {"jsonrpc":"2.0","id":1,"method":"ping"},
                {"jsonrpc":"2.0","method":"notifications/initialized"},
                1,
                {"jsonrpc":"2.0","id":2,"method":"nope"}
            ]"#,
        )
        .await
        .unwrap();
        let arr = resp.as_array().unwrap();
        assert_eq!(arr.len(), 3);
        assert_eq!(arr[0]["id"], 1);
        assert_eq!(arr[0]["result"], json!({}));
        assert_eq!(arr[1]["error"]["code"], -32600);
        assert_eq!(arr[2]["error"]["code"], -32601);
    }

    #[tokio::test]
    async fn empty_capability_lists() {
        let handler = make_handler();
        let resp = rpc(
            &handler,
            r#"{"jsonrpc":"2.0","id":1,"method":"resources/list"}"#,
        )
        .await
        .unwrap();
        assert_eq!(resp["result"], json!({"resources": []}));
        let resp = rpc(
            &handler,
            r#"{"jsonrpc":"2.0","id":1,"method":"prompts/list"}"#,
        )
        .await
        .unwrap();
        assert_eq!(resp["result"], json!({"prompts": []}));
    }

    #[test]
    fn resource_names() {
        assert_eq!(resource_name("file:///a/b/c.png"), "c.png");
        assert_eq!(resource_name("https://x.test/dir/"), "dir");
        assert_eq!(resource_name("plain"), "plain");
        assert_eq!(resource_name(""), "");
    }
}
