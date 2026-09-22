//! MCP ElevenLabs Speech Server
//!
//! Exposes ElevenLabs text-to-speech and sound effect generation as MCP
//! tools. Generated audio is written to a local output directory and the
//! tools return the file path.
//!
//! Usage:
//!     # STDIO mode (Claude Code / .mcp.json)
//!     ELEVENLABS_API_KEY=your_key mcp-elevenlabs-speech --mode stdio
//!
//!     # HTTP mode (docker compose); `--mode http` is accepted as an alias
//!     ELEVENLABS_API_KEY=your_key mcp-elevenlabs-speech --mode standalone --port 8018
//!     curl http://localhost:8018/health

mod client;
mod config;
mod server;
mod storage;
mod types;

use clap::Parser;
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use tracing::{info, warn};

use config::Config;
use server::ElevenLabsSpeechServer;

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-elevenlabs-speech")]
#[command(about = "MCP server for ElevenLabs text-to-speech synthesis")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

/// Map the legacy `--mode http` (used by docker-compose and the Python-era
/// server) to `standalone`, which is the mcp-core HTTP mode. Without this the
/// container exits immediately with a clap "invalid value" error.
fn normalize_mode_alias(args: impl IntoIterator<Item = String>) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for arg in args {
        let prev_is_mode = out.last().is_some_and(|p| p == "--mode" || p == "-m");
        if prev_is_mode && arg.eq_ignore_ascii_case("http") {
            out.push("standalone".to_string());
        } else if arg.eq_ignore_ascii_case("--mode=http") {
            out.push("--mode=standalone".to_string());
        } else {
            out.push(arg);
        }
    }
    out
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse_from(normalize_mode_alias(std::env::args()));

    init_logging(&args.server.log_level);

    let config = Config::from_env();
    info!(
        "Output directory: {} (model default: {}, voice default: {})",
        config.output_dir.display(),
        config.default_model,
        config.default_voice
    );
    let speech_server = ElevenLabsSpeechServer::new(config);
    if !speech_server.has_api_key() {
        warn!(
            "ELEVENLABS_API_KEY is not set: only list_presets and clear_cache will work until it is configured"
        );
    }

    let mut builder = MCPServer::builder("elevenlabs-speech", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);
    for tool in speech_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    builder.build().run().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn v(args: &[&str]) -> Vec<String> {
        args.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn http_mode_alias() {
        assert_eq!(
            normalize_mode_alias(v(&["bin", "--mode", "http", "--port", "8018"])),
            v(&["bin", "--mode", "standalone", "--port", "8018"])
        );
        assert_eq!(
            normalize_mode_alias(v(&["bin", "--mode=http"])),
            v(&["bin", "--mode=standalone"])
        );
        assert_eq!(
            normalize_mode_alias(v(&["bin", "--mode", "stdio"])),
            v(&["bin", "--mode", "stdio"])
        );
        let parsed = Args::try_parse_from(normalize_mode_alias(v(&["bin", "-m", "http"]))).unwrap();
        assert_eq!(parsed.server.mode, mcp_core::ServerMode::Standalone);
    }
}
