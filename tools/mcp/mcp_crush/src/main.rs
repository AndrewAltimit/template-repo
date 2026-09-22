//! MCP Crush Server
//!
//! Code generation / explanation / conversion by running the charmbracelet
//! `crush` CLI against OpenRouter. See README.md for configuration.
//!
//! Usage:
//!     # STDIO mode (MCP clients such as Claude Code)
//!     mcp-crush --mode stdio
//!
//!     # Standalone HTTP mode
//!     mcp-crush --mode standalone --port 8015
//!     curl http://localhost:8015/health
//!     curl http://localhost:8015/mcp/tools

mod config;
mod consult;
mod crush;
mod runner;
mod server;
mod util;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use tracing::{debug, warn};

use config::CrushConfig;
use server::CrushServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-crush")]
#[command(about = "MCP server for Crush AI code generation via OpenRouter")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Load .env file if present
    let _ = dotenvy::dotenv();

    let args = Args::parse();
    init_logging(&args.server.log_level);

    let config = CrushConfig::from_env();
    debug!(?config, "Loaded configuration");
    if config.api_key.is_empty() {
        warn!("OPENROUTER_API_KEY is not set; consult_crush will return an error until it is");
    }

    let crush_server = CrushServer::new(config);
    let mut builder = MCPServer::builder("crush", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);
    for tool in crush_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    builder.build().run().await?;
    Ok(())
}
