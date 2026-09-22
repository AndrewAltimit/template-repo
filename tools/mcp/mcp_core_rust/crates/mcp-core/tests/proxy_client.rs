//! End-to-end tests of `mcp_client::RestToolClient` against real backends
//! served by this crate's REST (server mode) and HTTP (standalone) routers.

use std::sync::Arc;

use async_trait::async_trait;
use mcp_client::{ClientError, RestToolClient};
use mcp_core::tool::{Tool, ToolRegistry, ToolResult};
use mcp_core::transport::{HttpState, HttpTransport, RestState, RestTransport};
use mcp_core::{MCPError, Result};
use serde_json::{Value, json};

struct Echo;

#[async_trait]
impl Tool for Echo {
    fn name(&self) -> &str {
        "echo"
    }
    fn description(&self) -> &str {
        "Echo"
    }
    fn schema(&self) -> Value {
        json!({"type": "object", "properties": {"msg": {"type": "string"}}})
    }
    async fn execute(&self, args: Value) -> Result<ToolResult> {
        match args.get("msg").and_then(Value::as_str) {
            Some(msg) => Ok(ToolResult::text(msg.to_string())),
            None => Ok(ToolResult::error("msg is required")),
        }
    }
}

struct Broken;

#[async_trait]
impl Tool for Broken {
    fn name(&self) -> &str {
        "broken"
    }
    fn description(&self) -> &str {
        "Always Err"
    }
    fn schema(&self) -> Value {
        json!({"type": "object"})
    }
    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        Err(MCPError::internal("database unavailable"))
    }
}

fn registry() -> ToolRegistry {
    let mut tools = ToolRegistry::new();
    tools.register(Echo);
    tools.register(Broken);
    tools
}

async fn spawn(app: axum::Router) -> String {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });
    format!("http://{addr}")
}

async fn rest_backend() -> String {
    spawn(RestTransport::router(Arc::new(RestState {
        name: "rest".into(),
        version: "1".into(),
        tools: registry(),
    })))
    .await
}

async fn http_backend() -> String {
    spawn(HttpTransport::router(Arc::new(HttpState::new(
        "http".into(),
        "1".into(),
        registry(),
    ))))
    .await
}

async fn exercise(base: String) {
    let client = RestToolClient::new(format!("{base}/"));
    assert!(client.health_check().await.unwrap());

    let tools = client.list_tools().await.unwrap();
    let names: Vec<_> = tools.iter().map(|t| t.name.as_str()).collect();
    assert_eq!(names, vec!["broken", "echo"]);
    assert_eq!(tools[1].input_schema["properties"]["msg"]["type"], "string");

    let ok = client
        .execute_tool("echo", json!({"msg": "hi"}))
        .await
        .unwrap();
    assert!(ok.success);
    assert_eq!(ok.result.unwrap()["content"][0]["text"], "hi");

    // A tool-level error result is `Ok(success: false)` with its content.
    let tool_err = client.execute_tool("echo", json!({})).await.unwrap();
    assert!(!tool_err.success);
    assert_eq!(
        tool_err.result.unwrap()["content"][0]["text"],
        "msg is required"
    );

    // A tool returning Err (HTTP 500) is still a readable result, not a
    // transport/parse failure.
    let broken = client.execute_tool("broken", json!({})).await.unwrap();
    assert!(!broken.success);
    assert!(broken.error.unwrap().contains("database unavailable"));

    let missing = client.execute_tool("nope", json!({})).await.unwrap_err();
    assert!(matches!(missing, ClientError::ToolNotFound(_)), "{missing}");
}

#[tokio::test]
async fn client_against_rest_server_mode() {
    exercise(rest_backend().await).await;
}

#[tokio::test]
async fn client_against_standalone_simple_api() {
    exercise(http_backend().await).await;
}

#[tokio::test]
async fn list_tools_errors_on_non_tool_response() {
    let app = axum::Router::new().route(
        "/tools",
        axum::routing::get(|| async { axum::Json(json!({"unexpected": true})) }),
    );
    let client = RestToolClient::new(spawn(app).await);
    assert!(client.list_tools().await.is_err());
}
