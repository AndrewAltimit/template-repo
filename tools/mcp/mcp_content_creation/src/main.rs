//! MCP Content Creation Server
//!
//! Provides content creation tools via MCP - LaTeX compilation, TikZ rendering,
//! PDF previews, and Manim animations.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-content-creation --mode standalone --port 8011
//!
//!     # Test endpoints
//!     curl http://localhost:8011/health
//!     curl http://localhost:8011/mcp/tools

mod engine;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use std::path::PathBuf;

use server::ContentCreationServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-content-creation")]
#[command(about = "MCP server for content creation - LaTeX, TikZ, PDF previews, and Manim")]
#[command(version = "2.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Output directory for generated content
    #[arg(long, default_value = "/app/output", env = "MCP_OUTPUT_DIR")]
    output_dir: PathBuf,

    /// Project root for resolving relative paths
    #[arg(long, default_value = "/app", env = "MCP_PROJECT_ROOT")]
    project_root: PathBuf,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create content creation server
    let content_server = ContentCreationServer::new(args.output_dir, args.project_root);

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("content-creation", "2.0.0");
    builder = args.server.apply_to(builder);

    for tool in content_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
