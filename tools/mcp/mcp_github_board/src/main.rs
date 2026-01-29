//! MCP GitHub Board Server
//!
//! Provides MCP tools for interacting with GitHub Projects v2 boards,
//! managing work claims, dependencies, and agent coordination.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-github-board --mode standalone --port 8022
//!
//!     # Test endpoints
//!     curl http://localhost:8022/health
//!     curl http://localhost:8022/mcp/tools

mod server;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::GitHubBoardServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-github-board")]
#[command(about = "MCP server for GitHub Projects v2 board operations")]
#[command(version = "2.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create GitHub board server
    let board_server = GitHubBoardServer::new();

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("github-board", "2.0.0");
    builder = args.server.apply_to(builder);

    for tool in board_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
