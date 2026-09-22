//! MCP Sprite Sheet Server
//!
//! Programmatic pixel art and sprite sheet creation via MCP tools.
//!
//! Usage:
//!     # STDIO mode (how Claude Code launches it)
//!     mcp-sprite-sheet --mode stdio --output /output
//!
//!     # Standalone HTTP mode
//!     mcp-sprite-sheet --mode standalone --port 8027
//!     curl http://localhost:8027/health
//!     curl http://localhost:8027/mcp/tools

mod args;
mod engine;
mod files;
mod font;
mod geometry;
mod import;
mod palette;
mod persist;
mod render;
mod server;
mod tools;
mod types;

use std::path::PathBuf;

use anyhow::Context;
use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::SpriteSheetServer;

fn default_output_dir() -> PathBuf {
    std::env::temp_dir().join("sprites")
}

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-sprite-sheet")]
#[command(about = "MCP server for programmatic pixel art and sprite sheet creation")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Output directory for rendered PNG/GIF/JSON files
    #[arg(long, env = "MCP_SPRITE_OUTPUT_DIR", default_value_os_t = default_output_dir())]
    output: PathBuf,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    std::fs::create_dir_all(&args.output)
        .with_context(|| format!("cannot create output directory {}", args.output.display()))?;
    tracing::info!(output = %args.output.display(), "sprite sheet server starting");

    let sprite_server = SpriteSheetServer::new(args.output);

    let mut builder = MCPServer::builder("sprite-sheet", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);

    for tool in sprite_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();
    server.run().await?;

    Ok(())
}
