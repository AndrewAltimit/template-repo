//! MCP OpenCode Server
//!
//! Provides AI-powered code assistance via OpenRouter API.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-opencode --mode standalone --port 8014
//!
//!     # Test endpoints
//!     curl http://localhost:8014/health
//!     curl http://localhost:8014/mcp/tools

mod opencode;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::OpenCodeServer;
use types::OpenCodeConfig;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-opencode")]
#[command(about = "MCP server for AI-powered code assistance via OpenRouter")]
#[command(version = "1.1.0")]
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

    // Load configuration from environment
    let config = OpenCodeConfig::from_env();

    // Create OpenCode server
    let opencode_server = OpenCodeServer::new(config);

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("opencode", "1.1.0");
    builder = args.server.apply_to(builder);

    for tool in opencode_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
