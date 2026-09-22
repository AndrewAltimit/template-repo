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
//!         use mcp_core::args::ArgsExt;
//!         let msg = args.required_str("message")?;
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
//! # Modules at a glance
//!
//! | Module | What it gives a server author |
//! |--------|-------------------------------|
//! | [`tool`] | [`Tool`] trait, [`ToolResult`]/[`Content`], [`ToolRegistry`] |
//! | [`args`] | Typed argument extraction ([`args::parse_args`], [`args::ArgsExt`]) |
//! | [`schema`] | Input schemas derived from Rust types ([`schema::schema_for`]) |
//! | [`context`] | Progress notifications and request metadata inside `execute` |
//! | [`server`] | [`MCPServer`] builder, CLI args, logging, graceful shutdown |
//! | [`http`] | Shared `reqwest` client construction with sane timeouts |
//! | [`transport`] | STDIO / HTTP / REST transports and the protocol handler |
//! | [`jsonrpc`] | JSON-RPC and MCP wire types, protocol-version negotiation |
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
//! | `/mcp`, `/messages` | POST | MCP JSON-RPC endpoint (Streamable HTTP) |
//! | `/mcp`, `/messages` | DELETE | Terminate an MCP session |
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
//!
//! ## Stdio Mode
//!
//! Newline-delimited JSON-RPC over stdin/stdout, for clients that spawn the
//! server as a child process. Requests are handled concurrently and support
//! cancellation and progress notifications.
//!
//! ```bash
//! ./my-server --mode stdio
//! ```

pub mod args;
pub mod context;
pub mod error;
pub mod http;
pub mod jsonrpc;
pub mod schema;
pub mod server;
pub mod session;
pub mod tool;
pub mod transport;

// Re-export commonly used items
pub use error::{MCPError, Result};
pub use server::{MCPServer, MCPServerArgs, MCPServerBuilder, ServerMode, init_logging};
pub use tool::{BoxedTool, Content, Tool, ToolAnnotations, ToolRegistry, ToolResult, ToolSchema};

/// Re-export of the `schemars` version used by [`schema::schema_for`], so
/// servers can `#[derive(JsonSchema)]` without a separate dependency (add
/// `#[schemars(crate = "mcp_core::schemars")]` to the derive).
pub use schemars;

/// Prelude module for convenient imports
pub mod prelude {
    pub use crate::error::{MCPError, Result};
    pub use crate::server::{MCPServer, MCPServerArgs, MCPServerBuilder, ServerMode, init_logging};
    pub use crate::tool::{BoxedTool, Content, Tool, ToolRegistry, ToolResult, ToolSchema};
}

/// Compile-time checks for `#[mcp_tool]` misuse (run by `cargo test --doc`).
///
/// Control case (must compile):
/// ```
/// #[mcp_macros::mcp_tool(description = "ok")]
/// async fn fine(#[mcp(description = "x")] x: i64) -> Result<i64, String> { Ok(x) }
/// ```
///
/// Unknown tool attribute key:
/// ```compile_fail
/// #[mcp_macros::mcp_tool(descripton = "typo")]
/// async fn f() -> Result<(), String> { Ok(()) }
/// ```
///
/// Unknown parameter attribute key:
/// ```compile_fail
/// #[mcp_macros::mcp_tool(description = "d")]
/// async fn f(#[mcp(descripton = "typo")] x: i64) -> Result<i64, String> { Ok(x) }
/// ```
///
/// Missing description and doc comment:
/// ```compile_fail
/// #[mcp_macros::mcp_tool]
/// async fn f() -> Result<(), String> { Ok(()) }
/// ```
///
/// Missing `Result` return type:
/// ```compile_fail
/// #[mcp_macros::mcp_tool(description = "d")]
/// async fn f() {}
/// ```
///
/// Invalid tool name:
/// ```compile_fail
/// #[mcp_macros::mcp_tool(name = "has space", description = "d")]
/// async fn f() -> Result<(), String> { Ok(()) }
/// ```
///
/// Destructuring pattern parameter:
/// ```compile_fail
/// #[mcp_macros::mcp_tool(description = "d")]
/// async fn f((a, b): (i64, i64)) -> Result<i64, String> { Ok(a + b) }
/// ```
#[cfg(doctest)]
pub struct McpToolCompileChecks;

/// Implementation details used by code generated by `mcp-macros`. Not part of
/// the public API; may change without notice.
#[doc(hidden)]
pub mod __private {
    pub use async_trait;
    pub use serde_json;
}
