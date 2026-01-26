//! MCP Reaction Search Server
//!
//! Provides semantic search for anime reaction images via MCP tools.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-reaction-search --mode standalone --port 8024
//!
//!     # Test endpoints
//!     curl http://localhost:8024/health
//!     curl http://localhost:8024/mcp/tools

mod config;
mod engine;
mod server;
mod types;

use clap::Parser;
use mcp_core::{init_logging, MCPServer, server::MCPServerArgs};

use server::ReactionSearchServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-reaction-search")]
#[command(about = "MCP server for semantic reaction image search")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create reaction search server
    let reaction_server = ReactionSearchServer::new();

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("reaction-search", "1.0.0");
    builder = args.server.apply_to(builder);

    for tool in reaction_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
