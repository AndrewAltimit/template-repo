//! MCP AgentCore Memory Server
//!
//! Persistent memory for AI agents backed by a self-hosted ChromaDB vector
//! database: short-term session events, long-term facts in namespaces, and
//! semantic search over those facts. Embeddings are computed locally (ChromaDB's
//! HTTP API does not embed text itself).
//!
//! Usage:
//!     # STDIO mode (for Claude Code)
//!     mcp-agentcore-memory --mode stdio
//!
//!     # Standalone HTTP mode
//!     mcp-agentcore-memory --mode standalone --port 8023
//!
//!     # Download the embedding model and exit (used by the Docker build)
//!     mcp-agentcore-memory --prefetch-model
//!
//! See README.md for the environment variables.

mod cache;
mod config;
mod embedding;
mod namespaces;
mod sanitize;
mod server;
mod service;
mod store;

#[cfg(test)]
mod tests;

use std::sync::Arc;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use tracing::info;

use config::Config;
use service::MemoryService;
use store::chroma::ChromaStore;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-agentcore-memory")]
#[command(about = "MCP server for AI agent memory using ChromaDB")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Load (downloading if needed) the embedding model, then exit.
    #[arg(long)]
    prefetch_model: bool,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    let config = Config::from_env();
    let embedder = embedding::from_config(&config);

    if args.prefetch_model {
        embedder
            .embed(vec!["warm-up".to_string()])
            .await
            .map_err(|e| anyhow::anyhow!(e))?;
        info!(
            "Embedding model '{}' ready in {}",
            embedder.id(),
            config.model_cache_dir.display()
        );
        return Ok(());
    }

    info!(
        "Embedder: {} ({} dims), collection prefix: {}",
        embedder.id(),
        embedder.dimension(),
        config.collection_prefix
    );
    let store = ChromaStore::new(&config).map_err(|e| anyhow::anyhow!(e))?;
    let service = Arc::new(MemoryService::new(&config, Arc::new(store), embedder));

    let mut builder = MCPServer::builder("agentcore-memory", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);
    for tool in server::tools(service) {
        builder = builder.tool_boxed(tool);
    }
    builder.build().run().await?;
    Ok(())
}
