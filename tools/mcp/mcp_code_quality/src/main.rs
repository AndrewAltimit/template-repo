//! MCP Code Quality Server
//!
//! Provides code quality tools via MCP - format checking, linting, testing,
//! type checking, security scanning, and dependency auditing.
//!
//! Usage:
//!     # Standalone mode (default)
//!     mcp-code-quality --mode standalone --port 8010
//!
//!     # Test endpoints
//!     curl http://localhost:8010/health
//!     curl http://localhost:8010/mcp/tools

mod engine;
mod server;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use std::path::PathBuf;

use crate::engine::DEFAULT_TIMEOUT_SECS;
use server::CodeQualityServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-code-quality")]
#[command(
    about = "MCP server for code quality - format checking, linting, testing, and security scanning"
)]
#[command(version = "2.0.0")]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Timeout in seconds for subprocess operations
    #[arg(long, default_value_t = DEFAULT_TIMEOUT_SECS, env = "MCP_CODE_QUALITY_TIMEOUT")]
    timeout: u64,

    /// Comma-separated list of allowed paths
    #[arg(
        long,
        default_value = "/workspace,/app,/home",
        env = "MCP_CODE_QUALITY_ALLOWED_PATHS"
    )]
    allowed_paths: String,

    /// Path to audit log file
    #[arg(
        long,
        default_value = "/var/log/mcp-code-quality/audit.log",
        env = "MCP_CODE_QUALITY_AUDIT_LOG"
    )]
    audit_log: PathBuf,

    /// Enable rate limiting
    #[arg(long, default_value = "true", env = "MCP_CODE_QUALITY_RATE_LIMIT")]
    rate_limit: bool,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_logging(&args.server.log_level);

    // Parse allowed paths
    let allowed_paths: Vec<String> = args
        .allowed_paths
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    // Create code quality server
    let quality_server =
        CodeQualityServer::new(args.timeout, allowed_paths, args.audit_log, args.rate_limit);

    // Build MCP server with all tools
    let mut builder = MCPServer::builder("code-quality", "2.0.0");
    builder = args.server.apply_to(builder);

    for tool in quality_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    let server = builder.build();

    server.run().await?;

    Ok(())
}
