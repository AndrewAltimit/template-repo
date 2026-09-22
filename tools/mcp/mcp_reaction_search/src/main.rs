//! MCP Reaction Search Server
//!
//! Semantic search over the anime reaction image catalog published in the
//! `AndrewAltimit/Media` repository.
//!
//! ```text
//! mcp-reaction-search --mode stdio                  # MCP over stdin/stdout
//! mcp-reaction-search --mode standalone --port 8024 # MCP over HTTP
//! curl http://localhost:8024/health
//! ```
//!
//! See README.md for tools, environment variables, and caching behaviour.

mod config;
mod embed;
mod engine;
mod server;
mod service;
mod text;
mod types;

use std::path::PathBuf;
use std::time::Duration;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use config::{ConfigSettings, DEFAULT_CONFIG_URL, default_cache_root};
use service::{ReactionService, ServiceSettings};

/// CLI arguments. Every reaction-search option can also be set through the
/// environment variable named in its help text.
#[derive(Parser, Debug)]
#[command(name = "mcp-reaction-search")]
#[command(about = "MCP server for semantic reaction image search")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Reaction config source: http(s) URL, file:// URL, or local path
    #[arg(long, env = "REACTION_SEARCH_CONFIG_URL", default_value = DEFAULT_CONFIG_URL)]
    config_url: String,

    /// Cache directory for the config and the embedding model
    /// [default: <platform cache dir>/mcp_reaction_search]
    #[arg(long, env = "REACTION_SEARCH_CACHE_DIR")]
    cache_dir: Option<PathBuf>,

    /// Config cache TTL in seconds (default: 1 week)
    #[arg(
        long,
        env = "REACTION_SEARCH_CACHE_TTL_SECS",
        default_value_t = 604_800
    )]
    cache_ttl_secs: u64,

    /// Total timeout for fetching the config, in seconds
    #[arg(long, env = "REACTION_SEARCH_FETCH_TIMEOUT_SECS", default_value_t = 15)]
    fetch_timeout_secs: u64,

    /// Seconds a search waits for a loading model before answering with
    /// keyword matching
    #[arg(long, env = "REACTION_SEARCH_MODEL_WAIT_SECS", default_value_t = 30)]
    model_wait_secs: u64,

    /// Seconds before retrying a failed model load
    #[arg(long, env = "REACTION_SEARCH_MODEL_RETRY_SECS", default_value_t = 300)]
    model_retry_secs: u64,

    /// Load the config and embedding model in the background at startup so
    /// the first search is fast (set to false for fully lazy loading)
    #[arg(
        long,
        env = "REACTION_SEARCH_PRELOAD",
        default_value_t = true,
        action = clap::ArgAction::Set
    )]
    preload: bool,
}

impl Args {
    fn service_settings(&self) -> ServiceSettings {
        let cache_dir = self
            .cache_dir
            .clone()
            .unwrap_or_else(|| default_cache_root().join("mcp_reaction_search"));
        ServiceSettings {
            model_cache_dir: cache_dir.join("models"),
            config: ConfigSettings {
                config_url: self.config_url.clone(),
                cache_dir,
                cache_ttl: Duration::from_secs(self.cache_ttl_secs),
                fetch_timeout: Duration::from_secs(self.fetch_timeout_secs.max(1)),
            },
            model_wait: Duration::from_secs(self.model_wait_secs),
            model_retry: Duration::from_secs(self.model_retry_secs),
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    let service = ReactionService::new(args.service_settings());
    if args.preload {
        service.preload();
    }

    let mut builder = MCPServer::builder("reaction-search", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);
    for tool in server::tools(&service) {
        builder = builder.tool_boxed(tool);
    }
    builder.build().run().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cli_defaults() {
        let args = Args::try_parse_from(["mcp-reaction-search"]).unwrap();
        assert!(args.preload);
        let s = args.service_settings();
        assert_eq!(s.config.cache_ttl, Duration::from_secs(604_800));
        assert!(s.model_cache_dir.ends_with("models"));
    }

    #[test]
    fn cli_overrides() {
        let args = Args::try_parse_from([
            "mcp-reaction-search",
            "--mode",
            "stdio",
            "--preload",
            "false",
            "--cache-dir",
            "/tmp/rs",
            "--config-url",
            "/tmp/config.yaml",
            "--fetch-timeout-secs",
            "0",
        ])
        .unwrap();
        assert!(!args.preload);
        let s = args.service_settings();
        assert_eq!(s.config.cache_dir, PathBuf::from("/tmp/rs"));
        assert_eq!(s.model_cache_dir, PathBuf::from("/tmp/rs/models"));
        assert_eq!(s.config.config_url, "/tmp/config.yaml");
        assert_eq!(s.config.fetch_timeout, Duration::from_secs(1));
    }
}
