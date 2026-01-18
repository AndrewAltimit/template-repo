//! Command-line interface for board manager.

use clap::{Parser, Subcommand};
use std::path::Path;

use crate::config::{get_github_token, load_config};
use crate::error::Result;
use crate::manager::BoardManager;
use crate::models::{IssuePriority, IssueStatus, IssueType, ReleaseReason};
use crate::security::{
    AgentJudgement, AssessmentContext, Comment, TrustBucketer, TrustLevel as SecurityTrustLevel,
};

/// GitHub Projects v2 board manager CLI.
#[derive(Parser)]
#[command(name = "board-manager")]
#[command(about = "Manage GitHub Projects v2 board for AI agent coordination")]
#[command(version)]
pub struct Cli {
    /// Output format (human or json)
    #[arg(long, default_value = "human")]
    pub format: OutputFormat,

    /// Enable verbose logging
    #[arg(short, long)]
    pub verbose: bool,

    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum OutputFormat {
    Human,
    Json,
}

impl std::str::FromStr for OutputFormat {
    type Err = String;

    fn from_str(s: &str) -> std::result::Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "human" => Ok(OutputFormat::Human),
            "json" => Ok(OutputFormat::Json),
            _ => Err(format!("Invalid format: {}", s)),
        }
    }
}

#[derive(Subcommand)]
pub enum Commands {
    /// Query ready work from the board
    Ready {
        /// Filter by agent name
        #[arg(short, long)]
        agent: Option<String>,

        /// Maximum number of issues to return
        #[arg(short, long, default_value = "10")]
        limit: usize,

        /// Only show issues with approval comments
        #[arg(long)]
        approved_only: bool,

        /// Only show issues with these labels (comma-separated)
        #[arg(long, value_delimiter = ',')]
        include_labels: Option<Vec<String>>,

        /// Exclude issues with these labels (comma-separated)
        #[arg(long, value_delimiter = ',')]
        exclude_labels: Option<Vec<String>>,
    },

    /// Claim an issue for work
    Claim {
        /// Issue number to claim
        #[arg(required = true)]
        issue: u64,

        /// Agent name claiming the issue
        #[arg(short, long, required = true)]
        agent: String,

        /// Session ID (auto-generated if not provided)
        #[arg(short, long)]
        session: Option<String>,
    },

    /// Renew an active claim
    Renew {
        /// Issue number with active claim
        #[arg(required = true)]
        issue: u64,

        /// Agent name renewing the claim
        #[arg(short, long, required = true)]
        agent: String,

        /// Session ID
        #[arg(short, long, required = true)]
        session: String,
    },

    /// Release claim on an issue
    Release {
        /// Issue number to release
        #[arg(required = true)]
        issue: u64,

        /// Agent name releasing the claim
        #[arg(short, long, required = true)]
        agent: String,

        /// Release reason
        #[arg(short, long, default_value = "completed")]
        reason: String,
    },

    /// Update issue status
    Status {
        /// Issue number to update
        #[arg(required = true)]
        issue: u64,

        /// New status (Todo, In Progress, Blocked, Done, Abandoned)
        #[arg(short, long, required = true)]
        status: String,
    },

    /// Add blocker dependency
    Block {
        /// Issue that is blocked
        #[arg(required = true)]
        issue: u64,

        /// Issue that blocks
        #[arg(short, long, required = true)]
        blocker: u64,
    },

    /// Mark issue as discovered from parent
    DiscoverFrom {
        /// Child issue number
        #[arg(required = true)]
        issue: u64,

        /// Parent issue number
        #[arg(short, long, required = true)]
        parent: u64,
    },

    /// Get issue details
    Info {
        /// Issue number
        #[arg(required = true)]
        issue: u64,
    },

    /// List enabled agents
    Agents,

    /// Show board configuration
    Config,

    /// Assess whether a fix should be auto-applied
    AssessFix {
        /// Review comment text to assess
        #[arg(required = true)]
        comment: String,

        /// File path being modified (for context)
        #[arg(long)]
        file_path: Option<String>,

        /// Whether the PR is security-related
        #[arg(long)]
        security_related: bool,

        /// Whether the PR is a draft
        #[arg(long)]
        draft: bool,
    },

    /// Get trust level for a username
    TrustLevel {
        /// Username to check
        #[arg(required = true)]
        username: String,

        /// Path to .agents.yaml config
        #[arg(long)]
        config_path: Option<String>,
    },

    /// Bucket comments by trust level
    BucketComments {
        /// JSON array of comments (each with 'author' and 'body' fields)
        #[arg(required = true)]
        comments_json: String,

        /// Path to .agents.yaml config
        #[arg(long)]
        config_path: Option<String>,

        /// Filter out noise comments
        #[arg(long, default_value = "true")]
        filter_noise: bool,

        /// Include empty bucket headers
        #[arg(long)]
        include_empty: bool,
    },

    /// Find approved issues not yet on the board
    FindApproved {
        /// Agent name to search for (default: claude)
        #[arg(short, long, default_value = "claude")]
        agent: String,
    },

    /// Add an issue to the project board
    AddToBoard {
        /// Issue number to add
        #[arg(required = true)]
        issue: u64,

        /// Initial status (Todo, In Progress, Blocked, Done, Abandoned)
        #[arg(short, long, default_value = "Todo")]
        status: String,

        /// Issue priority (Critical, High, Medium, Low)
        #[arg(short, long)]
        priority: Option<String>,

        /// Issue type (Feature, Bug, Tech Debt, Documentation)
        #[arg(short = 't', long = "type")]
        issue_type: Option<String>,

        /// Assigned agent name
        #[arg(short, long)]
        agent: Option<String>,
    },

    /// Check if an issue has approval from authorized user
    CheckApproval {
        /// Issue number to check
        #[arg(required = true)]
        issue: u64,
    },
}

/// Run the CLI.
pub async fn run(cli: Cli) -> Result<()> {
    // Initialize tracing
    if cli.verbose {
        tracing_subscriber::fmt()
            .with_env_filter("board_manager=debug")
            .init();
    } else {
        tracing_subscriber::fmt()
            .with_env_filter("board_manager=warn")
            .init();
    }

    // Handle commands that don't need board manager
    match &cli.command {
        Commands::AssessFix {
            comment,
            file_path,
            security_related,
            draft,
        } => {
            let judgement = AgentJudgement::default();
            let context = AssessmentContext {
                file_path: file_path.clone(),
                is_security_related: *security_related,
                is_draft_pr: *draft,
                ..Default::default()
            };

            let result = judgement.assess_fix(comment, &context);

            if cli.format == OutputFormat::Json {
                println!("{}", serde_json::to_string_pretty(&result)?);
            } else {
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
            }
            return Ok(());
        }

        Commands::TrustLevel {
            username,
            config_path,
        } => {
            let path = config_path.as_ref().map(|s| Path::new(s.as_str()));
            let bucketer = TrustBucketer::from_yaml(path)?;
            let level = bucketer.get_trust_level(username);

            if cli.format == OutputFormat::Json {
                println!(
                    "{}",
                    serde_json::json!({
                        "username": username,
                        "trust_level": format!("{}", level)
                    })
                );
            } else {
                println!("User '{}' has trust level: {}", username, level);
            }
            return Ok(());
        }

        Commands::BucketComments {
            comments_json,
            config_path,
            filter_noise,
            include_empty,
        } => {
            // Parse comments from JSON
            let comments_value: serde_json::Value = serde_json::from_str(comments_json)
                .map_err(|e| crate::error::BoardError::Config(format!("Invalid JSON: {}", e)))?;

            let comments: Vec<Comment> = comments_value
                .as_array()
                .ok_or_else(|| crate::error::BoardError::Config("Expected JSON array".to_string()))?
                .iter()
                .filter_map(Comment::from_json)
                .collect();

            let path = config_path.as_ref().map(|s| Path::new(s.as_str()));
            let bucketer = TrustBucketer::from_yaml(path)?;

            if cli.format == OutputFormat::Json {
                let buckets = bucketer.bucket_comments(&comments, *filter_noise);
                let result = serde_json::json!({
                    "admin": buckets.get(&SecurityTrustLevel::Admin).map(|v| v.len()).unwrap_or(0),
                    "trusted": buckets.get(&SecurityTrustLevel::Trusted).map(|v| v.len()).unwrap_or(0),
                    "community": buckets.get(&SecurityTrustLevel::Community).map(|v| v.len()).unwrap_or(0),
                });
                println!("{}", serde_json::to_string_pretty(&result)?);
            } else {
                let formatted =
                    bucketer.format_bucketed_comments(&comments, *filter_noise, *include_empty);
                println!("{}", formatted);
            }
            return Ok(());
        }

        _ => {}
    }

    // Commands that require board manager
    let config = load_config()?;
    let token = get_github_token()?;
    let mut manager = BoardManager::new(config, token)?;
    manager.initialize().await?;

    match cli.command {
        Commands::Ready {
            agent,
            limit,
            approved_only,
            include_labels,
            exclude_labels,
        } => {
            // Get more issues if filtering
            let has_filters = approved_only || include_labels.is_some() || exclude_labels.is_some();
            let fetch_limit = if has_filters { limit * 5 } else { limit };

            let mut issues = manager
                .get_ready_work(agent.as_deref(), fetch_limit)
                .await?;

            // Filter by labels if specified
            if let Some(ref include) = include_labels {
                let include_set: std::collections::HashSet<_> = include.iter().collect();
                issues.retain(|i| i.labels.iter().any(|l| include_set.contains(l)));
            }

            if let Some(ref exclude) = exclude_labels {
                let exclude_set: std::collections::HashSet<_> = exclude.iter().collect();
                issues.retain(|i| !i.labels.iter().any(|l| exclude_set.contains(l)));
            }

            // Filter by approval status if requested
            if approved_only {
                let mut approved_issues = Vec::new();
                for issue in issues {
                    let (is_approved, _) = manager.is_issue_approved(issue.number).await?;
                    if is_approved {
                        approved_issues.push(issue);
                        if approved_issues.len() >= limit {
                            break;
                        }
                    }
                }
                issues = approved_issues;
            }

            // Apply final limit
            issues.truncate(limit);

            if cli.format == OutputFormat::Json {
                println!("{}", serde_json::to_string_pretty(&issues)?);
            } else if issues.is_empty() {
                println!("No ready issues found.");
            } else {
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
            }
        }

        Commands::Claim {
            issue,
            agent,
            session,
        } => {
            let session_id = session.unwrap_or_else(|| uuid::Uuid::new_v4().to_string());
            let success = manager.claim_work(issue, &agent, &session_id).await?;

            if cli.format == OutputFormat::Json {
                println!(
                    "{}",
                    serde_json::json!({
                        "success": success,
                        "issue": issue,
                        "agent": agent,
                        "session_id": session_id
                    })
                );
            } else if success {
                println!(
                    "Claimed issue #{} for {} (session: {})",
                    issue, agent, session_id
                );
            } else {
                println!("Failed to claim issue #{} - already claimed", issue);
            }
        }

        Commands::Renew {
            issue,
            agent,
            session,
        } => {
            let success = manager.renew_claim(issue, &agent, &session).await?;

            if cli.format == OutputFormat::Json {
                println!(
                    "{}",
                    serde_json::json!({
                        "success": success,
                        "issue": issue,
                        "agent": agent
                    })
                );
            } else if success {
                println!("Renewed claim on issue #{} for {}", issue, agent);
            } else {
                println!(
                    "Failed to renew claim on #{} - no active claim by {}",
                    issue, agent
                );
            }
        }

        Commands::Release {
            issue,
            agent,
            reason,
        } => {
            let release_reason = ReleaseReason::from_str(&reason).ok_or_else(|| {
                crate::error::BoardError::Config(format!("Invalid reason: {}", reason))
            })?;

            manager.release_work(issue, &agent, release_reason).await?;

            if cli.format == OutputFormat::Json {
                println!(
                    "{}",
                    serde_json::json!({
                        "success": true,
                        "issue": issue,
                        "agent": agent,
                        "reason": reason
                    })
                );
            } else {
                println!("Released claim on issue #{} (reason: {})", issue, reason);
            }
        }

        Commands::Status { issue, status } => {
            let new_status = IssueStatus::from_str(&status).ok_or_else(|| {
                crate::error::BoardError::Config(format!("Invalid status: {}", status))
            })?;

            manager.update_status(issue, new_status).await?;

            if cli.format == OutputFormat::Json {
                println!(
                    "{}",
                    serde_json::json!({
                        "success": true,
                        "issue": issue,
                        "status": status
                    })
                );
            } else {
                println!("Updated issue #{} status to {}", issue, status);
            }
        }

        Commands::Block { issue, blocker } => {
            manager.add_blocker(issue, blocker).await?;

            if cli.format == OutputFormat::Json {
                println!(
                    "{}",
                    serde_json::json!({
                        "success": true,
                        "issue": issue,
                        "blocker": blocker
                    })
                );
            } else {
                println!("Added blocker: #{} blocks #{}", blocker, issue);
            }
        }

        Commands::DiscoverFrom { issue, parent } => {
            manager.mark_discovered_from(issue, parent).await?;

            if cli.format == OutputFormat::Json {
                println!(
                    "{}",
                    serde_json::json!({
                        "success": true,
                        "issue": issue,
                        "parent": parent
                    })
                );
            } else {
                println!("Marked issue #{} as discovered from #{}", issue, parent);
            }
        }

        Commands::Info { issue } => {
            let issue_data = manager.get_issue(issue).await?;

            if let Some(i) = issue_data {
                if cli.format == OutputFormat::Json {
                    println!("{}", serde_json::to_string_pretty(&i)?);
                } else {
                    println!("Issue #{}: {}", i.number, i.title);
                    println!("  Status: {}", i.status);
                    println!("  Priority: {}", i.priority);
                    if let Some(agent) = &i.agent {
                        println!("  Agent: {}", agent);
                    }
                    if !i.blocked_by.is_empty() {
                        println!("  Blocked by: {:?}", i.blocked_by);
                    }
                    if let Some(parent) = i.discovered_from {
                        println!("  Discovered from: #{}", parent);
                    }
                    if let Some(url) = &i.url {
                        println!("  URL: {}", url);
                    }
                }
            } else {
                println!("Issue #{} not found on board", issue);
            }
        }

        Commands::Agents => {
            let agents = manager.get_enabled_agents();

            if cli.format == OutputFormat::Json {
                println!("{}", serde_json::to_string_pretty(&agents)?);
            } else {
                println!("Enabled agents:");
                for agent in agents {
                    println!("  - {}", agent);
                }
            }
        }

        Commands::Config => {
            let config = manager.get_config();

            if cli.format == OutputFormat::Json {
                println!("{}", serde_json::to_string_pretty(&config)?);
            } else {
                println!("Board Configuration:");
                println!(
                    "  Project: #{} (owner: {})",
                    config.project_number, config.owner
                );
                println!("  Repository: {}", config.repository);
                println!("  Claim timeout: {}h", config.claim_timeout / 3600);
                println!("  Enabled agents: {:?}", config.enabled_agents);
            }
        }

        Commands::FindApproved { agent } => {
            let approved_issues = manager.find_approved_issues(&agent).await?;

            if cli.format == OutputFormat::Json {
                println!("{}", serde_json::to_string_pretty(&approved_issues)?);
            } else if approved_issues.is_empty() {
                println!("No approved issues found for agent: {}", agent);
            } else {
                println!("Found {} approved issues:\n", approved_issues.len());
                for issue in &approved_issues {
                    let board_status = if issue.on_board {
                        "on board"
                    } else {
                        "NOT on board"
                    };
                    println!("  #{}: {} ({})", issue.number, issue.title, board_status);
                }
            }
        }

        Commands::AddToBoard {
            issue,
            status,
            priority,
            issue_type,
            agent,
        } => {
            // Check if already on board
            let existing = manager.get_issue(issue).await?;
            if let Some(existing_issue) = existing {
                if cli.format == OutputFormat::Json {
                    println!(
                        "{}",
                        serde_json::json!({
                            "success": true,
                            "issue": issue,
                            "already_on_board": true,
                            "status": existing_issue.status.as_str()
                        })
                    );
                } else {
                    println!(
                        "Issue #{} is already on the board (status: {})",
                        issue, existing_issue.status
                    );
                }
                return Ok(());
            }

            // Parse status
            let new_status = IssueStatus::from_str(&status).ok_or_else(|| {
                crate::error::BoardError::Config(format!("Invalid status: {}", status))
            })?;

            // Parse priority
            let new_priority = match &priority {
                Some(p) => Some(IssuePriority::from_str(p).ok_or_else(|| {
                    crate::error::BoardError::Config(format!("Invalid priority: {}", p))
                })?),
                None => None,
            };

            // Parse type
            let new_type = match &issue_type {
                Some(t) => Some(IssueType::from_str(t).ok_or_else(|| {
                    crate::error::BoardError::Config(format!("Invalid type: {}", t))
                })?),
                None => None,
            };

            // Use normalized agent name
            let agent_name = agent.as_deref().unwrap_or("Claude Code");

            let success = manager
                .add_issue_to_board(issue, new_status, new_priority, new_type, Some(agent_name))
                .await?;

            if cli.format == OutputFormat::Json {
                println!(
                    "{}",
                    serde_json::json!({
                        "success": success,
                        "issue": issue,
                        "already_on_board": false,
                        "status": new_status.as_str()
                    })
                );
            } else if success {
                println!(
                    "Added issue #{} to board with status: {}",
                    issue, new_status
                );
            } else {
                println!("Failed to add issue #{} to board", issue);
            }
        }

        Commands::CheckApproval { issue } => {
            let (is_approved, approver) = manager.is_issue_approved(issue).await?;

            if cli.format == OutputFormat::Json {
                println!(
                    "{}",
                    serde_json::json!({
                        "approved": is_approved,
                        "issue": issue,
                        "approver": approver
                    })
                );
            } else if is_approved {
                println!(
                    "Issue #{} is APPROVED by {}",
                    issue,
                    approver.unwrap_or_default()
                );
            } else {
                println!("Issue #{} is NOT approved", issue);
            }
        }

        // These commands are handled early and shouldn't reach here
        Commands::AssessFix { .. }
        | Commands::TrustLevel { .. }
        | Commands::BucketComments { .. } => {
            unreachable!("Security commands should be handled before board manager init")
        }
    }

    Ok(())
}
