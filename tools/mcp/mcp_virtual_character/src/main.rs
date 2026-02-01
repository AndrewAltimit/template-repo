//! Virtual Character MCP Server CLI entry point.
//!
#![allow(dead_code, unused_imports)]

//! This binary provides an MCP server for controlling virtual characters
//! via VRChat OSC or other backends.

use anyhow::Result;
use clap::Parser;
use mcp_core::{init_logging, server::MCPServerArgs, MCPServer};

mod backends;
mod constants;
mod server;
mod types;

use server::VirtualCharacterServer;

/// Virtual Character MCP Server
#[derive(Parser)]
#[command(name = "mcp-virtual-character")]
#[command(about = "MCP server for virtual character control via VRChat OSC")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    tracing::info!("Starting Virtual Character MCP Server v1.0.0");

    // Create server instance
    let vc_server = VirtualCharacterServer::new();

    // Build MCP server
    let mut builder = MCPServer::builder("virtual-character", "1.0.0");
    builder = args.server.apply_to(builder);

    // Register all tools
    for tool in vc_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    tracing::info!("Virtual Character MCP Server initialized");
    tracing::info!("Available backends: mock, vrchat_remote");
    tracing::info!("Default VRChat configuration:");
    tracing::info!("  - Host: 127.0.0.1");
    tracing::info!("  - VRChat Receive Port: 9000");
    tracing::info!("  - VRChat Send Port: 9001");
    tracing::info!("  - VRCEmote System: Enabled");

    server.run().await?;

    Ok(())
}
