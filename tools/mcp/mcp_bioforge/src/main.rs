//! MCP BioForge Server
//!
//! Provides biological automation tools via MCP -- liquid handling, thermal
//! control, plate imaging, colony counting, and protocol management.
//!
//! Phase 1: All tools return mock responses for end-to-end agent testing.
//!
//! Usage:
//!     mcp-bioforge --mode standalone --port 8030
//!     mcp-bioforge --mode stdio

mod tools;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

/// CLI arguments for the BioForge MCP server.
#[derive(Parser)]
#[command(name = "mcp-bioforge")]
#[command(about = "MCP server for BioForge biological automation platform")]
#[command(version = "0.1.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    let bioforge = tools::BioForgeServer::new();

    let mut builder = MCPServer::builder("bioforge", "0.1.0");
    builder = args.server.apply_to(builder);

    for tool in bioforge.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();
    server.run().await?;

    Ok(())
}
