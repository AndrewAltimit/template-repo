//! MCP ComfyUI Server
//!
//! Exposes a ComfyUI instance (text-to-image, img2img, upscale, ControlNet,
//! custom workflows, job tracking and LoRA file management) as MCP tools.
//!
//! Usage:
//!     # HTTP (default mode), as run inside the ComfyUI container
//!     mcp-comfyui --mode standalone --port 8013
//!
//!     # STDIO, for a local MCP client
//!     mcp-comfyui --mode stdio
//!
//!     # Test endpoints
//!     curl http://localhost:8013/health
//!     curl http://localhost:8013/mcp/tools
//!
//! Configuration is read from `COMFYUI_*` environment variables; see
//! [`config::Config`] and the crate README.

mod client;
mod config;
mod loras;
mod server;
mod types;
mod validate;
mod workflows;

#[cfg(test)]
mod mock_tests;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::ComfyUIServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-comfyui")]
#[command(about = "MCP server for ComfyUI image generation")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    let comfyui_server = ComfyUIServer::new();

    let mut builder = MCPServer::builder("comfyui", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);

    for tool in comfyui_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    builder.build().run().await?;

    Ok(())
}
