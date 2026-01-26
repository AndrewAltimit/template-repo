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

use crate::error::{JsonRpcErrorCode, MCPError};
use crate::jsonrpc::{
    ContentBlock, InitializeParams, InitializeResult, JsonRpcRequest, JsonRpcResponse,
    ServerCapabilities, ServerInfo, ToolCallParams, ToolCallResult, ToolInfo, ToolsListResult,
};
use crate::session::{ClientInfo, SessionManager};
use crate::tool::{Content, ToolRegistry};

/// Shared state for HTTP handlers
pub struct HttpState {
    /// Server name
    pub name: String,
    /// Server version
    pub version: String,
    /// Tool registry
    pub tools: ToolRegistry,
    /// Session manager
    pub sessions: SessionManager,
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
        server: state.name.clone(),
        version: state.version.clone(),
    })
}

async fn list_tools_handler(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    let tools: Vec<_> = state
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
    let tool = match state.tools.get(&request.tool) {
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
        }
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
        "server_name": state.name,
        "server_version": state.version,
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
    Json(request): Json<Value>,
) -> impl IntoResponse {
    let client_name = request
        .get("client")
        .and_then(|c| c.get("name"))
        .and_then(|n| n.as_str())
        .unwrap_or("unknown");

    let timestamp = chrono::Utc::now().timestamp();

    Json(json!({
        "session_id": format!("session-{}-{}", client_name, timestamp),
        "server": {
            "name": state.name,
            "version": state.version,
        },
        "capabilities": {
            "tools": true,
            "prompts": false,
            "resources": false,
        }
    }))
}

async fn capabilities_handler(State(state): State<Arc<HttpState>>) -> impl IntoResponse {
    let tool_names: Vec<_> = state.tools.names().into_iter().collect();

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
            "name": state.name,
            "version": state.version,
            "description": format!("{} MCP Server", state.name),
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
                    if let Some(resp) =
                        process_jsonrpc_request(&state, &request, &session_id).await
                    {
                        responses.push(resp);
                    }
                    // Notifications (no id) don't get responses, which is correct
                }
                Err(e) => {
                    // Per JSON-RPC 2.0, return an error for invalid batch items
                    // Try to extract the id from the raw value for the error response
                    let id = req.get("id").cloned().unwrap_or(json!(null));
                    responses.push(JsonRpcResponse::error_with_code(
                        id,
                        JsonRpcErrorCode::InvalidRequest,
                        Some(format!("Invalid request in batch: {}", e)),
                    ));
                }
            }
        }
        return json_response_with_session(json!(responses), session_id);
    }

    // Handle single request
    match serde_json::from_value::<JsonRpcRequest>(body) {
        Ok(request) => {
            // Generate session ID for initialize requests
            let effective_session = if request.method == "initialize" && session_id.is_none() {
                Some(state.sessions.create_session("2024-11-05").await)
            } else {
                session_id
            };

            match process_jsonrpc_request(&state, &request, &effective_session).await {
                Some(resp) => json_response_with_session(json!(resp), effective_session),
                None => {
                    // Notification - no response body
                    Response::builder()
                        .status(StatusCode::ACCEPTED)
                        .header("Mcp-Session-Id", effective_session.unwrap_or_default())
                        .body(axum::body::Body::empty())
                        .unwrap()
                }
            }
        }
        Err(e) => {
            let error_resp = JsonRpcResponse::error_with_code(
                json!(null),
                JsonRpcErrorCode::ParseError,
                Some(e.to_string()),
            );
            json_response_with_session(json!(error_resp), session_id)
        }
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

// ============================================================================
// JSON-RPC processing
// ============================================================================

async fn process_jsonrpc_request(
    state: &HttpState,
    request: &JsonRpcRequest,
    session_id: &Option<String>,
) -> Option<JsonRpcResponse> {
    let is_notification = request.is_notification();
    let id = request.id.clone().unwrap_or(json!(null));

    info!("JSON-RPC request: method={}, id={:?}", request.method, id);

    let result = match request.method.as_str() {
        "initialize" => handle_initialize(state, &request.params, session_id).await,
        "initialized" => {
            info!("Client sent initialized notification");
            if is_notification {
                return None;
            }
            Ok(json!({"status": "acknowledged"}))
        }
        "tools/list" => handle_tools_list(state).await,
        "tools/call" => handle_tools_call(state, &request.params).await,
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
        }
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

async fn handle_initialize(
    state: &HttpState,
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
        state
            .sessions
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
            name: state.name.clone(),
            version: state.version.clone(),
        },
        capabilities: ServerCapabilities::default(),
    };

    Ok(serde_json::to_value(result)?)
}

async fn handle_tools_list(state: &HttpState) -> Result<Value, MCPError> {
    let tools: Vec<ToolInfo> = state
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

async fn handle_tools_call(state: &HttpState, params: &Value) -> Result<Value, MCPError> {
    let call_params: ToolCallParams = serde_json::from_value(params.clone())
        .map_err(|e| MCPError::InvalidParameters(e.to_string()))?;

    info!("Calling tool: {}", call_params.name);

    let tool = state
        .tools
        .get(&call_params.name)
        .ok_or_else(|| MCPError::ToolNotFound(call_params.name.clone()))?;

    let result = tool.execute(call_params.arguments).await?;

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

        let state = Arc::new(HttpState {
            name: "test-server".to_string(),
            version: "1.0.0".to_string(),
            tools,
            sessions: SessionManager::new(),
        });

        let app = HttpTransport::router(state);
        let client = axum_test::TestServer::new(app).unwrap();

        let response = client.get("/health").await;
        response.assert_status_ok();

        let body: HealthResponse = response.json();
        assert_eq!(body.status, "healthy");
        assert_eq!(body.server, "test-server");
    }
}
