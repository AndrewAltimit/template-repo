//! Gaea2 MCP Server entry point.
//!
//! Provides MCP tools for creating, validating, analysing, repairing and
//! (on a Windows host with Gaea2 installed) building Gaea2 `.terrain` projects.

use anyhow::Result;
use clap::Parser;
use mcp_core::{init_logging, server::MCPServerArgs, MCPServer};

mod analysis;
mod cli;
mod config;
mod generation;
mod input;
mod repair;
mod schema;
mod server;
mod templates;
mod types;
mod validation;

use config::Gaea2Config;
use server::Gaea2Server;

/// Gaea2 MCP Server
#[derive(Parser)]
#[command(name = "mcp-gaea2")]
#[command(about = "MCP server for Gaea2 terrain generation")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Path to the Gaea2 executable (Gaea.Swarm.exe). Enables build tools.
    #[arg(long, env = "GAEA2_PATH")]
    gaea_path: Option<String>,

    /// Output directory for generated terrain files
    #[arg(long, default_value = "/app/output/gaea2", env = "GAEA2_OUTPUT_DIR")]
    output_dir: String,

    /// Extra directories clients may read/build from, as an OS path list
    /// (';'-separated on Windows, ':'-separated elsewhere). The output
    /// directory is always allowed.
    #[arg(long, env = "GAEA2_ALLOWED_DIRS")]
    allowed_dirs: Option<String>,

    /// Maximum number of concurrent Gaea.Swarm builds
    #[arg(long, default_value_t = 1, env = "GAEA2_MAX_CONCURRENT_BUILDS")]
    max_concurrent_builds: usize,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    let version = env!("CARGO_PKG_VERSION");
    tracing::info!("Starting Gaea2 MCP Server v{version}");

    let config = Gaea2Config::new(args.gaea_path, args.output_dir, args.allowed_dirs);
    let gaea2_server = Gaea2Server::new(config, args.max_concurrent_builds);

    let mut builder = MCPServer::builder("gaea2", version);
    builder = args.server.apply_to(builder);
    for tool in gaea2_server.tools() {
        builder = builder.tool_boxed(tool);
    }
    let server = builder.build();

    tracing::info!("Output directory: {}", gaea2_server.output_dir());
    match gaea2_server.gaea_path() {
        Some(path) => tracing::info!("Gaea2 executable: {path}"),
        None => tracing::warn!(
            "Gaea2 executable not configured - run/validate_runtime tools are disabled"
        ),
    }

    server.run().await?;
    Ok(())
}
