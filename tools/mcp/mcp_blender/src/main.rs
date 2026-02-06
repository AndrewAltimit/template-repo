// Allow pre-existing dead code in planned but unused type enums
#![allow(
    dead_code,
    clippy::derivable_impls,
    clippy::manual_map,
    clippy::unnecessary_map_or,
    clippy::len_zero
)]

//! MCP Blender Server
//!
//! Provides MCP tools for headless Blender 3D content creation, rendering,
//! and simulation through subprocess automation.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-blender --mode standalone --port 8017
//!
//!     # Test endpoints
//!     curl http://localhost:8017/health
//!     curl http://localhost:8017/mcp/tools

mod blender;
mod jobs;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::BlenderServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-blender")]
#[command(about = "MCP server for headless Blender 3D content creation and rendering")]
#[command(version = "2.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create Blender server
    let blender_server = BlenderServer::new();

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("blender", "2.0.0");
    builder = args.server.apply_to(builder);

    for tool in blender_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
