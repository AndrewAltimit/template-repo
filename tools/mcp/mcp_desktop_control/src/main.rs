//! MCP Desktop Control Server
//!
//! Cross-platform desktop control and automation via MCP tools.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-desktop-control --mode standalone --port 8030
//!
//!     # STDIO mode for Claude Desktop
//!     mcp-desktop-control --mode stdio
//!
//!     # Test endpoints
//!     curl http://localhost:8030/health
//!     curl http://localhost:8030/mcp/tools

mod backend;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::DesktopControlServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-desktop-control")]
#[command(about = "MCP server for cross-platform desktop control and automation")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create desktop control server
    let desktop_server = DesktopControlServer::new();

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("desktop-control", "1.0.0");
    builder = args.server.apply_to(builder);

    for tool in desktop_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
