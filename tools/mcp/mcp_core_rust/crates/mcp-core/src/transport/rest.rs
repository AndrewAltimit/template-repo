//! REST-only transport for server mode.
//!
//! This provides a simplified REST API without MCP protocol overhead.
//! Useful for direct API access, microservice deployments, and testing.
//!
//! # Endpoints
//!
//! - `GET /health` - Health check
//! - `GET /tools` - List available tools
//! - `POST /tools/{name}/call` - Execute a specific tool
//! - `POST /execute` - Execute tool (alternative endpoint)

use axum::{
    Router,
    extract::{Json, Path, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};
use tracing::info;

use crate::error::MCPError;
use crate::tool::ToolRegistry;

/// Shared state for REST handlers
pub struct RestState {
    /// Server name
    pub name: String,
    /// Server version
    pub version: String,
    /// Tool registry
    pub tools: ToolRegistry,
}

/// REST transport for server mode (no MCP protocol)
pub struct RestTransport;

impl RestTransport {
    /// Create an Axum router with REST-only endpoints
    pub fn router(state: Arc<RestState>) -> Router {
        let cors = CorsLayer::new()
            .allow_origin(Any)
            .allow_methods(Any)
            .allow_headers(Any);

        Router::new()
            // Health check
            .route("/health", get(health_handler))
            // Tool operations
            .route("/tools", get(list_tools_handler))
            .route("/tools/:name/call", post(call_tool_handler))
            .route("/execute", post(execute_handler))
            .with_state(state)
            .layer(cors)
    }
}

// ============================================================================
// Response types
// ============================================================================

/// Health check response
#[derive(Serialize)]
struct HealthResponse {
    status: String,
    server: String,
    version: String,
    mode: String,
}

/// Tool information
#[derive(Serialize)]
struct ToolInfoResponse {
    name: String,
    description: String,
    parameters: Value,
}

/// Tool list response
#[derive(Serialize)]
struct ToolListResponse {
    tools: Vec<ToolInfoResponse>,
    count: usize,
}

/// Tool execution request
#[derive(Deserialize)]
struct ExecuteRequest {
    /// Tool name (only for /execute endpoint)
    #[serde(default)]
    tool: Option<String>,
    /// Tool arguments
    #[serde(default)]
    arguments: Value,
}

/// Tool execution response
#[derive(Serialize)]
struct ExecuteResponse {
    success: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

// ============================================================================
// Handlers
// ============================================================================

async fn health_handler(State(state): State<Arc<RestState>>) -> impl IntoResponse {
    Json(HealthResponse {
        status: "healthy".to_string(),
        server: state.name.clone(),
        version: state.version.clone(),
        mode: "server".to_string(),
    })
}

async fn list_tools_handler(State(state): State<Arc<RestState>>) -> impl IntoResponse {
    let tools: Vec<ToolInfoResponse> = state
        .tools
        .list()
        .into_iter()
        .map(|t| ToolInfoResponse {
            name: t.name,
            description: t.description,
            parameters: t.input_schema,
        })
        .collect();

    let count = tools.len();

    Json(ToolListResponse { tools, count })
}

fn failure(status: StatusCode, error: String) -> (StatusCode, Json<ExecuteResponse>) {
    (
        status,
        Json(ExecuteResponse {
            success: false,
            result: None,
            error: Some(error),
        }),
    )
}

/// Execute `name` (inside the registry's panic boundary) and shape the REST
/// response. Shared by both execution endpoints.
async fn run_tool(
    state: &RestState,
    name: &str,
    arguments: Value,
) -> (StatusCode, Json<ExecuteResponse>) {
    let arguments = if arguments.is_null() {
        json!({})
    } else {
        arguments
    };
    match state.tools.call(name, arguments).await {
        Ok(result) => (
            StatusCode::OK,
            Json(ExecuteResponse {
                success: !result.is_error,
                result: Some(json!({
                    "content": result.content,
                    "is_error": result.is_error
                })),
                error: None,
            }),
        ),
        Err(MCPError::ToolNotFound(_)) => {
            failure(StatusCode::NOT_FOUND, format!("Tool '{name}' not found"))
        },
        Err(e) => failure(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()),
    }
}

async fn call_tool_handler(
    State(state): State<Arc<RestState>>,
    Path(name): Path<String>,
    Json(request): Json<ExecuteRequest>,
) -> impl IntoResponse {
    info!("REST call tool: {}", name);
    run_tool(&state, &name, request.arguments).await
}

async fn execute_handler(
    State(state): State<Arc<RestState>>,
    Json(request): Json<ExecuteRequest>,
) -> impl IntoResponse {
    let Some(name) = request.tool else {
        return failure(
            StatusCode::BAD_REQUEST,
            "Missing 'tool' field in request".to_string(),
        );
    };
    info!("REST execute tool: {}", name);
    run_tool(&state, &name, request.arguments).await
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
                "properties": {
                    "message": {"type": "string"}
                }
            })
        }
        async fn execute(&self, args: Value) -> crate::error::Result<ToolResult> {
            let msg = args
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("no message");
            Ok(ToolResult::text(format!("Echo: {}", msg)))
        }
    }

    #[tokio::test]
    async fn test_rest_health_endpoint() {
        let mut tools = ToolRegistry::new();
        tools.register(TestTool);

        let state = Arc::new(RestState {
            name: "test-server".to_string(),
            version: "1.0.0".to_string(),
            tools,
        });

        let app = RestTransport::router(state);
        let client = axum_test::TestServer::new(app).unwrap();

        let response = client.get("/health").await;
        response.assert_status_ok();

        let body: Value = response.json();
        assert_eq!(body["status"], "healthy");
        assert_eq!(body["mode"], "server");
    }

    #[tokio::test]
    async fn test_rest_list_tools() {
        let mut tools = ToolRegistry::new();
        tools.register(TestTool);

        let state = Arc::new(RestState {
            name: "test-server".to_string(),
            version: "1.0.0".to_string(),
            tools,
        });

        let app = RestTransport::router(state);
        let client = axum_test::TestServer::new(app).unwrap();

        let response = client.get("/tools").await;
        response.assert_status_ok();

        let body: Value = response.json();
        assert_eq!(body["count"], 1);
        assert_eq!(body["tools"][0]["name"], "test_tool");
    }

    #[tokio::test]
    async fn test_rest_call_tool() {
        let mut tools = ToolRegistry::new();
        tools.register(TestTool);

        let state = Arc::new(RestState {
            name: "test-server".to_string(),
            version: "1.0.0".to_string(),
            tools,
        });

        let app = RestTransport::router(state);
        let client = axum_test::TestServer::new(app).unwrap();

        let response = client
            .post("/tools/test_tool/call")
            .json(&json!({"arguments": {"message": "hello"}}))
            .await;
        response.assert_status_ok();

        let body: Value = response.json();
        assert!(body["success"].as_bool().unwrap());
    }

    #[tokio::test]
    async fn test_rest_execute() {
        let mut tools = ToolRegistry::new();
        tools.register(TestTool);

        let state = Arc::new(RestState {
            name: "test-server".to_string(),
            version: "1.0.0".to_string(),
            tools,
        });

        let app = RestTransport::router(state);
        let client = axum_test::TestServer::new(app).unwrap();

        let response = client
            .post("/execute")
            .json(&json!({
                "tool": "test_tool",
                "arguments": {"message": "world"}
            }))
            .await;
        response.assert_status_ok();

        let body: Value = response.json();
        assert!(body["success"].as_bool().unwrap());
    }

    #[tokio::test]
    async fn test_rest_tool_not_found() {
        let tools = ToolRegistry::new();

        let state = Arc::new(RestState {
            name: "test-server".to_string(),
            version: "1.0.0".to_string(),
            tools,
        });

        let app = RestTransport::router(state);
        let client = axum_test::TestServer::new(app).unwrap();

        let response = client
            .post("/tools/nonexistent/call")
            .json(&json!({"arguments": {}}))
            .await;
        response.assert_status(StatusCode::NOT_FOUND);

        let body: Value = response.json();
        assert!(!body["success"].as_bool().unwrap());
        assert!(body["error"].as_str().unwrap().contains("not found"));
    }
}
