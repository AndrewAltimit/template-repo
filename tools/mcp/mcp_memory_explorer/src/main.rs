//! MCP Memory Explorer Server
//!
//! Read-only process memory exploration for reverse engineering and agent
//! integration with legacy software: process/module listing, typed reads, hex
//! dumps, signature scans, value search with refinement, pointer chains, and
//! watches.
//!
//! Backends: Windows (`ReadProcessMemory`/`VirtualQueryEx`/Toolhelp) and Linux
//! (`/proc/<pid>/mem` + `/proc/<pid>/maps`). Other platforms only support
//! `list_processes`.
//!
//! Usage:
//!     mcp-memory-explorer --mode stdio                    # MCP over STDIO (Claude Code)
//!     mcp-memory-explorer --mode standalone --port 8028   # HTTP (default port 8028)
//!     curl http://localhost:8028/health

mod address;
mod backend;
mod explorer;
mod pattern;
mod server;
mod types;

use clap::{CommandFactory, FromArgMatches, Parser};
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};

use server::MemoryExplorerServer;

/// Default HTTP port for this server (the shared core default is 8000).
const DEFAULT_PORT: &str = "8028";

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-memory-explorer")]
#[command(about = "MCP server for read-only process memory exploration and reverse engineering")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,
}

fn parse_args() -> Args {
    let matches = Args::command()
        .mut_arg("port", |a| a.default_value(DEFAULT_PORT))
        .get_matches();
    Args::from_arg_matches(&matches).unwrap_or_else(|e| e.exit())
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = parse_args();

    init_logging(&args.server.log_level);

    let memory_server = MemoryExplorerServer::new();

    let mut builder = MCPServer::builder("memory-explorer", env!("CARGO_PKG_VERSION"));
    builder = args.server.apply_to(builder);
    for tool in memory_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    builder.build().run().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_port_is_8028() {
        let matches = Args::command()
            .mut_arg("port", |a| a.default_value(DEFAULT_PORT))
            .try_get_matches_from(["mcp-memory-explorer"])
            .unwrap();
        let args = Args::from_arg_matches(&matches).unwrap();
        assert_eq!(args.server.port, 8028);

        let matches = Args::command()
            .mut_arg("port", |a| a.default_value(DEFAULT_PORT))
            .try_get_matches_from(["mcp-memory-explorer", "--port", "9000", "--mode", "stdio"])
            .unwrap();
        let args = Args::from_arg_matches(&matches).unwrap();
        assert_eq!(args.server.port, 9000);
    }
}
