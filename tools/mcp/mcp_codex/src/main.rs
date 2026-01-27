// Allow collapsible_if - clippy suggests let-chains which require nightly
#![allow(clippy::collapsible_if)]

//! MCP Codex Server
//!
//! Provides Codex AI integration for code generation via MCP tools.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-codex --mode standalone --port 8021
//!
//!     # Test endpoints
//!     curl http://localhost:8021/health
//!     curl http://localhost:8021/mcp/tools

mod codex;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::CodexServer;
use types::CodexConfig;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-codex")]
#[command(about = "MCP server for Codex AI code generation")]
#[command(version = "2.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Load .env file if present
    let _ = dotenvy::dotenv();

    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Load configuration from environment
    let config = CodexConfig::from_env();

    // Create Codex server
    let codex_server = CodexServer::new(config);

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("codex", "2.0.0");
    builder = args.server.apply_to(builder);

    for tool in codex_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
