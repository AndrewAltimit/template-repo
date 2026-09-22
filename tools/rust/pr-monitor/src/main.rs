//! pr-monitor: GitHub PR comment monitoring with intelligent analysis
//!
//! This tool monitors a GitHub PR for comments and reviews from administrators
//! or AI reviewers and outputs a structured decision when a relevant comment
//! is detected.
//!
//! # Usage
//!
//! ```bash
//! pr-monitor 123                          # Monitor PR #123
//! pr-monitor 123 --timeout 1800           # Monitor for 30 minutes
//! pr-monitor 123 --json                   # Output only JSON (quiet mode)
//! pr-monitor 123 --since-commit abc1234   # Only monitor comments after commit
//! ```
//!
//! # Exit Codes
//!
//! - 0: Found relevant comment (output as JSON on stdout)
//! - 1: Timeout or error (no relevant comment found); the timeout code is
//!   configurable with `--timeout-exit-code`
//! - 130: Interrupted by user (Ctrl+C)

use std::process::exit;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use clap::Parser;

use pr_monitor::analysis::Decision;
use pr_monitor::cli::Args;
use pr_monitor::error::{Error, Result};
use pr_monitor::github::{GhClient, RepoSpec};
use pr_monitor::monitor::{Filter, Poller, PollerConfig};

/// Run the main monitoring logic
fn run(args: Args) -> Result<()> {
    let quiet = args.json;

    // Setup signal handling for graceful shutdown
    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    if let Err(e) = ctrlc::set_handler(move || r.store(false, Ordering::SeqCst)) {
        eprintln!("WARNING: could not install Ctrl+C handler: {e}");
    }

    if args.config.is_some() {
        eprintln!("WARNING: --config is not supported and will be ignored");
    }

    // Verify gh CLI is available (fail fast)
    GhClient::check_available()?;

    let client = match &args.repo {
        Some(repo) => GhClient::with_repo(RepoSpec::parse(repo)?),
        None => GhClient::new(),
    };

    if !quiet {
        eprintln!("{}", "=".repeat(60));
        eprintln!("PR #{} MONITORING AGENT", args.pr_number);
        eprintln!("{}", "=".repeat(60));
        eprintln!();
    }

    // Resolve since-commit to timestamp if provided
    let since_time = match &args.since_commit {
        Some(sha) => {
            if !quiet {
                eprintln!("Resolving commit timestamp for {sha}...");
            }
            match client.get_commit_time(sha) {
                Ok(time) => {
                    if !quiet {
                        eprintln!(
                            "Will only monitor comments after: {}",
                            time.format("%Y-%m-%d %H:%M:%S UTC")
                        );
                        eprintln!();
                    }
                    Some(time)
                },
                Err(e) => {
                    // Without the filter only comments posted from now on are
                    // considered, which is the safe direction to degrade in.
                    eprintln!("WARNING: Could not resolve commit timestamp: {e}");
                    eprintln!("Continuing without commit filter (only new comments)...");
                    eprintln!();
                    None
                },
            }
        },
        None => None,
    };

    let filter = Filter {
        admin_user: args.admin_user.clone(),
        authors: args.authors.clone(),
        types: args.types.clone(),
    };

    let poller = Poller::new(
        client,
        PollerConfig {
            pr_number: args.pr_number,
            poll_interval: Duration::from_secs(args.poll_interval),
            timeout: Duration::from_secs(args.timeout),
            since_time,
            filter,
            quiet,
        },
        running,
    );

    let decision = poller.run()?.into_decision(args.pr_number);

    if !quiet {
        print_summary(&decision);
    }

    // Output JSON to stdout
    let json = if args.compact {
        serde_json::to_string(&decision)?
    } else {
        serde_json::to_string_pretty(&decision)?
    };
    println!("{json}");
    Ok(())
}

fn print_summary(decision: &Decision) {
    eprintln!();
    eprintln!("{}", "=".repeat(60));
    eprintln!("RELEVANT COMMENT DETECTED");
    eprintln!("{}", "=".repeat(60));
    eprintln!("Author: {}", decision.comment.author);
    if let Some(kind) = decision.response_type {
        eprintln!("Type: {}", kind.as_str());
    }
    eprintln!("Priority: {:?}", decision.priority);
    if let Some(action) = &decision.action_required {
        eprintln!("Action: {action}");
    }
    if let Some(url) = &decision.comment.url {
        eprintln!("URL: {url}");
    }
    eprintln!();
}

fn main() {
    let args = Args::parse();
    let timeout_exit_code = args.timeout_exit_code;

    if let Err(e) = run(args) {
        report_error(&e);
        exit(e.exit_code(timeout_exit_code));
    }
}

fn report_error(e: &Error) {
    eprintln!("ERROR: {e}");
    if let Some(help) = e.help_text() {
        eprintln!();
        eprintln!("{help}");
    }
}
