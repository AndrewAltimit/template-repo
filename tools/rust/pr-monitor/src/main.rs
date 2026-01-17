//! pr-monitor: GitHub PR comment monitoring with intelligent analysis
//!
//! This tool monitors a GitHub PR for comments from administrators or AI reviewers
//! and outputs a structured decision when a relevant comment is detected.
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
//! - 1: Timeout or error (no relevant comment found)
//! - 130: Interrupted by user (Ctrl+C)

use std::process::exit;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use clap::Parser;

mod analysis;
mod cli;
mod error;
mod github;
mod monitor;

use cli::Args;
use error::Error;
use github::GhClient;
use monitor::Poller;

/// Run the main monitoring logic
fn run() -> Result<(), Error> {
    let args = Args::parse();

    // Setup signal handling for graceful shutdown
    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    ctrlc::set_handler(move || {
        r.store(false, Ordering::SeqCst);
    })
    .ok();

    // Verify gh CLI is available and authenticated (fail fast)
    GhClient::check_available()?;

    if !args.json {
        eprintln!("{}", "=".repeat(60));
        eprintln!("PR #{} MONITORING AGENT", args.pr_number);
        eprintln!("{}", "=".repeat(60));
        eprintln!();
    }

    // Resolve since-commit to timestamp if provided
    let since_time = if let Some(sha) = &args.since_commit {
        if !args.json {
            eprintln!("Resolving commit timestamp for {}...", sha);
        }
        match GhClient::get_commit_time(sha) {
            Ok(time) => {
                if !args.json {
                    eprintln!(
                        "Will only monitor comments after: {}",
                        time.format("%Y-%m-%d %H:%M:%S UTC")
                    );
                    eprintln!();
                }
                Some(time)
            }
            Err(e) => {
                if !args.json {
                    eprintln!("WARNING: Could not resolve commit timestamp: {}", e);
                    eprintln!("Continuing without commit filter...");
                    eprintln!();
                }
                None
            }
        }
    } else {
        None
    };

    // Create and run poller
    let poller = Poller::new(
        args.pr_number,
        Duration::from_secs(args.poll_interval),
        Duration::from_secs(args.timeout),
        since_time,
        running,
    );

    match poller.run(args.json) {
        Ok((comment, classification)) => {
            let decision = classification.into_decision(&comment);

            if !args.json {
                eprintln!();
                eprintln!("{}", "=".repeat(60));
                eprintln!("RELEVANT COMMENT DETECTED");
                eprintln!("{}", "=".repeat(60));
                eprintln!("Author: {}", decision.comment.author);
                eprintln!("Type: {:?}", decision.response_type);
                eprintln!("Priority: {:?}", decision.priority);
                if let Some(action) = &decision.action_required {
                    eprintln!("Action: {}", action);
                }
                eprintln!();
            }

            // Output JSON to stdout
            println!("{}", serde_json::to_string_pretty(&decision)?);
            Ok(())
        }
        Err(e) => Err(e),
    }
}

fn main() {
    if let Err(e) = run() {
        eprintln!("ERROR: {}", e);
        if let Some(help) = e.help_text() {
            eprintln!();
            eprintln!("{}", help);
        }
        exit(e.exit_code());
    }
}
