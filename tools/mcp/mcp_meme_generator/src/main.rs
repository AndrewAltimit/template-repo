//! MCP Meme Generator Server
//!
//! Generates memes from templates with text overlays via MCP tools.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-meme-generator --mode standalone --port 8016
//!
//!     # Test endpoints
//!     curl http://localhost:8016/health
//!     curl http://localhost:8016/mcp/tools

mod generator;
mod server;
mod types;
mod upload;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use std::path::PathBuf;

use server::MemeGeneratorServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-meme-generator")]
#[command(about = "MCP server for meme generation with text overlays")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Path to templates directory
    #[arg(long, default_value = None)]
    templates: Option<PathBuf>,

    /// Output directory for generated memes
    #[arg(long, default_value = "/tmp/memes")]
    output: PathBuf,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Determine templates directory
    let templates_dir = args.templates.unwrap_or_else(|| {
        // Default to templates in the binary's directory or current directory
        let exe_dir = std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|p| p.to_path_buf()));

        if let Some(dir) = exe_dir {
            let templates = dir.join("templates");
            if templates.exists() {
                return templates;
            }
        }

        // Check current directory
        let cwd_templates = PathBuf::from("templates");
        if cwd_templates.exists() {
            return cwd_templates;
        }

        // Check MCP server source directory
        let source_templates = PathBuf::from("tools/mcp/mcp_meme_generator/templates");
        if source_templates.exists() {
            return source_templates;
        }

        // Default fallback
        PathBuf::from("templates")
    });

    // Create meme generator server
    let meme_server = MemeGeneratorServer::new(templates_dir, args.output);

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("meme-generator", "1.0.0");
    builder = args.server.apply_to(builder);

    for tool in meme_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
