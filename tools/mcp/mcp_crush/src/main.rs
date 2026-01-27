//! MCP Crush Server
//!
//! Provides Crush AI code generation via OpenRouter API.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-crush --mode standalone --port 8015
//!
//!     # Test endpoints
//!     curl http://localhost:8015/health
//!     curl http://localhost:8015/mcp/tools

mod crush;
mod server;
mod types;

use clap::Parser;
use mcp_core::{init_logging, server::MCPServerArgs, MCPServer};

use server::CrushServer;
use types::CrushConfig;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-crush")]
#[command(about = "MCP server for Crush AI code generation via OpenRouter")]
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
    let config = CrushConfig::from_env();

    // Create Crush server
    let crush_server = CrushServer::new(config);

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("crush", "2.0.0");
    builder = args.server.apply_to(builder);

    for tool in crush_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
