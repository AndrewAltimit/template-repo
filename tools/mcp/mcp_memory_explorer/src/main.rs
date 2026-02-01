//! MCP Memory Explorer Server
//!
//! Provides memory exploration and game reverse engineering tools via MCP.
//! Windows-only: uses Windows memory APIs for process memory access.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-memory-explorer --mode standalone --port 8025
//!
//!     # Test endpoints
//!     curl http://localhost:8025/health
//!     curl http://localhost:8025/mcp/tools

mod explorer;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::MemoryExplorerServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-memory-explorer")]
#[command(about = "MCP server for game memory exploration and reverse engineering")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create memory explorer server
    let memory_server = MemoryExplorerServer::new();

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("memory-explorer", "1.0.0");
    builder = args.server.apply_to(builder);

    for tool in memory_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
