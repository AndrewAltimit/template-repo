//! CLI argument parsing for pr-monitor

use clap::Parser;
use std::path::PathBuf;

/// Monitor GitHub PR for admin or AI reviewer comments
#[derive(Parser, Debug)]
#[command(name = "pr-monitor")]
#[command(author, version, about, long_about = None)]
#[command(after_help = "EXAMPLES:
    pr-monitor 123                          # Monitor PR #123
    pr-monitor 123 --timeout 1800           # Monitor for 30 minutes
    pr-monitor 123 --json                   # Output only JSON (quiet mode)
    pr-monitor 123 --since-commit abc1234   # Only monitor comments after commit

EXIT CODES:
    0 - Found relevant comment (output as JSON)
    1 - Timeout or error (no relevant comment found)
    130 - Interrupted by user (Ctrl+C)")]
pub struct Args {
    /// PR number to monitor
    pub pr_number: u32,

    /// Timeout in seconds (default: 600 = 10 minutes)
    #[arg(long, default_value = "600")]
    pub timeout: u64,

    /// Poll interval in seconds (default: 5, minimum: 1)
    #[arg(long, default_value = "5", value_parser = clap::value_parser!(u64).range(1..))]
    pub poll_interval: u64,

    /// Output only JSON (suppress stderr progress messages)
    #[arg(long)]
    pub json: bool,

    /// Only monitor comments after this commit SHA
    #[arg(long)]
    pub since_commit: Option<String>,

    /// Config file path (optional, for future use)
    #[arg(long)]
    pub config: Option<PathBuf>,
}
