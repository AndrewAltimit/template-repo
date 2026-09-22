//! Command-line interface for board manager.
//!
//! Output contract: with `--format json` every successful command prints a
//! single JSON document on stdout; all logs go to stderr. Failures exit with
//! status 1 and an `Error: ...` line on stderr.

use clap::{ArgAction, Args, Parser, Subcommand, ValueEnum};
use serde::Serialize;
use serde_json::json;
use std::collections::HashMap;
use std::io::{self, Read};
use std::path::PathBuf;
use tracing::warn;

use crate::board::ReadyFilter;
use crate::config::{get_github_token, load_config};
use crate::error::{BoardError, Result};
use crate::manager::{AddOptions, BoardManager, JanitorOptions};
use crate::models::{
    ClaimOutcome, DependencyGraph, Issue, IssuePriority, IssueSize, IssueStatus, IssueType,
    JanitorReport, ReleaseReason,
};
use crate::security::{AgentJudgement, AssessmentContext, Comment, TrustBucketer, TrustLevel};

/// GitHub Projects v2 board manager CLI.
#[derive(Parser, Debug)]
#[command(name = "board-manager")]
#[command(about = "Manage GitHub Projects v2 board for AI agent coordination")]
#[command(version)]
pub struct Cli {
    /// Output format
    #[arg(long, value_enum, ignore_case = true, default_value_t = OutputFormat::Human, global = true)]
    pub format: OutputFormat,

    /// Enable verbose (debug) logging on stderr
    #[arg(short, long, global = true)]
    pub verbose: bool,

    /// Board config file (default: $BOARD_CONFIG_PATH, then ai-agents-board.yml
    /// in the current or a parent directory, then BOARD_* env vars)
    #[arg(long, global = true, value_name = "PATH")]
    pub config: Option<PathBuf>,

    #[command(subcommand)]
    pub command: Commands,
}

/// Output format.
#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
pub enum OutputFormat {
    Human,
    Json,
}

/// All subcommands.
#[derive(Subcommand, Debug)]
pub enum Commands {
    #[command(flatten)]
    Board(BoardCommand),
    #[command(flatten)]
    Local(LocalCommand),
}

/// Commands that talk to the GitHub API (need a token and board config).
#[derive(Subcommand, Debug)]
pub enum BoardCommand {
    /// Query ready work: open Todo issues whose blockers are resolved,
    /// highest priority first
    Ready {
        /// Only issues unassigned or assigned to this agent
        #[arg(short, long)]
        agent: Option<String>,

        /// Maximum number of issues to return
        #[arg(short, long, default_value = "10")]
        limit: usize,

        /// Only show issues with an approval trigger from an authorized user
        #[arg(long)]
        approved_only: bool,

        /// Only show issues with any of these labels (comma-separated, repeatable)
        #[arg(long, value_delimiter = ',')]
        include_labels: Option<Vec<String>>,

        /// Exclude issues with any of these labels (comma-separated, repeatable)
        #[arg(long, value_delimiter = ',')]
        exclude_labels: Option<Vec<String>>,
    },

    /// Claim an issue for work (posts a claim comment, sets In Progress)
    Claim {
        /// Issue number to claim
        issue: u64,

        /// Agent name claiming the issue
        #[arg(short, long)]
        agent: String,

        /// Session ID (auto-generated if not provided)
        #[arg(short, long)]
        session: Option<String>,
    },

    /// Renew an active claim (for long-running work)
    Renew {
        /// Issue number with active claim
        issue: u64,

        /// Agent name renewing the claim
        #[arg(short, long)]
        agent: String,

        /// Session ID
        #[arg(short, long)]
        session: String,
    },

    /// Release a claim (completed, pr_created, blocked, abandoned, error)
    Release {
        /// Issue number to release
        issue: u64,

        /// Agent name releasing the claim
        #[arg(short, long)]
        agent: String,

        /// Release reason; blocked sets Blocked, abandoned/error set Abandoned
        #[arg(short, long, default_value = "completed")]
        reason: String,
    },

    /// Update issue status (Todo, In Progress, Blocked, Done, Abandoned)
    Status {
        /// Issue number to update
        issue: u64,

        /// New status (positional form)
        #[arg(value_name = "STATUS", conflicts_with = "status")]
        status_positional: Option<String>,

        /// New status
        #[arg(short, long)]
        status: Option<String>,
    },

    /// Add a blocking dependency (ISSUE is blocked by BLOCKER)
    Block {
        /// Issue that is blocked
        issue: u64,

        /// Issue that blocks
        #[arg(short, long)]
        blocker: u64,
    },

    /// Remove a blocking dependency
    Unblock {
        /// Issue that is blocked
        issue: u64,

        /// Blocker to remove
        #[arg(short, long)]
        blocker: u64,
    },

    /// Mark an issue as discovered while working on a parent issue
    DiscoverFrom {
        /// Child issue number
        issue: u64,

        /// Parent issue number
        #[arg(short, long)]
        parent: u64,
    },

    /// Get board details for an issue (JSON `null` if not on the board)
    Info {
        /// Issue number
        issue: u64,
    },

    /// Show the dependency graph of an issue (blockers, blocked, parent, children)
    #[command(visible_alias = "graph")]
    Deps {
        /// Issue number
        issue: u64,
    },

    /// List enabled agents
    Agents,

    /// Show board configuration
    Config,

    /// Find open issues with [Approved][AGENT] comments via GitHub search
    FindApproved {
        /// Agent name in the trigger (default: claude)
        #[arg(short, long, default_value = "claude")]
        agent: String,

        /// Return raw search hits without verifying the approver is authorized
        #[arg(long)]
        unverified: bool,
    },

    /// Add an issue to the project board
    #[command(visible_alias = "add")]
    AddToBoard {
        /// Issue number to add
        issue: u64,

        /// Initial status (Todo, In Progress, Blocked, Done, Abandoned)
        #[arg(short, long, default_value = "Todo")]
        status: String,

        /// Priority (Critical, High, Medium, Low)
        #[arg(short, long)]
        priority: Option<String>,

        /// Type (Feature, Bug, Tech Debt, Documentation)
        #[arg(short = 't', long = "type")]
        issue_type: Option<String>,

        /// Estimated size (XS, S, M, L, XL)
        #[arg(long)]
        size: Option<String>,

        /// Assigned agent (workflow name like `claude` or board name)
        #[arg(short, long)]
        agent: Option<String>,
    },

    /// Check whether an issue has an approval trigger from an authorized user
    CheckApproval {
        /// Issue number to check
        issue: u64,

        /// Require the [Approved][..] trigger to name this agent
        #[arg(short, long)]
        agent: Option<String>,
    },

    /// Release stale claims on In Progress issues and reset their status
    Janitor {
        /// Only clean claims held by this agent
        #[arg(short, long)]
        agent: Option<String>,

        /// Hours without claim activity before a claim is stale
        /// (default: work_claims.timeout from config)
        #[arg(long, value_name = "HOURS")]
        threshold: Option<f64>,

        /// Status to reset stale issues to
        #[arg(long, default_value = "Todo")]
        reset_status: String,

        /// Report what would be cleaned without changing anything
        #[arg(long)]
        dry_run: bool,
    },
}

/// Commands that run locally without GitHub access.
#[derive(Subcommand, Debug)]
pub enum LocalCommand {
    /// Assess whether a review suggestion should be auto-applied
    AssessFix(AssessFixArgs),

    /// Get trust level for a username
    TrustLevel {
        /// Username to check
        username: String,

        /// Path to .agents.yaml config
        #[arg(long)]
        config_path: Option<PathBuf>,
    },

    /// Bucket comments by author trust level (JSON array on stdin or as argument)
    BucketComments {
        /// JSON array of comments, or "-" to read stdin (recommended)
        #[arg(default_value = "-")]
        comments_json: String,

        /// Path to .agents.yaml config
        #[arg(long)]
        config_path: Option<PathBuf>,

        /// Filter out automated noise (claim comments, bare triggers).
        /// Enabled by default; disable with --filter-noise=false
        #[arg(
            long,
            action = ArgAction::Set,
            num_args = 0..=1,
            require_equals = true,
            default_value_t = true,
            default_missing_value = "true"
        )]
        filter_noise: bool,

        /// Include empty bucket headers
        #[arg(long)]
        include_empty: bool,
    },
}

/// Arguments for `assess-fix`.
#[derive(Args, Debug)]
pub struct AssessFixArgs {
    /// Review comment text to assess
    pub comment: String,

    /// File path being modified (for context)
    #[arg(long)]
    pub file_path: Option<String>,

    /// File containing the diff under review (for context)
    #[arg(long)]
    pub diff_file: Option<PathBuf>,

    /// Whether the PR is security-related
    #[arg(long)]
    pub security_related: bool,

    /// Whether the PR is a draft
    #[arg(long)]
    pub draft: bool,

    /// Whether the change touches a public API
    #[arg(long)]
    pub touches_api: bool,

    /// Whether the change touches the database / data model
    #[arg(long)]
    pub touches_database: bool,

    /// Whether tests exist for the affected code
    #[arg(long)]
    pub existing_tests: bool,

    /// Free-text pipeline status (e.g. "all tests passed")
    #[arg(long)]
    pub pipeline_status: Option<String>,

    /// CI job result as NAME=RESULT (repeatable), e.g. build=success
    #[arg(long = "job-result", value_name = "NAME=RESULT")]
    pub job_results: Vec<String>,

    /// Recent commit message (repeatable)
    #[arg(long = "recent-commit", value_name = "MESSAGE")]
    pub recent_commits: Vec<String>,
}

/// Prints either JSON or human output.
#[derive(Clone, Copy)]
struct Out {
    json: bool,
}

impl Out {
    fn emit<T: Serialize + ?Sized>(self, value: &T, human: impl FnOnce()) -> Result<()> {
        if self.json {
            println!("{}", serde_json::to_string_pretty(value)?);
        } else {
            human();
        }
        Ok(())
    }
}

fn init_tracing(verbose: bool) {
    let default = if verbose {
        "board_manager=debug"
    } else {
        "board_manager=warn"
    };
    let filter = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(default));
    // stderr keeps stdout clean for `--format json` consumers.
    let _ = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_writer(io::stderr)
        .try_init();
}

fn parse_arg<T>(value: &str) -> Result<T>
where
    T: std::str::FromStr<Err = String>,
{
    value.parse().map_err(BoardError::Validation)
}

fn parse_opt<T>(value: Option<&str>) -> Result<Option<T>>
where
    T: std::str::FromStr<Err = String>,
{
    value.map(parse_arg).transpose()
}

/// Run the CLI.
pub async fn run(cli: Cli) -> Result<()> {
    init_tracing(cli.verbose);
    let out = Out {
        json: cli.format == OutputFormat::Json,
    };

    match cli.command {
        Commands::Local(cmd) => run_local(cmd, out),
        Commands::Board(cmd) => {
            let config = load_config(cli.config.as_deref())?;
            let token = get_github_token()?;
            let mut manager = BoardManager::new(config, token)?;
            manager.initialize().await?;
            run_board(cmd, &manager, out).await
        },
    }
}

// ===== Local commands =====

fn run_local(cmd: LocalCommand, out: Out) -> Result<()> {
    match cmd {
        LocalCommand::AssessFix(args) => assess_fix(&args, out),
        LocalCommand::TrustLevel {
            username,
            config_path,
        } => {
            let level =
                TrustBucketer::from_yaml(config_path.as_deref())?.get_trust_level(&username);
            out.emit(
                &json!({ "username": username, "trust_level": level.as_str() }),
                || println!("User '{}' has trust level: {}", username, level),
            )
        },
        LocalCommand::BucketComments {
            comments_json,
            config_path,
            filter_noise,
            include_empty,
        } => bucket_comments(
            &comments_json,
            config_path,
            filter_noise,
            include_empty,
            out,
        ),
    }
}

fn assess_fix(args: &AssessFixArgs, out: Out) -> Result<()> {
    let job_results = args
        .job_results
        .iter()
        .map(|kv| {
            kv.split_once('=')
                .map(|(k, v)| (k.trim().to_string(), v.trim().to_string()))
                .ok_or_else(|| {
                    BoardError::Validation(format!("--job-result expects NAME=RESULT, got '{kv}'"))
                })
        })
        .collect::<Result<HashMap<_, _>>>()?;
    let diff = args
        .diff_file
        .as_ref()
        .map(std::fs::read_to_string)
        .transpose()?;

    let context = AssessmentContext {
        file_path: args.file_path.clone(),
        diff,
        is_security_related: args.security_related,
        is_draft_pr: args.draft,
        touches_api: args.touches_api,
        touches_database: args.touches_database,
        existing_tests: args.existing_tests,
        pipeline_status: args.pipeline_status.clone(),
        job_results,
        recent_commits: args.recent_commits.clone(),
    };
    let result = AgentJudgement.assess_fix(&args.comment, &context);

    out.emit(&result, || {
        println!("Judgement Result:");
        println!("  Should auto-fix: {}", result.should_auto_fix);
        println!("  Confidence: {:.0}%", result.confidence * 100.0);
        println!("  Category: {}", result.category);
        println!("  Reasoning: {}", result.reasoning);
        if result.is_false_positive {
            println!("  False positive: yes");
            if let Some(reason) = &result.dismiss_reason {
                println!("  Dismiss reason: {}", reason);
            }
        }
        if let Some(question) = &result.ask_owner_question {
            println!("\n  Owner question:\n{}", question);
        }
    })
}

fn bucket_comments(
    comments_json: &str,
    config_path: Option<PathBuf>,
    filter_noise: bool,
    include_empty: bool,
    out: Out,
) -> Result<()> {
    let input = if comments_json == "-" {
        let mut buffer = String::new();
        io::stdin().read_to_string(&mut buffer)?;
        buffer
    } else {
        comments_json.to_string()
    };

    let value: serde_json::Value = serde_json::from_str(&input)
        .map_err(|e| BoardError::Validation(format!("Invalid comments JSON: {}", e)))?;
    let array = value
        .as_array()
        .ok_or_else(|| BoardError::Validation("Expected a JSON array of comments".into()))?;
    let comments: Vec<Comment> = array.iter().filter_map(Comment::from_json).collect();
    if comments.len() < array.len() {
        warn!(
            "Skipped {} comment(s) without a string body",
            array.len() - comments.len()
        );
    }

    let bucketer = TrustBucketer::from_yaml(config_path.as_deref())?;
    if out.json {
        let buckets = bucketer.bucket_comments(&comments, filter_noise);
        let mut result = serde_json::Map::new();
        let mut lists = serde_json::Map::new();
        for level in TrustLevel::ALL {
            let bucket = buckets.get(&level).cloned().unwrap_or_default();
            result.insert(level.as_str().into(), json!(bucket.len()));
            lists.insert(level.as_str().into(), serde_json::to_value(bucket)?);
        }
        result.insert("buckets".into(), serde_json::Value::Object(lists));
        println!("{}", serde_json::to_string_pretty(&result)?);
    } else {
        println!(
            "{}",
            bucketer.format_bucketed_comments(&comments, filter_noise, include_empty)
        );
    }
    Ok(())
}

// ===== Board commands =====

async fn run_board(cmd: BoardCommand, manager: &BoardManager, out: Out) -> Result<()> {
    match cmd {
        BoardCommand::Ready {
            agent,
            limit,
            approved_only,
            include_labels,
            exclude_labels,
        } => {
            let filter = ReadyFilter {
                agent,
                include_labels: include_labels.unwrap_or_default(),
                exclude_labels: exclude_labels.unwrap_or_default(),
            };
            ready(manager, &filter, limit, approved_only, out).await
        },
        BoardCommand::Claim {
            issue,
            agent,
            session,
        } => claim(manager, issue, &agent, session, out).await,
        BoardCommand::Renew {
            issue,
            agent,
            session,
        } => {
            let success = manager.renew_claim(issue, &agent, &session).await?;
            out.emit(
                &json!({ "success": success, "issue": issue, "agent": agent }),
                || {
                    if success {
                        println!("Renewed claim on issue #{} for {}", issue, agent);
                    } else {
                        println!(
                            "Failed to renew claim on #{} - no active claim by {}",
                            issue, agent
                        );
                    }
                },
            )
        },
        BoardCommand::Release {
            issue,
            agent,
            reason,
        } => {
            let reason: ReleaseReason = parse_arg(&reason)?;
            manager.release_work(issue, &agent, reason).await?;
            out.emit(
                &json!({ "success": true, "issue": issue, "agent": agent, "reason": reason.as_str() }),
                || println!("Released claim on issue #{} (reason: {})", issue, reason),
            )
        },
        BoardCommand::Status {
            issue,
            status_positional,
            status,
        } => {
            let raw = status.or(status_positional).ok_or_else(|| {
                BoardError::Validation("a status is required (e.g. `status 12 Done`)".into())
            })?;
            let status: IssueStatus = parse_arg(&raw)?;
            manager.update_status(issue, status).await?;
            out.emit(
                &json!({ "success": true, "issue": issue, "status": status.as_str() }),
                || println!("Updated issue #{} status to {}", issue, status),
            )
        },
        BoardCommand::Info { issue } => {
            let found = manager.get_issue(issue).await?;
            out.emit(&found, || match &found {
                Some(i) => print_issue(i),
                None => println!("Issue #{} not found on board", issue),
            })
        },
        other => run_board_deps(other, manager, out).await,
    }
}

/// Dependency commands (Blocked By / Discovered From fields).
async fn run_board_deps(cmd: BoardCommand, manager: &BoardManager, out: Out) -> Result<()> {
    match cmd {
        BoardCommand::Block { issue, blocker } => {
            let blocked_by = manager.add_blocker(issue, blocker).await?;
            out.emit(
                &json!({ "success": true, "issue": issue, "blocker": blocker, "blocked_by": blocked_by }),
                || println!("Added blocker: #{} blocks #{}", blocker, issue),
            )
        },
        BoardCommand::Unblock { issue, blocker } => {
            let blocked_by = manager.remove_blocker(issue, blocker).await?;
            out.emit(
                &json!({ "success": true, "issue": issue, "blocker": blocker, "blocked_by": blocked_by }),
                || println!("Removed blocker: #{} no longer blocks #{}", blocker, issue),
            )
        },
        BoardCommand::DiscoverFrom { issue, parent } => {
            manager.mark_discovered_from(issue, parent).await?;
            out.emit(
                &json!({ "success": true, "issue": issue, "parent": parent }),
                || println!("Marked issue #{} as discovered from #{}", issue, parent),
            )
        },
        BoardCommand::Deps { issue } => {
            let graph = manager.dependency_graph(issue).await?;
            out.emit(&graph, || match &graph {
                Some(g) => print_graph(g),
                None => println!("Issue #{} not found on board", issue),
            })
        },
        other => run_board_admin(other, manager, out).await,
    }
}

/// Configuration, discovery and maintenance commands.
async fn run_board_admin(cmd: BoardCommand, manager: &BoardManager, out: Out) -> Result<()> {
    match cmd {
        BoardCommand::Agents => {
            let agents = manager.get_enabled_agents();
            out.emit(agents, || {
                println!("Enabled agents:");
                for agent in agents {
                    println!("  - {}", agent);
                }
            })
        },
        BoardCommand::Config => {
            let config = manager.get_config();
            out.emit(config, || {
                println!("Board Configuration:");
                println!(
                    "  Project: #{} {} (owner: {})",
                    config.project_number,
                    manager.project_title().unwrap_or_default(),
                    config.owner
                );
                println!("  Repository: {}", config.repository);
                println!("  Claim timeout: {}h", config.claim_timeout / 3600);
                println!("  Enabled agents: {:?}", config.enabled_agents);
            })
        },
        BoardCommand::FindApproved { agent, unverified } => {
            let issues = manager.find_approved_issues(&agent, !unverified).await?;
            out.emit(&issues, || {
                if issues.is_empty() {
                    println!("No approved issues found for agent: {}", agent);
                } else {
                    println!("Found {} approved issues:\n", issues.len());
                    for issue in &issues {
                        println!("  {}", issue);
                    }
                }
            })
        },
        BoardCommand::AddToBoard {
            issue,
            status,
            priority,
            issue_type,
            size,
            agent,
        } => {
            let opts = AddOptions {
                priority: parse_opt::<IssuePriority>(priority.as_deref())?,
                issue_type: parse_opt::<IssueType>(issue_type.as_deref())?,
                size: parse_opt::<IssueSize>(size.as_deref())?,
                agent: Some(agent.unwrap_or_else(|| "Claude Code".to_string())),
            };
            add_to_board(manager, issue, parse_arg(&status)?, &opts, out).await
        },
        BoardCommand::CheckApproval { issue, agent } => {
            let (approved, approver) = manager.is_issue_approved(issue, agent.as_deref()).await?;
            out.emit(
                &json!({ "approved": approved, "issue": issue, "approver": approver }),
                || match &approver {
                    Some(a) => println!("Issue #{} is APPROVED by {}", issue, a),
                    None => println!("Issue #{} is NOT approved", issue),
                },
            )
        },
        BoardCommand::Janitor {
            agent,
            threshold,
            reset_status,
            dry_run,
        } => {
            let hours = threshold.unwrap_or(manager.get_config().claim_timeout as f64 / 3600.0);
            if !hours.is_finite() || hours <= 0.0 {
                return Err(BoardError::Validation(
                    "--threshold must be a positive number of hours".into(),
                ));
            }
            let opts = JanitorOptions {
                agent,
                threshold_secs: (hours * 3600.0).round() as i64,
                reset_status: parse_arg(&reset_status)?,
                dry_run,
            };
            let report = manager.janitor(&opts).await?;
            out.emit(&report, || print_janitor(&report))
        },
        _ => Err(BoardError::Validation(
            "internal error: command routed to the wrong handler".into(),
        )),
    }
}

async fn ready(
    manager: &BoardManager,
    filter: &ReadyFilter,
    limit: usize,
    approved_only: bool,
    out: Out,
) -> Result<()> {
    let mut issues = manager.get_ready_work(filter).await?;
    if approved_only {
        issues = manager
            .filter_approved(issues, limit, filter.agent.as_deref())
            .await?;
    }
    issues.truncate(limit);

    out.emit(&issues, || {
        if issues.is_empty() {
            println!("No ready issues found.");
            return;
        }
        println!("Ready issues ({}):", issues.len());
        for issue in &issues {
            println!(
                "  #{:<5} [{}] {} ({})",
                issue.number,
                issue.priority,
                issue.title,
                issue.agent.as_deref().unwrap_or("unassigned")
            );
        }
    })
}

async fn claim(
    manager: &BoardManager,
    issue: u64,
    agent: &str,
    session: Option<String>,
    out: Out,
) -> Result<()> {
    if !manager.get_enabled_agents().is_empty() && !manager.get_config().is_agent_enabled(agent) {
        warn!("Agent '{}' is not in agents.enabled_agents", agent);
    }
    let session_id = session.unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
    let outcome = manager.claim_work(issue, agent, &session_id).await?;

    let mut result = json!({
        "success": outcome == ClaimOutcome::Claimed,
        "issue": issue,
        "agent": agent,
        "session_id": session_id,
    });
    let holder = match &outcome {
        ClaimOutcome::Claimed => None,
        ClaimOutcome::AlreadyClaimed(c) => Some(("already_claimed", c)),
        ClaimOutcome::LostRace(c) => Some(("lost_race", c)),
    };
    if let Some((reason, c)) = holder {
        result["reason"] = json!(format!("{} by {}", reason, c.agent));
        result["claimed_by"] = json!(c.agent);
        result["claimed_session"] = json!(c.session_id);
    }

    out.emit(&result, || match holder {
        None => println!(
            "Claimed issue #{} for {} (session: {})",
            issue, agent, session_id
        ),
        Some((_, c)) => println!(
            "Failed to claim issue #{} - already claimed by {}",
            issue, c.agent
        ),
    })
}

async fn add_to_board(
    manager: &BoardManager,
    issue: u64,
    status: IssueStatus,
    opts: &AddOptions,
    out: Out,
) -> Result<()> {
    let lookup = manager.lookup_issue(issue).await?;
    if lookup.on_board {
        let current = lookup.issue.status;
        return out.emit(
            &json!({
                "success": true,
                "issue": issue,
                "already_on_board": true,
                "status": current.as_str()
            }),
            || {
                println!(
                    "Issue #{} is already on the board (status: {})",
                    issue, current
                )
            },
        );
    }

    let warnings = manager.add_issue_to_board(&lookup, status, opts).await?;
    out.emit(
        &json!({
            "success": true,
            "issue": issue,
            "already_on_board": false,
            "status": status.as_str(),
            "warnings": warnings
        }),
        || {
            println!("Added issue #{} to board with status: {}", issue, status);
            for w in &warnings {
                println!("  warning: {}", w);
            }
        },
    )
}

fn print_issue(i: &Issue) {
    println!("Issue #{}: {}", i.number, i.title);
    println!("  State: {}", i.state);
    println!("  Status: {}", i.status);
    println!("  Priority: {}", i.priority);
    if let Some(t) = i.issue_type {
        println!("  Type: {}", t);
    }
    if let Some(s) = i.size {
        println!("  Size: {}", s);
    }
    if let Some(agent) = &i.agent {
        println!("  Agent: {}", agent);
    }
    if !i.blocked_by.is_empty() {
        let list: Vec<String> = i.blocked_by.iter().map(|b| format!("#{}", b)).collect();
        println!("  Blocked by: {}", list.join(", "));
    }
    if let Some(parent) = i.discovered_from {
        println!("  Discovered from: #{}", parent);
    }
    if !i.labels.is_empty() {
        println!("  Labels: {}", i.labels.join(", "));
    }
    if let Some(url) = &i.url {
        println!("  URL: {}", url);
    }
}

fn print_graph(g: &DependencyGraph) {
    println!(
        "Issue #{}: {} ({})",
        g.issue.number, g.issue.title, g.issue.status
    );
    println!("  Ready: {}", if g.ready { "yes" } else { "no" });
    let section = |name: &str, refs: &[crate::models::IssueRef]| {
        if !refs.is_empty() {
            println!("  {}:", name);
            for r in refs {
                println!("    #{} {} ({}, {})", r.number, r.title, r.status, r.state);
            }
        }
    };
    section("Blocked by", &g.blocked_by);
    if !g.missing_blockers.is_empty() {
        println!("  Blockers not on board: {:?}", g.missing_blockers);
    }
    section("Blocks", &g.blocks);
    if let Some(p) = &g.parent {
        println!("  Discovered from: #{} {}", p.number, p.title);
    }
    section("Children", &g.children);
}

fn print_janitor(r: &JanitorReport) {
    let verb = if r.dry_run {
        "Would release"
    } else {
        "Released"
    };
    println!(
        "Janitor: inspected {} In Progress issue(s), threshold {:.1}h",
        r.inspected, r.threshold_hours
    );
    for s in &r.stale {
        println!(
            "  {} #{} ({}) claimed by {} {:.1}h ago -> {}",
            verb, s.issue, s.title, s.agent, s.age_hours, r.reset_status
        );
    }
    if !r.unclaimed_in_progress.is_empty() {
        println!(
            "  In Progress without a claim (untouched): {:?}",
            r.unclaimed_in_progress
        );
    }
    if !r.failed.is_empty() {
        println!("  Failed to release: {:?}", r.failed);
    }
    println!("cleaned_count={}", r.cleaned_count);
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::CommandFactory;

    fn parse(args: &[&str]) -> Cli {
        Cli::try_parse_from(std::iter::once("board-manager").chain(args.iter().copied()))
            .unwrap_or_else(|e| panic!("{args:?}: {e}"))
    }

    #[test]
    fn cli_definition_is_valid() {
        Cli::command().debug_assert();
    }

    #[test]
    fn workflow_invocations_parse() {
        // Invocations used by .github workflows/actions, the MCP server and
        // github-agents; these must keep parsing.
        parse(&[
            "--format",
            "json",
            "ready",
            "--limit",
            "5",
            "--approved-only",
            "--agent",
            "claude",
        ]);
        parse(&[
            "--format",
            "json",
            "ready",
            "--include-labels",
            "a",
            "--include-labels",
            "b,c",
        ]);
        parse(&["--format", "json", "find-approved", "--agent", "claude"]);
        parse(&[
            "--format",
            "json",
            "add-to-board",
            "12",
            "--agent",
            "claude",
        ]);
        parse(&["--format", "json", "check-approval", "12"]);
        parse(&[
            "--format",
            "json",
            "claim",
            "12",
            "--agent",
            "claude",
            "--session",
            "s",
        ]);
        parse(&[
            "--format",
            "json",
            "renew",
            "12",
            "--agent",
            "claude",
            "--session",
            "s",
        ]);
        parse(&[
            "--format", "json", "release", "12", "--agent", "claude", "--reason", "error",
        ]);
        parse(&["--format", "json", "block", "12", "--blocker", "3"]);
        parse(&["--format", "json", "discover-from", "12", "--parent", "3"]);
        parse(&["--format", "json", "info", "12"]);
        parse(&["--format", "json", "agents"]);
        parse(&["--format", "json", "config"]);
        parse(&["bucket-comments", "--filter-noise"]);
        parse(&[
            "add",
            "7",
            "--priority",
            "High",
            "--type",
            "Tech Debt",
            "--size",
            "M",
            "--agent",
            "x",
        ]);
    }

    #[test]
    fn status_accepts_positional_or_flag() {
        let positional = parse(&["--format", "json", "status", "12", "In Progress"]);
        let flag = parse(&["status", "12", "--status", "Done"]);
        match (positional.command, flag.command) {
            (
                Commands::Board(BoardCommand::Status {
                    status_positional: Some(p),
                    status: None,
                    ..
                }),
                Commands::Board(BoardCommand::Status {
                    status: Some(f), ..
                }),
            ) => {
                assert_eq!(p, "In Progress");
                assert_eq!(f, "Done");
            },
            other => panic!("unexpected parse: {other:?}"),
        }
        assert!(Cli::try_parse_from(["bm", "status", "1", "Done", "--status", "Todo"]).is_err());
    }

    #[test]
    fn global_flags_after_subcommand() {
        let cli = parse(&["ready", "--format", "JSON", "-v", "--config", "x.yml"]);
        assert_eq!(cli.format, OutputFormat::Json);
        assert!(cli.verbose);
        assert_eq!(cli.config, Some(PathBuf::from("x.yml")));
    }

    #[test]
    fn filter_noise_flag_forms() {
        let get = |args: &[&str]| match parse(args).command {
            Commands::Local(LocalCommand::BucketComments { filter_noise, .. }) => filter_noise,
            other => panic!("unexpected: {other:?}"),
        };
        assert!(get(&["bucket-comments"]));
        assert!(get(&["bucket-comments", "--filter-noise"]));
        assert!(!get(&["bucket-comments", "--filter-noise=false"]));
    }

    #[test]
    fn janitor_and_deps_parse() {
        parse(&[
            "janitor",
            "--agent",
            "claude",
            "--threshold",
            "2",
            "--dry-run",
        ]);
        parse(&["janitor", "--reset-status", "abandoned"]);
        parse(&["deps", "5"]);
        parse(&["graph", "5"]);
        parse(&["unblock", "5", "--blocker", "3"]);
    }

    #[test]
    fn assess_fix_context_flags() {
        parse(&[
            "assess-fix",
            "this will fail",
            "--job-result",
            "build=success",
            "--recent-commit",
            "bump v5",
            "--pipeline-status",
            "ok",
            "--touches-api",
            "--existing-tests",
        ]);
    }

    #[test]
    fn parse_helpers_report_validation_errors() {
        assert!(matches!(
            parse_arg::<IssueStatus>("nope"),
            Err(BoardError::Validation(_))
        ));
        assert_eq!(
            parse_opt::<IssueSize>(Some("xl")).unwrap(),
            Some(IssueSize::XL)
        );
        assert_eq!(parse_opt::<IssueSize>(None).unwrap(), None);
    }
}
