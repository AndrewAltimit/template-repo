//! github-agents: CLI for GitHub AI Agents
//!
//! Monitors issues and PRs for authorized trigger comments, runs AI review
//! and refinement pipelines, and exposes the security primitives (allow-list,
//! trigger parsing, commit validation) for use from workflows.
//!
//! # Usage
//!
//! ```bash
//! github-agents issue-monitor                    # Run issue monitor once
//! github-agents pr-monitor --continuous          # Run continuously
//! github-agents pr-review 123 --profile security # Review a PR
//! github-agents security parse-trigger --comment "[Approved][Claude]"
//! ```
//!
//! # Exit Codes
//!
//! - 0: Success
//! - 1: General error
//! - 2: GitHub CLI missing or not authenticated
//! - 3: GitHub token not found
//! - 5: Agent not available (unknown, disabled or not installed)
//! - 6: Agent execution failed
//! - 7: Agent timed out
//! - 8: Security check failed / denied
//! - 130: Interrupted by user (Ctrl+C)

use std::path::Path;
use std::process::exit;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use clap::{Parser, Subcommand};
use tracing::{Level, error, info, warn};
use tracing_subscriber::FmtSubscriber;

mod agents;
mod analyzers;
mod commands;
mod creators;
mod error;
mod iteration;
mod monitor;
mod review;
mod security;
mod utils;

use error::Error;

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

    /// Monitor GitHub PRs for automation triggers
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
        /// Agents to use (comma-separated; disabled agents are skipped)
        #[arg(long, default_value = "claude")]
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

        /// Override default agent (claude, openrouter, opencode, crush)
        #[arg(long)]
        agent: Option<String>,

        /// Review profile from review-profiles.yaml (e.g., security, quality, openrouter-general)
        #[arg(long)]
        profile: Option<String>,

        /// Force full review (ignore incremental state)
        #[arg(long)]
        full: bool,

        /// Dry run (show review without posting)
        #[arg(long)]
        dry_run: bool,

        /// Output format (text or json)
        #[arg(long, default_value = "text")]
        format: String,

        /// Enable editor pass to clean up review formatting
        #[arg(long)]
        editor: bool,

        /// Agent to use for editor pass (default: claude)
        #[arg(long, default_value = "claude")]
        editor_agent: String,
    },

    /// Check agent iteration count from PR comments
    IterationCheck {
        /// PR number to check
        #[arg(long)]
        pr: u64,

        /// Agent type to check (review-fix or failure-fix)
        #[arg(long)]
        agent_type: String,

        /// Maximum iterations before stopping (default: 5)
        #[arg(long, default_value = "5")]
        max_iterations: u32,

        /// Output format (json, github-actions, or text)
        #[arg(long, default_value = "text")]
        format: String,

        /// Path to .agents.yaml config (default: .agents.yaml)
        #[arg(long, default_value = ".agents.yaml")]
        config: String,
    },

    /// Analyze codebase and create issues from findings
    Analyze {
        /// Agents to use for analysis (comma-separated; disabled agents are skipped)
        #[arg(long, default_value = "claude")]
        agents: String,

        /// File patterns to include (comma-separated globs)
        #[arg(long, default_value = "**/*.py,**/*.rs,**/*.ts,**/*.js")]
        include_paths: String,

        /// File patterns to exclude (comma-separated globs)
        #[arg(
            long,
            default_value = "**/tests/**,**/__pycache__/**,**/node_modules/**,**/target/**"
        )]
        exclude_paths: String,

        /// Categories to analyze (comma-separated)
        #[arg(long, default_value = "security,performance,quality,tech_debt")]
        categories: String,

        /// Minimum priority to create issues for (P0, P1, P2, P3)
        #[arg(long, default_value = "P2")]
        min_priority: String,

        /// Maximum issues to create per run
        #[arg(long, default_value = "5")]
        max_issues: usize,

        /// Dry run (analyze but don't create issues)
        #[arg(long)]
        dry_run: bool,

        /// Output format (text or json)
        #[arg(long, default_value = "text")]
        format: String,
    },

    /// Security primitives: allow-list, trigger parsing, commit validation
    Security {
        /// Path to .agents.yaml config
        #[arg(long, default_value = ".agents.yaml", global = true)]
        config: String,

        /// Output format (text or json)
        #[arg(long, default_value = "text", global = true)]
        format: String,

        #[command(subcommand)]
        command: commands::SecurityCommand,
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
        .with_writer(std::io::stderr) // Logs to stderr to keep stdout clean for JSON output
        .finish();

    if tracing::subscriber::set_global_default(subscriber).is_err() {
        eprintln!("warning: logging subscriber already set");
    }
}

/// Validate an `--format` value against the accepted set.
fn check_format(format: &str, allowed: &[&str]) -> Result<(), Error> {
    if allowed.contains(&format) {
        Ok(())
    } else {
        Err(Error::Config(format!(
            "Invalid --format '{}'. Expected one of: {}",
            format,
            allowed.join(", ")
        )))
    }
}

/// Install a Ctrl+C handler; monitors poll the returned flag for graceful
/// shutdown.
fn install_interrupt_flag() -> Arc<AtomicBool> {
    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    if let Err(e) = ctrlc::set_handler(move || r.store(false, Ordering::SeqCst)) {
        warn!("Could not install Ctrl+C handler: {}", e);
    }
    running
}

async fn run(args: Args) -> Result<(), Error> {
    let running = install_interrupt_flag();
    match args.command {
        Commands::IssueMonitor {
            continuous,
            interval,
        } => commands::issue_monitor(running, continuous, interval).await?,

        Commands::PrMonitor {
            continuous,
            interval,
        } => commands::pr_monitor(running, continuous, interval).await?,

        Commands::RefinementMonitor {
            agents,
            max_issues,
            max_comments,
            min_age_days,
            dry_run,
            format,
        } => {
            check_format(&format, &["text", "json"])?;
            let config = monitor::RefinementConfig {
                min_age_days,
                max_age_days: 365,
                max_issues_per_run: max_issues,
                max_comments_per_issue: max_comments,
                dry_run,
                ..Default::default()
            };
            commands::refinement(running, &agents, config, &format).await?
        },

        Commands::PrReview {
            pr_number,
            agent,
            profile,
            full,
            dry_run,
            format,
            editor,
            editor_agent,
        } => {
            check_format(&format, &["text", "json"])?;
            let opts = commands::PrReviewOptions {
                pr_number,
                agent,
                profile,
                full,
                dry_run,
                json: format == "json",
                editor_agent: editor.then_some(editor_agent),
            };
            commands::pr_review(opts).await?
        },

        Commands::IterationCheck {
            pr,
            agent_type,
            max_iterations,
            format,
            config,
        } => {
            check_format(&format, &["text", "json", "github-actions"])?;
            commands::iteration_check(pr, &agent_type, max_iterations, &format, Path::new(&config))
                .await?
        },

        Commands::Analyze {
            agents,
            include_paths,
            exclude_paths,
            categories,
            min_priority,
            max_issues,
            dry_run,
            format,
        } => {
            check_format(&format, &["text", "json"])?;
            let opts = commands::AnalyzeOptions {
                agents,
                include_paths,
                exclude_paths,
                categories,
                min_priority,
                max_issues,
                dry_run,
                json: format == "json",
            };
            commands::analyze(opts).await?
        },

        Commands::Security {
            config,
            format,
            command,
        } => {
            check_format(&format, &["text", "json"])?;
            commands::security(command, Path::new(&config), format == "json").await?
        },
    }
    Ok(())
}

#[tokio::main]
async fn main() {
    let args = Args::parse();
    setup_logging(args.verbose);

    info!("GitHub AI Agents CLI starting...");
    let result = run(args).await;
    if result.is_ok() {
        info!("GitHub AI Agents CLI completed");
    }
    if let Err(e) = result {
        error!("Error: {}", e);
        if let Some(help) = e.help_text() {
            eprintln!("{}", help);
        }
        exit(e.exit_code());
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::CommandFactory;

    #[test]
    fn cli_definition_is_valid() {
        Args::command().debug_assert();
    }

    #[test]
    fn workflow_invocations_parse() {
        // Mirrors the invocations in .github/workflows and .github/actions
        let cases: &[&[&str]] = &[
            &["github-agents", "issue-monitor"],
            &["github-agents", "pr-monitor"],
            &[
                "github-agents",
                "refinement-monitor",
                "--agents",
                "claude,gemini",
                "--max-issues",
                "5",
                "--max-comments",
                "2",
                "--min-age-days",
                "3",
                "--format",
                "json",
                "--dry-run",
            ],
            &[
                "github-agents",
                "pr-review",
                "12",
                "--profile",
                "security",
                "--editor",
            ],
            &["github-agents", "pr-review", "12", "--agent", "codex"],
            &[
                "github-agents",
                "iteration-check",
                "--pr",
                "7",
                "--agent-type",
                "failure-fix",
                "--max-iterations",
                "5",
                "--config",
                ".agents.yaml",
                "--format",
                "json",
            ],
            &[
                "github-agents",
                "analyze",
                "--agents",
                "claude",
                "--format",
                "json",
                "--min-priority",
                "P1",
                "--max-issues",
                "3",
                "--include-paths",
                "**/*.rs",
                "--dry-run",
            ],
            &["github-agents", "security", "check-user", "--username", "x"],
            &[
                "github-agents",
                "security",
                "check-action",
                "--action",
                "issue_approved",
            ],
            &[
                "github-agents",
                "security",
                "validate-pr-commit",
                "--pr",
                "123",
                "--expected-sha",
                "abc1234",
            ],
            &[
                "github-agents",
                "security",
                "parse-trigger",
                "--comment",
                "[Approved][Claude]",
            ],
            &[
                "github-agents",
                "-v",
                "security",
                "--format",
                "json",
                "parse-trigger",
                "--comment",
                "x",
            ],
        ];
        for case in cases {
            Args::try_parse_from(*case).unwrap_or_else(|e| panic!("{:?}: {}", case, e));
        }
    }

    #[test]
    fn format_validation() {
        assert!(check_format("json", &["text", "json"]).is_ok());
        assert!(check_format("yaml", &["text", "json"]).is_err());
    }
}
