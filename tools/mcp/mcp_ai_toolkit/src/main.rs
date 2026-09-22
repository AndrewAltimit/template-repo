//! AI Toolkit MCP Server
//!
//! MCP tools for managing LoRA training with [AI Toolkit](https://github.com/ostris/ai-toolkit):
//! training configs, datasets, training jobs, trained weights and host stats.
//! Runs next to AI Toolkit on the GPU machine (see `docker/ai-toolkit.Dockerfile`).
//!
//! Usage:
//!     # HTTP (default port 8020); `--mode http` is an alias of `standalone`
//!     mcp-ai-toolkit --mode standalone --port 8020
//!
//!     # STDIO for a local MCP client on the GPU host
//!     mcp-ai-toolkit --mode stdio
//!
//!     # Local MCP proxy forwarding to the remote GPU machine's REST API
//!     mcp-ai-toolkit --mode client --port 8020 --backend-url http://192.168.0.222:8020

mod config;
mod datasets;
mod jobs;
mod logs;
mod models;
mod server;
mod system;
mod training_config;
mod types;

use clap::{Parser, ValueEnum};
use mcp_core::{MCPServer, ServerMode, init_logging};
use tracing::warn;

use server::AIToolkitServer;

/// Parse `--mode`, accepting `http` as an alias for `standalone`.
fn parse_mode(s: &str) -> Result<ServerMode, String> {
    if s.eq_ignore_ascii_case("http") {
        return Ok(ServerMode::Standalone);
    }
    ServerMode::from_str(s, true)
        .map_err(|_| format!("invalid mode '{s}' (standalone|http|server|client|stdio)"))
}

/// CLI arguments.
#[derive(Parser, Debug)]
#[command(name = "mcp-ai-toolkit", version)]
#[command(about = "MCP server for AI Toolkit - LoRA training management")]
struct Args {
    /// Server mode: standalone (alias: http), server, client, stdio
    #[arg(long, short, default_value = "standalone", value_parser = parse_mode)]
    mode: ServerMode,

    /// Port to listen on (ignored in stdio mode)
    #[arg(long, short, default_value_t = 8020)]
    port: u16,

    /// Accepted for compatibility; the server always binds 0.0.0.0
    #[arg(long)]
    host: Option<String>,

    /// Backend URL for client mode (e.g. http://192.168.0.222:8020)
    #[arg(long)]
    backend_url: Option<String>,

    /// Log level (overridden by RUST_LOG)
    #[arg(long, default_value = "info")]
    log_level: String,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.log_level);

    if let Some(host) = &args.host
        && host != "0.0.0.0"
    {
        warn!("--host {host} is ignored: the server binds 0.0.0.0");
    }
    if args.mode == ServerMode::Client && args.backend_url.is_none() {
        anyhow::bail!("--backend-url is required in client mode");
    }

    let mut builder = MCPServer::builder("ai-toolkit", env!("CARGO_PKG_VERSION"))
        .port(args.port)
        .mode(args.mode);
    if let Some(url) = &args.backend_url {
        builder = builder.backend_url(url.clone());
    }

    // Client mode forwards every call to the backend; local tools are not needed
    // (and must not create directories on the client machine).
    if args.mode != ServerMode::Client {
        for tool in AIToolkitServer::from_env().tools() {
            builder = builder.tool_boxed(tool);
        }
    }

    builder.build().run().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_entrypoint_arguments() {
        // docker/entrypoints/ai-toolkit-entrypoint.sh invocation
        let a = Args::try_parse_from([
            "mcp-ai-toolkit",
            "--mode",
            "http",
            "--host",
            "0.0.0.0",
            "--port",
            "8020",
        ])
        .unwrap();
        assert_eq!(a.mode, ServerMode::Standalone);
        assert_eq!(a.port, 8020);
    }

    #[test]
    fn parses_modes_and_defaults() {
        let a = Args::try_parse_from(["x"]).unwrap();
        assert_eq!((a.mode, a.port), (ServerMode::Standalone, 8020));
        let a = Args::try_parse_from(["x", "-m", "STDIO"]).unwrap();
        assert_eq!(a.mode, ServerMode::Stdio);
        let a =
            Args::try_parse_from(["x", "--mode", "client", "--backend-url", "http://h:1"]).unwrap();
        assert_eq!(a.mode, ServerMode::Client);
        assert!(Args::try_parse_from(["x", "--mode", "bogus"]).is_err());
    }
}
