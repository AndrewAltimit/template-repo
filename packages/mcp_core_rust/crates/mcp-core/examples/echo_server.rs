//! Example MCP server with a simple echo tool.
//!
//! Run with: cargo run --example echo_server -- --port 8080
//!
//! Test with:
//!   curl http://localhost:8080/health
//!   curl http://localhost:8080/mcp/tools
//!   curl -X POST http://localhost:8080/mcp/execute \
//!     -H 'Content-Type: application/json' \
//!     -d '{"tool": "echo", "arguments": {"message": "hello"}}'

use async_trait::async_trait;
use clap::Parser;
use mcp_core::{init_logging, prelude::*, server::MCPServerArgs};
use serde::Serialize;
use serde_json::{json, Value};

/// Echo tool - echoes the input message
struct EchoTool;

#[async_trait]
impl Tool for EchoTool {
    fn name(&self) -> &str {
        "echo"
    }

    fn description(&self) -> &str {
        "Echo the input message back to the caller"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to echo"
                }
            },
            "required": ["message"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let message = args
            .get("message")
            .and_then(|v| v.as_str())
            .unwrap_or("no message");

        Ok(ToolResult::text(format!("Echo: {message}")))
    }
}

/// Add tool - adds two numbers
struct AddTool;

#[async_trait]
impl Tool for AddTool {
    fn name(&self) -> &str {
        "add"
    }

    fn description(&self) -> &str {
        "Add two numbers together"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "a": {
                    "type": "number",
                    "description": "First number"
                },
                "b": {
                    "type": "number",
                    "description": "Second number"
                }
            },
            "required": ["a", "b"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let a = args
            .get("a")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'a' parameter".to_string()))?;

        let b = args
            .get("b")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'b' parameter".to_string()))?;

        let result = a + b;

        #[derive(Serialize)]
        struct AddResult {
            a: f64,
            b: f64,
            sum: f64,
        }

        ToolResult::json(&AddResult { a, b, sum: result })
    }
}

/// Server status tool
struct StatusTool {
    start_time: std::time::Instant,
}

impl StatusTool {
    fn new() -> Self {
        Self {
            start_time: std::time::Instant::now(),
        }
    }
}

#[async_trait]
impl Tool for StatusTool {
    fn name(&self) -> &str {
        "server_status"
    }

    fn description(&self) -> &str {
        "Get server status information"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        #[derive(Serialize)]
        struct Status {
            server: &'static str,
            version: &'static str,
            uptime_seconds: u64,
        }

        ToolResult::json(&Status {
            server: "echo-server",
            version: "1.0.0",
            uptime_seconds: self.start_time.elapsed().as_secs(),
        })
    }
}

/// CLI arguments
#[derive(Parser)]
#[command(name = "echo-server")]
#[command(about = "Example MCP server with echo, add, and status tools")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    let server = args
        .server
        .apply_to(MCPServer::builder("echo-server", "1.0.0"))
        .tool(EchoTool)
        .tool(AddTool)
        .tool(StatusTool::new())
        .build();

    server.run().await?;

    Ok(())
}
