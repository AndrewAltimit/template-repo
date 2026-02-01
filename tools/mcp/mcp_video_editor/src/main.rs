//! MCP Video Editor Server
//!
//! Provides MCP tools for intelligent automated video editing with
//! transcript analysis, speaker detection, and automated editing decisions.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-video-editor --mode standalone --port 8019
//!
//!     # Test endpoints
//!     curl http://localhost:8019/health
//!     curl http://localhost:8019/mcp/tools

mod audio;
mod jobs;
mod server;
mod types;
mod video;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::VideoEditorServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-video-editor")]
#[command(about = "MCP server for intelligent automated video editing")]
#[command(version = "2.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create video editor server
    let video_server = VideoEditorServer::new();

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("video-editor", "2.0.0");
    builder = args.server.apply_to(builder);

    for tool in video_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
