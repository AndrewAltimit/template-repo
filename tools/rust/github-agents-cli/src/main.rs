//! github-agents: CLI for GitHub AI Agents
//!
//! This tool provides a fast Rust CLI interface for the GitHub AI Agents system.
//! It can delegate to Python monitors or run native Rust implementations.
//!
//! # Usage
//!
//! ```bash
//! github-agents issue-monitor                    # Run issue monitor once
//! github-agents issue-monitor --continuous       # Run continuously
//! github-agents issue-monitor --interval 600    # Custom interval (10 min)
//! github-agents pr-monitor                       # Run PR monitor once
//! github-agents pr-monitor --continuous          # Run continuously
//! ```
//!
//! # Exit Codes
//!
//! - 0: Success
//! - 1: Error
//! - 130: Interrupted by user (Ctrl+C)

use std::process::exit;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use clap::{Parser, Subcommand};
use tracing::{error, info, Level};
use tracing_subscriber::FmtSubscriber;

mod error;
mod monitor;

use error::Error;
use monitor::{IssueMonitor, Monitor, PrMonitor};

/// GitHub AI Agents CLI - Automated GitHub workflow management
#[derive(Parser, Debug)]
#[command(name = "github-agents")]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Enable verbose logging
    #[arg(short, long, global = true)]
    verbose: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Monitor GitHub issues for automation triggers
    IssueMonitor {
        /// Run continuously instead of once
        #[arg(long)]
        continuous: bool,

        /// Check interval in seconds (default: 300)
        #[arg(long, default_value = "300")]
        interval: u64,
    },

    /// Monitor GitHub PRs for review feedback
    PrMonitor {
        /// Run continuously instead of once
        #[arg(long)]
        continuous: bool,

        /// Check interval in seconds (default: 300)
        #[arg(long, default_value = "300")]
        interval: u64,
    },
}

fn setup_logging(verbose: bool) {
    let level = if verbose { Level::DEBUG } else { Level::INFO };

    let subscriber = FmtSubscriber::builder()
        .with_max_level(level)
        .with_target(false)
        .with_thread_ids(false)
        .with_file(false)
        .with_line_number(false)
        .finish();

    tracing::subscriber::set_global_default(subscriber).expect("Failed to set subscriber");
}

fn run() -> Result<(), Error> {
    let args = Args::parse();

    // Setup logging
    setup_logging(args.verbose);

    // Setup signal handling for graceful shutdown
    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    ctrlc::set_handler(move || {
        r.store(false, Ordering::SeqCst);
    })
    .ok();

    info!("GitHub AI Agents CLI starting...");

    match args.command {
        Commands::IssueMonitor {
            continuous,
            interval,
        } => {
            let monitor = IssueMonitor::new(running);
            if continuous {
                info!(
                    "Running issue monitor continuously (interval: {}s)",
                    interval
                );
                monitor.run_continuous(interval)?;
            } else {
                info!("Running issue monitor once");
                monitor.process_items()?;
            }
        }

        Commands::PrMonitor {
            continuous,
            interval,
        } => {
            let monitor = PrMonitor::new(running);
            if continuous {
                info!("Running PR monitor continuously (interval: {}s)", interval);
                monitor.run_continuous(interval)?;
            } else {
                info!("Running PR monitor once");
                monitor.process_items()?;
            }
        }
    }

    info!("GitHub AI Agents CLI completed");
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        error!("Error: {}", e);
        if let Some(help) = e.help_text() {
            eprintln!("{}", help);
        }
        exit(e.exit_code());
    }
}
