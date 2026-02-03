//! MCP Core - A Rust library for building MCP (Model Context Protocol) servers.
//!
//! This crate provides the core abstractions and implementations for building
//! MCP servers in Rust with support for multiple operational modes:
//!
//! - **Standalone**: Full MCP server with embedded tools (default)
//! - **Server**: REST API only, no MCP protocol
//! - **Client**: MCP proxy that forwards tool calls to a REST backend
//! - **Stdio**: JSON-RPC over stdin/stdout for process-based transports
//!
//! # Quick Start
//!
//! ```rust,no_run
//! use mcp_core::prelude::*;
//! use serde_json::{json, Value};
//!
//! // Define a tool
//! struct EchoTool;
//!
//! #[async_trait::async_trait]
//! impl Tool for EchoTool {
//!     fn name(&self) -> &str { "echo" }
//!     fn description(&self) -> &str { "Echo the input message" }
//!     fn schema(&self) -> Value {
//!         json!({
//!             "type": "object",
//!             "properties": {
//!                 "message": {"type": "string"}
//!             },
//!             "required": ["message"]
//!         })
//!     }
//!     async fn execute(&self, args: Value) -> Result<ToolResult> {
//!         let msg = args["message"].as_str().unwrap_or("no message");
//!         Ok(ToolResult::text(format!("Echo: {msg}")))
//!     }
//! }
//!
//! #[tokio::main]
//! async fn main() -> anyhow::Result<()> {
//!     init_logging("info");
//!
//!     let server = MCPServer::builder("my-server", "1.0.0")
//!         .port(8080)
//!         .tool(EchoTool)
//!         .build();
//!
//!     server.run().await?;
//!     Ok(())
//! }
//! ```
//!
//! # HTTP Endpoints
//!
//! The server exposes the following endpoints:
//!
//! | Endpoint | Method | Description |
//! |----------|--------|-------------|
//! | `/health` | GET | Health check |
//! | `/mcp/tools` | GET | List available tools |
//! | `/mcp/execute` | POST | Execute a tool (simple API) |
//! | `/messages` | POST | MCP JSON-RPC endpoint |
//! | `/.well-known/mcp` | GET | MCP discovery |
//!
//! # Operational Modes
//!
//! ## Standalone Mode (Default)
//!
//! Full MCP server with embedded tools. Use this for single-process deployments.
//!
//! ```bash
//! ./my-server --mode standalone --port 8080
//! ```
//!
//! ## Server Mode
//!
//! REST API only, no MCP protocol. Useful for microservice deployments where
//! the MCP protocol is handled by a separate gateway.
//!
//! ```bash
//! ./my-server --mode server --port 8080
//! ```
//!
//! ## Client Mode
//!
//! MCP proxy that forwards tool calls to a REST backend. Enables horizontal
//! scaling of tool execution while presenting a single MCP interface.
//!
//! ```bash
//! ./my-server --mode client --port 8080 --backend-url http://tools:8081
//! ```

pub mod error;
pub mod jsonrpc;
pub mod server;
pub mod session;
pub mod tool;
pub mod transport;

// Re-export commonly used items
pub use error::{MCPError, Result};
pub use server::{MCPServer, MCPServerArgs, MCPServerBuilder, ServerMode, init_logging};
pub use tool::{BoxedTool, Content, Tool, ToolRegistry, ToolResult, ToolSchema};

/// Prelude module for convenient imports
pub mod prelude {
    pub use crate::error::{MCPError, Result};
    pub use crate::server::{MCPServer, MCPServerArgs, MCPServerBuilder, ServerMode, init_logging};
    pub use crate::tool::{BoxedTool, Content, Tool, ToolRegistry, ToolResult, ToolSchema};
}
