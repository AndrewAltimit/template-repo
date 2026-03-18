//! MCP Sprite Sheet Server
//!
//! Programmatic pixel art and sprite sheet creation via MCP tools.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-sprite-sheet --mode standalone --port 8027
//!
//!     # Test endpoints
//!     curl http://localhost:8027/health
//!     curl http://localhost:8027/mcp/tools

mod engine;
mod palette;
mod render;
mod server;
mod tools;
mod types;

use std::path::PathBuf;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::SpriteSheetServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-sprite-sheet")]
#[command(about = "MCP server for programmatic pixel art and sprite sheet creation")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Output directory for rendered PNGs
    #[arg(long, default_value = "/tmp/sprites")]
    output: PathBuf,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Ensure output directory exists
    std::fs::create_dir_all(&args.output)?;

    let sprite_server = SpriteSheetServer::new(args.output);

    let mut builder = MCPServer::builder("sprite-sheet", "1.0.0");
    builder = args.server.apply_to(builder);

    for tool in sprite_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();
    server.run().await?;

    Ok(())
}
