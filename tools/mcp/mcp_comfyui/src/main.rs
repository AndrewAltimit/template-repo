//! MCP ComfyUI Server
//!
//! Provides image generation capabilities via ComfyUI integration.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-comfyui --mode standalone --port 8013
//!
//!     # Test endpoints
//!     curl http://localhost:8013/health
//!     curl http://localhost:8013/mcp/tools

mod client;
mod server;
mod types;
mod workflows;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::ComfyUIServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-comfyui")]
#[command(about = "MCP server for ComfyUI image generation")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create ComfyUI server
    let comfyui_server = ComfyUIServer::new();

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("comfyui", "1.0.0");
    builder = args.server.apply_to(builder);

    for tool in comfyui_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
