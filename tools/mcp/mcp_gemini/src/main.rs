// Allow collapsible_if - clippy suggests let-chains which require nightly
#![allow(clippy::collapsible_if)]

//! MCP Gemini Server
//!
//! Provides Gemini AI integration for second opinions and validation via MCP tools.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-gemini --mode standalone --port 8006
//!
//!     # Test endpoints
//!     curl http://localhost:8006/health
//!     curl http://localhost:8006/mcp/tools

mod gemini;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::GeminiServer;
use types::GeminiConfig;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-gemini")]
#[command(about = "MCP server for Gemini AI integration and consultation")]
#[command(version = "2.0.0")]
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
    let config = GeminiConfig::from_env();

    // Create Gemini server
    let gemini_server = GeminiServer::new(config);

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("gemini", "2.0.0");
    builder = args.server.apply_to(builder);

    for tool in gemini_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
