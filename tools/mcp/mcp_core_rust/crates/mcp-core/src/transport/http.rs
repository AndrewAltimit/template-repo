//! HTTP transport implementation using Axum.
//!
//! Serves the MCP Streamable HTTP transport (JSON responses, no server-sent
//! event stream) plus a few convenience endpoints:
//!
//! | Endpoint | Method | Purpose |
//! |----------|--------|---------|
//! | `/mcp`, `/messages`, `/mcp/rpc` | POST | JSON-RPC (single message or batch) |
//! | `/mcp`, `/messages` | DELETE | Terminate the session named by `Mcp-Session-Id` |
//! | `/mcp` | GET | `405`: this server does not offer an SSE stream |
//! | `/messages` | GET | Server info JSON (`405` when an SSE stream is requested) |
//! | `/health` | GET | Health check |
//! | `/mcp/tools` | GET | Tool list (simple API) |
//! | `/mcp/execute`, `/tools/execute` | POST | Execute a tool (simple API) |
//! | `/.well-known/mcp`, `/mcp/capabilities` | GET | Discovery |
//! | `/mcp/initialize` | POST | Create a session (simple API) |
//!
//! JSON-RPC POST semantics: a body containing only notifications/responses is
//! answered with `202 Accepted` and no body; unparseable JSON with `400` and a
//! JSON-RPC Parse error; otherwise `200` with the response(s). A session id is
//! issued in the `Mcp-Session-Id` header on `initialize`.

use axum::{
    Router,
    body::Bytes,
    extract::{Json, State},
    http::{HeaderMap, HeaderName, HeaderValue, StatusCode, header},
    response::{IntoResponse, Response},
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};
use tracing::debug;

use crate::error::MCPError;
use crate::session::SessionManager;
use crate::tool::ToolRegistry;
use crate::transport::handler::MCPHandler;

/// Session header defined by the Streamable HTTP transport.
const SESSION_HEADER: &str = "mcp-session-id";

/// Shared state for HTTP handlers
pub struct HttpState {
    /// The shared MCP protocol handler
    pub handler: MCPHandler,
}

impl HttpState {
    /// Create a new HTTP state.
    pub fn new(name: String, version: String, tools: ToolRegistry) -> Self {
        Self {
            handler: MCPHandler::new(name, version, tools),
        }
    }

    /// Create HTTP state around an already-configured handler (e.g. one with
    /// instructions or a tool timeout).
    pub fn from_handler(handler: MCPHandler) -> Self {
        Self { handler }
    }

    /// Get the server name.
    pub fn name(&self) -> &str {
        &self.handler.name
    }

    /// Get the server version.
    pub fn version(&self) -> &str {
        &self.handler.version
    }

    /// Get the session manager.
    pub fn sessions(&self) -> &SessionManager {
        &self.handler.sessions
    }
}

/// HTTP transport for MCP server
pub struct HttpTransport;

impl HttpTransport {
    /// Create an Axum router with all MCP endpoints
    pub fn router(state: Arc<HttpState>) -> Router {
        let cors = CorsLayer::new()
            .allow_origin(Any)
            .allow_methods(Any)
            .allow_headers(Any)
            // Browser clients must be able to read the session id.
            .expose_headers([HeaderName::from_static(SESSION_HEADER)]);

        Router::new()
            // Health check
            .route("/health", get(health_handler))
            // MCP tool operations (simple API)
            .route("/mcp/tools", get(list_tools_handler))
            .route("/mcp/execute", post(execute_tool_handler))
            .route("/tools/execute", post(execute_tool_handler)) // Legacy
            // MCP protocol discovery
            .route("/.well-known/mcp", get(discovery_handler))
            .route("/mcp/initialize", post(initialize_simple_handler))
            .route("/mcp/capabilities", get(capabilities_handler))
            // Streamable HTTP transport
            .route(
                "/messages",
                get(messages_get_handler)
                    .post(jsonrpc_handler)
                    .delete(delete_session_handler),
            )
            .route(
                "/mcp",
                get(mcp_get_handler)
                    .post(jsonrpc_handler)
                    .delete(delete_session_handler)
                    .options(options_handler),
            )
            .route("/mcp/rpc", post(jsonrpc_handler))
            .with_state(state)
            .layer(cors)
    }
}

// ============================================================================
// Response types
// ============================================================================

/// Health check response
#[derive(Serialize, Deserialize)]
struct HealthResponse {
    status: String,
    server: String,
    version: String,
}

/// Tool execution request (simple API)
#[derive(Deserialize)]
struct ToolRequest {
    tool: String,
    #[serde(default)]
    arguments: Option<Value>,
    #[serde(default)]
    parameters: Option<Value>,
}

impl ToolRequest {
    fn into_args(self) -> Value {
        self.arguments
            .or(self.parameters)
            .unwrap_or_else(|| json!({}))
    }
}

/// Tool execution response (simple API)
#[derive(Serialize)]
struct ToolResponse {
    success: bool,
    result: Option<Value>,
    error: Option<String>,
}

// ============================================================================
// Handlers
// ============================================================================

async fn health_handler(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    Json(HealthResponse {
        status: "healthy".to_string(),
        server: state.name().to_string(),
        version: state.version().to_string(),
    })
}

async fn list_tools_handler(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    let tools: Vec<_> = state
        .handler
        .tools
        .list()
        .into_iter()
        .map(|t| {
            json!({
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            })
        })
        .collect();

    Json(json!({ "tools": tools }))
}

async fn execute_tool_handler(
    State(state): State<Arc<HttpState>>,
    Json(request): Json<ToolRequest>,
) -> impl IntoResponse {
    let name = request.tool.clone();
    // Same panic boundary as the JSON-RPC path.
    match state.handler.tools.call(&name, request.into_args()).await {
        Ok(result) => (
            StatusCode::OK,
            Json(ToolResponse {
                success: !result.is_error,
                result: Some(json!(result)),
                error: None,
            }),
        ),
        Err(MCPError::ToolNotFound(_)) => (
            StatusCode::NOT_FOUND,
            Json(ToolResponse {
                success: false,
                result: None,
                error: Some(format!("Tool '{name}' not found")),
            }),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ToolResponse {
                success: false,
                result: None,
                error: Some(e.to_string()),
            }),
        ),
    }
}

async fn discovery_handler(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    Json(json!({
        "mcp_version": "1.0",
        "server_name": state.name(),
        "server_version": state.version(),
        "protocol_versions": crate::jsonrpc::SUPPORTED_PROTOCOL_VERSIONS,
        "capabilities": {
            "tools": true,
            "prompts": false,
            "resources": false,
        },
        "endpoints": {
            "tools": "/mcp/tools",
            "execute": "/mcp/execute",
            "initialize": "/mcp/initialize",
            "capabilities": "/mcp/capabilities",
            "jsonrpc": "/mcp",
        }
    }))
}

async fn initialize_simple_handler(
    State(state): State<Arc<HttpState>>,
    Json(_request): Json<Value>,
) -> impl IntoResponse {
    // Create and register session with the session manager
    let session_id = state.sessions().create_session("simple-api").await;

    Json(json!({
        "session_id": session_id,
        "server": {
            "name": state.name(),
            "version": state.version(),
        },
        "capabilities": {
            "tools": true,
            "prompts": false,
            "resources": false,
        }
    }))
}

async fn capabilities_handler(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    let tool_names = state.handler.tools.names();

    Json(json!({
        "capabilities": {
            "tools": {
                "list": tool_names,
                "count": tool_names.len(),
            },
            "prompts": {
                "supported": false,
            },
            "resources": {
                "supported": false,
            }
        }
    }))
}

fn wants_event_stream(headers: &HeaderMap) -> bool {
    headers
        .get_all(header::ACCEPT)
        .iter()
        .filter_map(|v| v.to_str().ok())
        .any(|v| v.contains("text/event-stream"))
}

/// `405 Method Not Allowed`: the Streamable HTTP spec's answer to a GET when
/// the server does not offer a server-to-client SSE stream. Clients (e.g. the
/// official SDKs) treat this as "no stream" and carry on with POST.
fn sse_not_supported() -> Response {
    (
        StatusCode::METHOD_NOT_ALLOWED,
        [(header::ALLOW, "POST, DELETE")],
    )
        .into_response()
}

async fn mcp_get_handler() -> Response {
    sse_not_supported()
}

async fn messages_get_handler(State(state): State<Arc<HttpState>>, headers: HeaderMap) -> Response {
    if wants_event_stream(&headers) {
        return sse_not_supported();
    }
    Json(json!({
        "protocol": "mcp",
        "version": "1.0",
        "server": {
            "name": state.name(),
            "version": state.version(),
            "description": format!("{} MCP Server", state.name()),
        },
        "transport": {
            "type": "streamable-http",
            "endpoint": "/messages",
        }
    }))
    .into_response()
}

fn session_from_headers(headers: &HeaderMap) -> Option<String> {
    headers
        .get(SESSION_HEADER)
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(String::from)
}

fn is_initialize(message: &Value) -> bool {
    message.get("method").and_then(Value::as_str) == Some("initialize")
}

/// JSON-RPC over HTTP POST (Streamable HTTP transport, JSON response mode).
async fn jsonrpc_handler(
    State(state): State<Arc<HttpState>>,
    headers: HeaderMap,
    body: Bytes,
) -> Response {
    let session_id = session_from_headers(&headers);
    debug!(
        "JSON-RPC POST: session={:?}, {} bytes",
        session_id,
        body.len()
    );

    // Parse the body ourselves so bad JSON (or a missing Content-Type) gets a
    // JSON-RPC Parse error instead of axum's plain-text rejection.
    let message = match serde_json::from_slice::<Value>(&body) {
        Ok(message) => message,
        Err(_) => {
            let resp = state.handler.handle_raw(&body, None).await;
            return json_response(StatusCode::BAD_REQUEST, resp.unwrap_or(Value::Null), None);
        },
    };

    // Issue a session id when a client initializes without one.
    let session_id = match session_id {
        None if is_initialize(&message) => Some(
            state
                .sessions()
                .create_session(crate::jsonrpc::LATEST_PROTOCOL_VERSION)
                .await,
        ),
        other => other,
    };

    match state
        .handler
        .handle_message(message, session_id.as_deref())
        .await
    {
        Some(resp) => json_response(StatusCode::OK, resp, session_id),
        // Only notifications/responses: acknowledged, no body.
        None => with_session(StatusCode::ACCEPTED.into_response(), session_id),
    }
}

/// Explicit session termination (`DELETE` with `Mcp-Session-Id`).
async fn delete_session_handler(
    State(state): State<Arc<HttpState>>,
    headers: HeaderMap,
) -> StatusCode {
    match session_from_headers(&headers) {
        None => StatusCode::BAD_REQUEST,
        Some(sid) => match state.sessions().remove(&sid).await {
            Some(_) => {
                debug!("Session terminated by client: {}", sid);
                StatusCode::NO_CONTENT
            },
            None => StatusCode::NOT_FOUND,
        },
    }
}

async fn options_handler() -> impl IntoResponse {
    (
        StatusCode::OK,
        [
            (header::ACCESS_CONTROL_ALLOW_ORIGIN, "*"),
            (
                header::ACCESS_CONTROL_ALLOW_METHODS,
                "GET, POST, DELETE, OPTIONS",
            ),
            (
                header::ACCESS_CONTROL_ALLOW_HEADERS,
                "Content-Type, Authorization, Mcp-Session-Id, Mcp-Protocol-Version, Mcp-Response-Mode",
            ),
            (header::ACCESS_CONTROL_MAX_AGE, "86400"),
        ],
    )
}

fn with_session(mut response: Response, session_id: Option<String>) -> Response {
    if let Some(value) = session_id.and_then(|sid| HeaderValue::from_str(&sid).ok()) {
        response
            .headers_mut()
            .insert(HeaderName::from_static(SESSION_HEADER), value);
    }
    response
}

fn json_response(status: StatusCode, value: Value, session_id: Option<String>) -> Response {
    with_session((status, Json(value)).into_response(), session_id)
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
        async fn execute(&self, args: Value) -> crate::error::Result<ToolResult> {
            if args.get("panic").is_some() {
                panic!("http boom");
            }
            Ok(ToolResult::text("test result"))
        }
    }

    fn server() -> (axum_test::TestServer, Arc<HttpState>) {
        let mut tools = ToolRegistry::new();
        tools.register(TestTool);
        let state = Arc::new(HttpState::new(
            "test-server".to_string(),
            "1.0.0".to_string(),
            tools,
        ));
        let app = HttpTransport::router(Arc::clone(&state));
        (axum_test::TestServer::new(app).unwrap(), state)
    }

    #[tokio::test]
    async fn test_health_endpoint() {
        let (client, _) = server();

        let response = client.get("/health").await;
        response.assert_status_ok();

        let body: HealthResponse = response.json();
        assert_eq!(body.status, "healthy");
        assert_eq!(body.server, "test-server");
    }

    #[tokio::test]
    async fn initialize_issues_session_and_records_version() {
        let (client, state) = server();
        let response = client
            .post("/mcp")
            .json(&json!({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "clientInfo": {"name": "t"}}}))
            .await;
        response.assert_status_ok();
        let sid = response
            .headers()
            .get(SESSION_HEADER)
            .expect("session header")
            .to_str()
            .unwrap()
            .to_string();
        let body: Value = response.json();
        assert_eq!(body["result"]["protocolVersion"], "2025-06-18");
        let session = state.sessions().get(&sid).await.unwrap();
        assert_eq!(session.protocol_version, "2025-06-18");

        // Terminate it.
        let response = client
            .delete("/mcp")
            .add_header(SESSION_HEADER, sid.as_str())
            .await;
        response.assert_status(StatusCode::NO_CONTENT);
        assert!(!state.sessions().exists(&sid).await);
        let response = client
            .delete("/mcp")
            .add_header(SESSION_HEADER, sid.as_str())
            .await;
        response.assert_status(StatusCode::NOT_FOUND);
        client
            .delete("/mcp")
            .await
            .assert_status(StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn notifications_get_202_without_body() {
        let (client, _) = server();
        for body in [
            json!({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json!([{"jsonrpc": "2.0", "method": "notifications/initialized"}]),
        ] {
            let response = client.post("/mcp").json(&body).await;
            response.assert_status(StatusCode::ACCEPTED);
            assert!(response.as_bytes().is_empty());
        }
    }

    #[tokio::test]
    async fn invalid_json_is_400_parse_error() {
        let (client, _) = server();
        let response = client
            .post("/mcp")
            .content_type("application/json")
            .bytes(Bytes::from_static(b"{oops"))
            .await;
        response.assert_status(StatusCode::BAD_REQUEST);
        let body: Value = response.json();
        assert_eq!(body["error"]["code"], -32700);
        assert!(body["id"].is_null());
    }

    #[tokio::test]
    async fn batch_and_tool_call_over_http() {
        let (client, _) = server();
        let response = client
            .post("/messages")
            .json(&json!([
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "test_tool", "arguments": {}}}
            ]))
            .await;
        response.assert_status_ok();
        let body: Value = response.json();
        let arr = body.as_array().unwrap();
        assert_eq!(arr.len(), 2);
        assert_eq!(arr[1]["result"]["content"][0]["text"], "test result");
    }

    #[tokio::test]
    async fn get_mcp_is_405() {
        let (client, _) = server();
        client
            .get("/mcp")
            .add_header("accept", "text/event-stream")
            .await
            .assert_status(StatusCode::METHOD_NOT_ALLOWED);
        client
            .get("/messages")
            .add_header("accept", "text/event-stream")
            .await
            .assert_status(StatusCode::METHOD_NOT_ALLOWED);
        client.get("/messages").await.assert_status_ok();
    }

    #[tokio::test]
    async fn simple_execute_api_catches_panics_and_missing_tools() {
        let (client, _) = server();
        let response = client
            .post("/mcp/execute")
            .json(&json!({"tool": "test_tool", "arguments": {"panic": true}}))
            .await;
        response.assert_status_ok();
        let body: Value = response.json();
        assert_eq!(body["success"], false);
        assert!(
            body["result"]["content"][0]["text"]
                .as_str()
                .unwrap()
                .contains("http boom")
        );

        let response = client
            .post("/mcp/execute")
            .json(&json!({"tool": "missing", "parameters": {}}))
            .await;
        response.assert_status(StatusCode::NOT_FOUND);
    }
}
