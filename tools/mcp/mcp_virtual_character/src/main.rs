//! Virtual Character MCP server CLI entry point.

use anyhow::Result;
use clap::{CommandFactory, FromArgMatches, Parser};
use mcp_core::{init_logging, server::MCPServerArgs, MCPServer};
use mcp_virtual_character::backends::BACKEND_NAMES;
use mcp_virtual_character::VirtualCharacterServer;

/// Default HTTP port for this server (matches docker-compose and .mcp.json.full).
const DEFAULT_PORT: &str = "8025";

/// Virtual Character MCP Server
#[derive(Parser)]
#[command(name = "mcp-virtual-character")]
#[command(about = "MCP server for virtual character control via VRChat OSC")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Connect this backend at startup (mock, vrchat_remote). vrchat_remote
    /// reads its configuration from VIRTUAL_CHARACTER_* environment variables.
    #[arg(long, env = "VIRTUAL_CHARACTER_BACKEND")]
    backend: Option<String>,
}

fn parse_args() -> Args {
    let mut cmd = Args::command();
    // Override the shared default port (8000) with this server's port.
    if cmd.get_arguments().any(|a| a.get_id() == "port") {
        cmd = cmd.mut_arg("port", |a| a.default_value(DEFAULT_PORT));
    }
    let matches = cmd.get_matches();
    Args::from_arg_matches(&matches).unwrap_or_else(|e| e.exit())
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = parse_args();
    init_logging(&args.server.log_level);

    let version = env!("CARGO_PKG_VERSION");
    tracing::info!("Starting Virtual Character MCP Server v{}", version);

    let vc_server = VirtualCharacterServer::new();

    if let Some(backend) = args.backend.as_deref().filter(|b| !b.is_empty()) {
        if !BACKEND_NAMES.contains(&backend) {
            anyhow::bail!(
                "unknown --backend '{}' (expected one of: {})",
                backend,
                BACKEND_NAMES.join(", ")
            );
        }
        match vc_server
            .connect_backend(backend, serde_json::json!({}))
            .await
        {
            Ok(_) => tracing::info!("Auto-connected backend: {}", backend),
            Err(e) => tracing::warn!(
                "Auto-connect to {} failed: {} (use set_backend)",
                backend,
                e
            ),
        }
    }

    let mut builder = MCPServer::builder("virtual-character", version);
    builder = args.server.apply_to(builder);
    for tool in vc_server.tools() {
        builder = builder.tool_boxed(tool);
    }
    let server = builder.build();

    tracing::info!(
        "Virtual Character MCP Server ready (mode: {}, backends: {})",
        args.server.mode,
        BACKEND_NAMES.join(", ")
    );
    server.run().await?;
    Ok(())
}
