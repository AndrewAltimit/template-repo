//! MCP Code Quality Server
//!
//! Exposes format checking, auto-formatting, linting, pytest, ty type
//! checking, bandit security scanning, pip-audit dependency auditing, and
//! markdown link checking as MCP tools. Every tool runs an external program
//! as a bounded subprocess (no shell, hard timeout, capped output) on paths
//! restricted to a configured allowlist, and every call is audit-logged.
//!
//! Usage:
//!     # STDIO (how .mcp.json launches it)
//!     mcp-code-quality --mode stdio
//!
//!     # HTTP
//!     mcp-code-quality --mode standalone --port 8010
//!     curl http://localhost:8010/health
//!     curl http://localhost:8010/mcp/tools

mod audit;
mod commands;
mod engine;
mod parsers;
mod paths;
mod process;
mod ratelimit;
mod server;
mod types;

use clap::{ArgAction, Parser};
use mcp_core::{MCPServer, init_logging, server::MCPServerArgs};
use std::path::PathBuf;
use std::time::Duration;

use engine::{
    CodeQualityEngine, DEFAULT_MAX_CONCURRENT, DEFAULT_MAX_OUTPUT_BYTES, DEFAULT_TIMEOUT_SECS,
    EngineConfig, VERSION,
};
use server::CodeQualityServer;

/// CLI arguments.
#[derive(Parser, Debug)]
#[command(name = "mcp-code-quality", version = VERSION)]
#[command(
    about = "MCP server for code quality - format checking, linting, testing, and security scanning"
)]
struct Args {
    #[command(flatten)]
    server: MCPServerArgs,

    /// Timeout in seconds for each external tool run (1..=86400)
    #[arg(
        long,
        default_value_t = DEFAULT_TIMEOUT_SECS,
        env = "MCP_CODE_QUALITY_TIMEOUT",
        value_parser = clap::value_parser!(u64).range(1..=86_400)
    )]
    timeout: u64,

    /// Comma-separated list of directories tools may operate on
    #[arg(
        long,
        default_value = "/workspace,/app,/home",
        env = "MCP_CODE_QUALITY_ALLOWED_PATHS"
    )]
    allowed_paths: String,

    /// Path to the JSON-lines audit log file
    #[arg(
        long,
        default_value = "/var/log/mcp-code-quality/audit.log",
        env = "MCP_CODE_QUALITY_AUDIT_LOG"
    )]
    audit_log: PathBuf,

    /// Rotate the audit log to `<file>.1` once it exceeds this many bytes
    #[arg(
        long,
        default_value_t = audit::DEFAULT_MAX_BYTES,
        env = "MCP_CODE_QUALITY_AUDIT_LOG_MAX_BYTES",
        value_parser = clap::value_parser!(u64).range(4096..)
    )]
    audit_log_max_bytes: u64,

    /// Enable per-tool rate limiting (`--rate-limit false` to disable)
    #[arg(
        long,
        default_value_t = true,
        env = "MCP_CODE_QUALITY_RATE_LIMIT",
        action = ArgAction::Set
    )]
    rate_limit: bool,

    /// Maximum bytes of stdout/stderr kept per tool run (head and tail are kept)
    #[arg(
        long,
        default_value_t = DEFAULT_MAX_OUTPUT_BYTES,
        env = "MCP_CODE_QUALITY_MAX_OUTPUT_BYTES",
        value_parser = parse_output_limit
    )]
    max_output_bytes: usize,

    /// Maximum number of external tool processes running at once
    #[arg(
        long,
        default_value_t = DEFAULT_MAX_CONCURRENT,
        env = "MCP_CODE_QUALITY_MAX_CONCURRENT",
        value_parser = parse_concurrency
    )]
    max_concurrent: usize,
}

fn parse_output_limit(s: &str) -> Result<usize, String> {
    let n: usize = s.parse().map_err(|e| format!("{e}"))?;
    if (1024..=64 * 1024 * 1024).contains(&n) {
        Ok(n)
    } else {
        Err("must be between 1024 and 67108864".to_string())
    }
}

fn parse_concurrency(s: &str) -> Result<usize, String> {
    let n: usize = s.parse().map_err(|e| format!("{e}"))?;
    if (1..=64).contains(&n) {
        Ok(n)
    } else {
        Err("must be between 1 and 64".to_string())
    }
}

/// Split the comma-separated allowlist, dropping empty entries.
fn split_paths(s: &str) -> Vec<String> {
    s.split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect()
}

impl Args {
    fn engine_config(&self) -> EngineConfig {
        EngineConfig {
            timeout: Duration::from_secs(self.timeout),
            allowed_paths: split_paths(&self.allowed_paths),
            audit_log_path: self.audit_log.clone(),
            audit_log_max_bytes: self.audit_log_max_bytes,
            rate_limiting: self.rate_limit,
            max_output_bytes: self.max_output_bytes,
            max_concurrent: self.max_concurrent,
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    init_logging(&args.server.log_level);

    let quality_server = CodeQualityServer::new(CodeQualityEngine::new(args.engine_config()));

    let mut builder = args
        .server
        .apply_to(MCPServer::builder("code-quality", VERSION));
    for tool in quality_server.tools() {
        builder = builder.tool_boxed(tool);
    }
    builder.build().run().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(extra: &[&str]) -> Result<Args, clap::Error> {
        let mut argv = vec!["mcp-code-quality"];
        argv.extend_from_slice(extra);
        Args::try_parse_from(argv)
    }

    #[test]
    fn defaults() {
        let a = parse(&[]).unwrap();
        let c = a.engine_config();
        assert!(c.rate_limiting);
        assert_eq!(c.timeout, Duration::from_secs(DEFAULT_TIMEOUT_SECS));
        assert_eq!(c.max_concurrent, DEFAULT_MAX_CONCURRENT);
        assert_eq!(c.max_output_bytes, DEFAULT_MAX_OUTPUT_BYTES);
    }

    #[test]
    fn rate_limit_can_be_disabled() {
        // Previously a SetTrue flag with default "true": impossible to turn off.
        let a = parse(&["--rate-limit", "false"]).unwrap();
        assert!(!a.rate_limit);
        let a = parse(&["--rate-limit", "true"]).unwrap();
        assert!(a.rate_limit);
    }

    #[test]
    fn rejects_out_of_range_values() {
        assert!(parse(&["--timeout", "0"]).is_err());
        assert!(parse(&["--max-concurrent", "0"]).is_err());
        assert!(parse(&["--max-output-bytes", "10"]).is_err());
        assert!(parse(&["--audit-log-max-bytes", "10"]).is_err());
    }

    #[test]
    fn allowed_paths_are_split_and_trimmed() {
        assert_eq!(split_paths(" /a , ,/b,"), vec!["/a", "/b"]);
        let a = parse(&["--allowed-paths", "/x,/y"]).unwrap();
        assert_eq!(a.engine_config().allowed_paths, vec!["/x", "/y"]);
    }

    #[test]
    fn stdio_mode_parses() {
        let a = parse(&["--mode", "stdio"]).unwrap();
        assert_eq!(format!("{:?}", a.server.mode).to_lowercase(), "stdio");
    }
}
