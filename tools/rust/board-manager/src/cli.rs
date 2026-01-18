//! Command-line interface for board manager.

use clap::{Parser, Subcommand};

use crate::config::{get_github_token, load_config};
use crate::error::Result;
use crate::manager::BoardManager;
use crate::models::{IssueStatus, ReleaseReason};

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

    let config = load_config()?;
    let token = get_github_token()?;
    let mut manager = BoardManager::new(config, token)?;
    manager.initialize().await?;

    match cli.command {
        Commands::Ready { agent, limit } => {
            let issues = manager.get_ready_work(agent.as_deref(), limit).await?;

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

        Commands::Claim { issue, agent, session } => {
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
                println!("Claimed issue #{} for {} (session: {})", issue, agent, session_id);
            } else {
                println!("Failed to claim issue #{} - already claimed", issue);
            }
        }

        Commands::Renew { issue, agent, session } => {
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
                println!("Failed to renew claim on #{} - no active claim by {}", issue, agent);
            }
        }

        Commands::Release { issue, agent, reason } => {
            let release_reason = ReleaseReason::from_str(&reason)
                .ok_or_else(|| crate::error::BoardError::Config(format!("Invalid reason: {}", reason)))?;

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
            let new_status = IssueStatus::from_str(&status)
                .ok_or_else(|| crate::error::BoardError::Config(format!("Invalid status: {}", status)))?;

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
                println!("  Project: #{} (owner: {})", config.project_number, config.owner);
                println!("  Repository: {}", config.repository);
                println!("  Claim timeout: {}h", config.claim_timeout / 3600);
                println!("  Enabled agents: {:?}", config.enabled_agents);
            }
        }
    }

    Ok(())
}
