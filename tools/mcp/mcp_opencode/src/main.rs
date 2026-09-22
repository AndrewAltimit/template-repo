//! MCP OpenCode Server
//!
//! AI code assistance (generate / refactor / review / explain) backed by the
//! OpenRouter chat-completions API. See README.md for configuration.
//!
//! Usage:
//!     # STDIO mode (MCP clients such as Claude Code)
//!     mcp-opencode --mode stdio
//!
//!     # Standalone HTTP mode
//!     mcp-opencode --mode standalone --port 8014
//!     curl http://localhost:8014/health
//!     curl http://localhost:8014/mcp/tools

mod config;
mod consult;
mod opencode;
mod server;
#[cfg(test)]
mod test_support;
mod util;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use tracing::{debug, warn};

use config::OpenCodeConfig;
use server::OpenCodeServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-opencode")]
#[command(about = "MCP server for AI-powered code assistance via OpenRouter")]
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

    let config = OpenCodeConfig::from_env();
    debug!(?config, "Loaded configuration");
    if config.api_key.is_empty() {
        warn!("OPENROUTER_API_KEY is not set; consult_opencode will return an error until it is");
    }

    let opencode_server = OpenCodeServer::new(config);
    let mut builder = MCPServer::builder("opencode", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);
    for tool in opencode_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    builder.build().run().await?;
    Ok(())
}
