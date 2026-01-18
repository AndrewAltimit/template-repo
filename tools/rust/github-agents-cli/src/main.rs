//! github-agents: CLI for GitHub AI Agents
//!
//! This tool provides a fast Rust CLI interface for the GitHub AI Agents system.
//! All monitoring and agent orchestration is implemented natively in Rust.
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
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use clap::{Parser, Subcommand};
use tracing::{Level, error, info};
use tracing_subscriber::FmtSubscriber;

mod agents;
mod analyzers;
mod creators;
mod error;
mod monitor;
mod review;
mod security;
mod utils;

use error::Error;
use monitor::{IssueMonitor, Monitor, PrMonitor, RefinementMonitor};

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

    /// Run multi-agent backlog refinement
    RefinementMonitor {
        /// Agents to use (comma-separated)
        #[arg(long, default_value = "claude,gemini")]
        agents: String,

        /// Maximum issues to review
        #[arg(long, default_value = "5")]
        max_issues: usize,

        /// Maximum comments per issue
        #[arg(long, default_value = "2")]
        max_comments: usize,

        /// Minimum issue age in days
        #[arg(long, default_value = "3")]
        min_age_days: i64,

        /// Dry run (review but don't post comments)
        #[arg(long)]
        dry_run: bool,

        /// Output format (text or json)
        #[arg(long, default_value = "text")]
        format: String,
    },

    /// Review a pull request using AI
    PrReview {
        /// PR number to review
        pr_number: u64,

        /// Override default agent (gemini, claude, openrouter)
        #[arg(long)]
        agent: Option<String>,

        /// Force full review (ignore incremental state)
        #[arg(long)]
        full: bool,

        /// Dry run (show review without posting)
        #[arg(long)]
        dry_run: bool,

        /// Output format (text or json)
        #[arg(long, default_value = "text")]
        format: String,
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

async fn run() -> Result<(), Error> {
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
            let monitor = IssueMonitor::new(running)?;
            if continuous {
                info!(
                    "Running issue monitor continuously (interval: {}s)",
                    interval
                );
                monitor.run_continuous(interval).await?;
            } else {
                info!("Running issue monitor once");
                monitor.process_items().await?;
            }
        }

        Commands::PrMonitor {
            continuous,
            interval,
        } => {
            let monitor = PrMonitor::new(running)?;
            if continuous {
                info!("Running PR monitor continuously (interval: {}s)", interval);
                monitor.run_continuous(interval).await?;
            } else {
                info!("Running PR monitor once");
                monitor.process_items().await?;
            }
        }

        Commands::RefinementMonitor {
            agents,
            max_issues,
            max_comments,
            min_age_days,
            dry_run,
            format,
        } => {
            let agent_list: Vec<String> = agents.split(',').map(|s| s.trim().to_string()).collect();
            info!(
                "Running backlog refinement with agents: {:?}, max_issues: {}, dry_run: {}",
                agent_list, max_issues, dry_run
            );

            let config = monitor::RefinementConfig {
                min_age_days,
                max_age_days: 365, // default to 1 year
                exclude_labels: vec![],
                max_issues_per_run: max_issues,
                max_comments_per_issue: max_comments,
                agent_cooldown_days: 14,
                min_insight_length: 50,
                max_insight_length: 2000,
                dry_run,
                enable_issue_management: false,
                agent_admins: vec![], // loaded from .agents.yaml by RefinementMonitor
            };

            let monitor = RefinementMonitor::new(running, config)?;
            let agent_refs: Vec<&str> = agent_list.iter().map(|s| s.as_str()).collect();
            let results = monitor.run(Some(agent_refs)).await?;

            if format == "json" {
                println!("{}", serde_json::to_string_pretty(&results)?);
            } else {
                println!(
                    "Refinement complete: {} issues reviewed, {} insights added",
                    results.len(),
                    results.iter().map(|r| r.insights_added).sum::<usize>()
                );
            }
        }

        Commands::PrReview {
            pr_number,
            agent,
            full,
            dry_run,
            format,
        } => {
            info!("Running PR review for #{}", pr_number);

            // Load config
            let config = review::PRReviewConfig::load()?;

            // Create reviewer
            let reviewer = review::PRReviewer::new(config, agent.as_deref(), dry_run).await?;

            // Run review
            let review_text = reviewer.review_pr(pr_number, full).await?;

            if format == "json" {
                let result = serde_json::json!({
                    "pr_number": pr_number,
                    "review": review_text,
                    "dry_run": dry_run,
                });
                println!("{}", serde_json::to_string_pretty(&result)?);
            } else if !dry_run {
                // Review was posted, just confirm
                println!("Review posted to PR #{}", pr_number);
            }
            // If dry_run, the review was already printed by the reviewer
        }
    }

    info!("GitHub AI Agents CLI completed");
    Ok(())
}

#[tokio::main]
async fn main() {
    if let Err(e) = run().await {
        error!("Error: {}", e);
        if let Some(help) = e.help_text() {
            eprintln!("{}", help);
        }
        exit(e.exit_code());
    }
}
