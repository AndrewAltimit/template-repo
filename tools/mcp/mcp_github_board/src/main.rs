//! MCP GitHub Board Server
//!
//! Exposes GitHub Projects v2 board operations (ready-work queue, claims,
//! status, dependencies, approvals, stale-claim cleanup) as MCP tools by
//! delegating to the `board-manager` CLI.
//!
//! Usage:
//!     # STDIO (for Claude Code / .mcp.json)
//!     mcp-github-board --mode stdio
//!
//!     # HTTP (default port 8022)
//!     mcp-github-board --mode standalone
//!     curl http://localhost:8022/health
//!     curl http://localhost:8022/mcp/tools

mod args;
mod runner;
mod server;
mod specs;

use clap::{CommandFactory, FromArgMatches, Parser};
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use runner::{CliRunner, DEFAULT_TIMEOUT_SECS, RunnerConfig};
use server::{GitHubBoardServer, ServerOptions, VERSION};

/// Default HTTP port for this server (mcp-core's generic default is 8000).
const DEFAULT_PORT: &str = "8022";

/// CLI arguments
#[derive(Parser)]
#[command(name = "mcp-github-board")]
#[command(about = "MCP server for GitHub Projects v2 board operations (wraps board-manager)")]
#[command(version)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Path to the board-manager binary (disables auto-discovery)
    #[arg(long, env = "BOARD_MANAGER_PATH", value_name = "PATH")]
    board_manager: Option<PathBuf>,

    /// Board config file passed to board-manager as --config (default:
    /// board-manager's own lookup: $BOARD_CONFIG_PATH, then ai-agents-board.yml
    /// in the working directory or a parent, then BOARD_* env vars)
    #[arg(long, value_name = "PATH")]
    board_config: Option<PathBuf>,

    /// Timeout for a single board-manager call, in seconds
    #[arg(
        long,
        env = "GITHUB_BOARD_TIMEOUT_SECS",
        default_value_t = DEFAULT_TIMEOUT_SECS,
        value_parser = clap::value_parser!(u64).range(1..=3600)
    )]
    timeout_secs: u64,

    /// Only register read-only tools (no claims, status or dependency changes)
    /// (env accepts true/false, 1/0, yes/no, on/off)
    #[arg(
        long,
        env = "GITHUB_BOARD_READ_ONLY",
        action = clap::ArgAction::SetTrue,
        value_parser = clap::builder::BoolishValueParser::new()
    )]
    read_only: bool,
}

/// Parse CLI arguments, overriding mcp-core's generic default port.
fn parse_args() -> Args {
    let cmd = Args::command().mut_arg("port", |a| a.default_value(DEFAULT_PORT));
    let matches = cmd.get_matches();
    Args::from_arg_matches(&matches).unwrap_or_else(|e| e.exit())
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = parse_args();

    init_logging(&args.server.log_level);

    let runner = Arc::new(CliRunner::new(RunnerConfig {
        board_manager: args.board_manager.clone(),
        board_config: args.board_config.clone(),
        timeout: Duration::from_secs(args.timeout_secs),
    }));
    let board_server = GitHubBoardServer::new(
        runner,
        ServerOptions {
            read_only: args.read_only,
        },
    );

    let mut builder = MCPServer::builder("github-board", VERSION);
    builder = args.server.apply_to(builder);
    for tool in board_server.tools() {
        builder = builder.tool_boxed(tool);
    }

    builder.build().run().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(argv: &[&str]) -> Args {
        let cmd = Args::command().mut_arg("port", |a| a.default_value(DEFAULT_PORT));
        let m = cmd
            .try_get_matches_from(std::iter::once("mcp-github-board").chain(argv.iter().copied()))
            .unwrap();
        Args::from_arg_matches(&m).unwrap()
    }

    #[test]
    fn cli_definition_is_valid() {
        Args::command().debug_assert();
    }

    #[test]
    fn defaults() {
        let a = parse(&[]);
        assert_eq!(a.server.port, 8022);
        assert!(!a.read_only);
        assert!(a.board_config.is_none());
    }

    #[test]
    fn explicit_flags() {
        let a = parse(&[
            "--mode",
            "stdio",
            "--port",
            "9000",
            "--timeout-secs",
            "30",
            "--read-only",
            "--board-config",
            "b.yml",
            "--board-manager",
            "/x/board-manager",
        ]);
        assert_eq!(a.server.port, 9000);
        assert_eq!(a.timeout_secs, 30);
        assert!(a.read_only);
        assert_eq!(a.board_config, Some(PathBuf::from("b.yml")));
        assert_eq!(a.board_manager, Some(PathBuf::from("/x/board-manager")));
    }

    #[test]
    fn timeout_is_bounded() {
        let cmd = Args::command();
        assert!(
            cmd.try_get_matches_from(["x", "--timeout-secs", "0"])
                .is_err()
        );
    }
}
