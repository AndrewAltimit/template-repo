//! HTTP transport implementation using Axum.

use axum::{
    Router,
    extract::{Json, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, options, post},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};
use tracing::info;

use crate::error::JsonRpcErrorCode;
use crate::jsonrpc::{JsonRpcRequest, JsonRpcResponse};
use crate::session::SessionManager;
use crate::tool::ToolRegistry;
use crate::transport::handler::MCPHandler;

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
            .allow_headers(Any);

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
            // HTTP Stream Transport (MCP 2024-11-05)
            .route("/messages", get(messages_get_handler))
            .route("/messages", post(messages_post_handler))
            // JSON-RPC endpoints
            .route("/mcp", get(mcp_sse_handler))
            .route("/mcp", post(jsonrpc_handler))
            .route("/mcp", options(options_handler))
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
    fn get_args(&self) -> Value {
        self.arguments
            .clone()
            .or_else(|| self.parameters.clone())
            .unwrap_or(json!({}))
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
    let tool = match state.handler.tools.get(&request.tool) {
        Some(t) => t,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(ToolResponse {
                    success: false,
                    result: None,
                    error: Some(format!("Tool '{}' not found", request.tool)),
                }),
            );
        },
    };

    match tool.execute(request.get_args()).await {
        Ok(result) => (
            StatusCode::OK,
            Json(ToolResponse {
                success: !result.is_error,
                result: Some(json!(result)),
                error: None,
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
    let tool_names: Vec<_> = state.handler.tools.names().into_iter().collect();

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

async fn messages_get_handler(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
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
}

async fn messages_post_handler(
    State(state): State<Arc<HttpState>>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Response {
    let session_id = headers
        .get("Mcp-Session-Id")
        .and_then(|v| v.to_str().ok())
        .map(String::from);

    let response_mode = headers
        .get("Mcp-Response-Mode")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("batch");

    info!(
        "Messages request: session={:?}, mode={}",
        session_id, response_mode
    );

    // Handle batch requests
    if let Some(requests) = body.as_array() {
        let mut responses = Vec::new();
        for req in requests {
            match serde_json::from_value::<JsonRpcRequest>(req.clone()) {
                Ok(request) => {
                    if let Some(resp) = state.handler.process_request(&request, &session_id).await {
                        responses.push(resp);
                    }
                },
                Err(e) => {
                    let id = req.get("id").cloned().unwrap_or(json!(null));
                    responses.push(JsonRpcResponse::error_with_code(
                        id,
                        JsonRpcErrorCode::InvalidRequest,
                        Some(format!("Invalid request in batch: {}", e)),
                    ));
                },
            }
        }
        return json_response_with_session(json!(responses), session_id);
    }

    // Handle single request
    match serde_json::from_value::<JsonRpcRequest>(body) {
        Ok(request) => {
            // Generate session ID for initialize requests
            let effective_session = if request.method == "initialize" && session_id.is_none() {
                Some(state.sessions().create_session("2024-11-05").await)
            } else {
                session_id
            };

            match state
                .handler
                .process_request(&request, &effective_session)
                .await
            {
                Some(resp) => json_response_with_session(json!(resp), effective_session),
                None => {
                    // Notification - no response body
                    let mut builder = Response::builder().status(StatusCode::ACCEPTED);
                    if let Some(sid) = effective_session {
                        builder = builder.header("Mcp-Session-Id", sid);
                    }
                    builder.body(axum::body::Body::empty()).unwrap()
                },
            }
        },
        Err(e) => {
            let error_resp = JsonRpcResponse::error_with_code(
                json!(null),
                JsonRpcErrorCode::ParseError,
                Some(e.to_string()),
            );
            json_response_with_session(json!(error_resp), session_id)
        },
    }
}

async fn mcp_sse_handler(State(_state): State<Arc<HttpState>>) -> impl IntoResponse {
    // SSE endpoint - simplified for now
    (
        StatusCode::OK,
        [("Content-Type", "text/event-stream")],
        "data: {\"type\": \"connection\", \"status\": \"connected\"}\n\n",
    )
}

async fn jsonrpc_handler(
    State(state): State<Arc<HttpState>>,
    headers: HeaderMap,
    Json(body): Json<Value>,
) -> Response {
    messages_post_handler(State(state), headers, Json(body)).await
}

async fn options_handler() -> impl IntoResponse {
    Response::builder()
        .status(StatusCode::OK)
        .header("Access-Control-Allow-Origin", "*")
        .header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        .header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, Mcp-Session-Id, Mcp-Response-Mode",
        )
        .header("Access-Control-Max-Age", "86400")
        .body(axum::body::Body::empty())
        .unwrap()
}

fn json_response_with_session(value: Value, session_id: Option<String>) -> Response {
    let mut builder = Response::builder()
        .status(StatusCode::OK)
        .header("Content-Type", "application/json");

    if let Some(sid) = session_id {
        builder = builder.header("Mcp-Session-Id", sid);
    }

    builder
        .body(axum::body::Body::from(value.to_string()))
        .unwrap()
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

    #[tokio::test]
    async fn test_health_endpoint() {
        let mut tools = ToolRegistry::new();
        tools.register(TestTool);

        let state = Arc::new(HttpState::new(
            "test-server".to_string(),
            "1.0.0".to_string(),
            tools,
        ));

        let app = HttpTransport::router(state);
        let client = axum_test::TestServer::new(app).unwrap();

        let response = client.get("/health").await;
        response.assert_status_ok();

        let body: HealthResponse = response.json();
        assert_eq!(body.status, "healthy");
        assert_eq!(body.server, "test-server");
    }
}
