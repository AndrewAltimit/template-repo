//! MCP Blender server.
//!
//! Exposes headless Blender (scene building, materials, physics, geometry
//! nodes, rendering, import/export) as MCP tools. Every tool runs one of the
//! Python scripts in `scripts/` inside a `blender --background` subprocess;
//! renders and bakes run as cancellable background jobs.
//!
//! ```text
//! mcp-blender --mode stdio                       # MCP over stdio
//! mcp-blender --mode standalone --port 8017      # MCP over HTTP
//! curl http://localhost:8017/health
//! ```
//!
//! Configuration is read from environment variables; see `README.md`.

mod blender;
mod config;
mod jobs;
mod paths;
mod server;
mod tools;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use config::Config;
use server::BlenderServer;

/// CLI arguments.
#[derive(Parser)]
#[command(name = "mcp-blender")]
#[command(about = "MCP server for headless Blender 3D content creation and rendering")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    let blender_server = BlenderServer::new(Config::from_env());

    let mut builder = MCPServer::builder("blender", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);
    for tool in blender_server.tools() {
        builder = builder.tool_boxed(tool);
    }
    builder.build().run().await?;
    Ok(())
}
