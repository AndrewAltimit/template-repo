//! MCP AgentCore Memory Server
//!
//! Provides MCP tools for AI agent memory using ChromaDB vector database.
//!
//! > This MCP server was converted from Python to Rust for improved performance
//! > and consistency with the project's container-first philosophy.
//! > See the MIT License in the repository root for licensing information.
//!
//! Usage:
//!     # STDIO mode (for Claude Code)
//!     mcp-agentcore-memory --mode stdio
//!
//!     # Standalone HTTP mode
//!     mcp-agentcore-memory --mode standalone --port 8023
//!
//! Environment variables:
//!     CHROMADB_HOST: ChromaDB host (default: localhost)
//!     CHROMADB_PORT: ChromaDB port (default: 8000)
//!     CHROMADB_COLLECTION: Collection prefix (default: agent_memory)

mod cache;
mod client;
mod sanitize;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::MemoryServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-agentcore-memory")]
#[command(about = "MCP server for AI agent memory using ChromaDB")]
#[command(version = "1.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Create memory server
    let memory_server = MemoryServer::new();

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("agentcore-memory", "1.0.0");
    builder = args.server.apply_to(builder);

    for tool in memory_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
