//! MCP Code Quality Server
//!
//! A Rust-based MCP server for code quality tools - formatting, linting, testing.
//! Uses modern tools like ruff (10-100x faster than black/flake8).
//!
//! # Usage
//!
//! ```bash
//! # Start HTTP server on default port 8010
//! mcp-code-quality
//!
//! # Custom port
//! MCP_CODE_QUALITY_PORT=9000 mcp-code-quality
//!
//! # With custom allowed paths
//! MCP_CODE_QUALITY_ALLOWED_PATHS=/workspace,/app mcp-code-quality
//! ```

mod config;
mod error;
mod security;
mod server;
mod subprocess;
mod tools;

use clap::Parser;
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use config::Config;

/// MCP Code Quality Server - Fast code formatting, linting, and testing
#[derive(Parser, Debug)]
#[command(name = "mcp-code-quality")]
#[command(about = "MCP server for code quality tools", long_about = None)]
struct Args {
    /// Port to listen on (default: 8010, or MCP_CODE_QUALITY_PORT env var)
    #[arg(short, long, env = "MCP_CODE_QUALITY_PORT", default_value = "8010")]
    port: u16,

    /// Host to bind to (default: 0.0.0.0)
    #[arg(long, env = "MCP_CODE_QUALITY_HOST", default_value = "0.0.0.0")]
    host: String,

    /// Disable rate limiting
    #[arg(long)]
    no_rate_limit: bool,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "mcp_code_quality=info,tower_http=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let args = Args::parse();

    // Load config from environment, with CLI overrides
    let mut config = Config::from_env();
    config.port = args.port;
    config.host = args.host;
    if args.no_rate_limit {
        config.rate_limit_enabled = false;
    }

    info!(
        "MCP Code Quality Server v{} starting...",
        env!("CARGO_PKG_VERSION")
    );
    info!("Listening on {}:{}", config.host, config.port);
    info!(
        "Rate limiting: {}",
        if config.rate_limit_enabled {
            "enabled"
        } else {
            "disabled"
        }
    );
    info!("Allowed paths: {:?}", config.allowed_paths);

    // Start server
    server::start_server(config).await?;

    Ok(())
}
