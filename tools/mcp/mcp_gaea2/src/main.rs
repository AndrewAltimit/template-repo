// Allow pre-existing dead code and style issues in planned but unused features
#![allow(
    dead_code,
    unused_imports,
    unused_variables,
    clippy::derivable_impls,
    clippy::too_many_arguments,
    clippy::get_first,
    clippy::option_map_or_none,
    clippy::vec_init_then_push,
    clippy::redundant_pattern_matching,
    clippy::bind_instead_of_map
)]

//! Gaea2 MCP Server CLI entry point.
//!
//! This binary provides an MCP server for Gaea2 terrain generation,
//! offering tools for project creation, validation, optimization, and execution.

use anyhow::Result;
use clap::Parser;
use mcp_core::{init_logging, server::MCPServerArgs, MCPServer};

mod cli;
mod config;
mod generation;
mod schema;
mod server;
mod templates;
mod types;
mod validation;

use server::Gaea2Server;

/// Gaea2 MCP Server
#[derive(Parser)]
#[command(name = "mcp-gaea2")]
#[command(about = "MCP server for Gaea2 terrain generation")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Path to Gaea2 executable (Gaea.Swarm.exe)
    #[arg(long, env = "GAEA2_PATH")]
    gaea_path: Option<String>,

    /// Output directory for generated terrain files
    #[arg(long, default_value = "/app/output/gaea2", env = "GAEA2_OUTPUT_DIR")]
    output_dir: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    tracing::info!("Starting Gaea2 MCP Server v1.0.0");

    // Create server instance
    let gaea2_server = Gaea2Server::new(args.gaea_path, args.output_dir).await?;

    // Build MCP server
    let mut builder = MCPServer::builder("gaea2", "1.0.0");
    builder = args.server.apply_to(builder);

    // Register all tools
    for tool in gaea2_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    tracing::info!("Gaea2 MCP Server initialized");
    tracing::info!("Output directory: {}", gaea2_server.output_dir());
    if let Some(path) = gaea2_server.gaea_path() {
        tracing::info!("Gaea2 executable: {}", path);
    } else {
        tracing::warn!("Gaea2 executable not configured - CLI automation disabled");
    }

    server.run().await?;

    Ok(())
}
