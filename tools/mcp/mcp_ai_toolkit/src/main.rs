//! AI Toolkit MCP Server
//!
//! Provides MCP tools for managing LoRA training with AI Toolkit.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-ai-toolkit --mode standalone --port 8012
//!
//!     # Test endpoints
//!     curl http://localhost:8012/health
//!     curl http://localhost:8012/mcp/tools

mod config;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::AIToolkitServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-ai-toolkit")]
#[command(about = "MCP server for AI Toolkit - LoRA training management")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create AI Toolkit server
    let toolkit_server = AIToolkitServer::new().await?;

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("ai-toolkit", "1.0.0");
    builder = args.server.apply_to(builder);

    for tool in toolkit_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
