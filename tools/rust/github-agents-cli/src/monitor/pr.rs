//! PR monitor implementation.
//!
//! Monitors GitHub PRs for review feedback and automation triggers.

use std::sync::Arc;
use std::sync::atomic::AtomicBool;

use chrono::{DateTime, Duration, Utc};
use serde::Deserialize;
use tracing::{debug, error, info, warn};

use super::base::{BaseMonitor, Monitor};
use crate::agents::{AgentCapability, AgentContext, AgentRegistry};
use crate::error::Error;
use crate::utils::run_gh_command;

/// PR data from GitHub API.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PullRequest {
    pub number: i64,
    pub title: String,
    pub body: Option<String>,
    pub author: Option<Author>,
    pub created_at: String,
    pub updated_at: Option<String>,
    pub head_ref_name: Option<String>,
    pub head_ref_oid: Option<String>,
    pub comments: Option<Vec<Comment>>,
    pub reviews: Option<Vec<Review>>,
}

/// Author information.
#[derive(Debug, Deserialize)]
pub struct Author {
    pub login: String,
}

/// Comment information.
#[derive(Debug, Deserialize)]
pub struct Comment {
    pub body: String,
    pub author: Option<Author>,
}

/// Review information.
#[derive(Debug, Deserialize)]
pub struct Review {
    pub body: Option<String>,
    pub author: Option<Author>,
    pub state: String,
}

/// PR monitor that watches for review feedback and automation triggers.
pub struct PrMonitor {
    base: BaseMonitor,
    /// Agent registry for selecting and executing agents
    agent_registry: AgentRegistry,
}

impl PrMonitor {
    /// Create a new PR monitor.
    pub fn new(running: Arc<AtomicBool>) -> Result<Self, Error> {
        Ok(Self {
            base: BaseMonitor::new(running)?,
            agent_registry: AgentRegistry::new(),
        })
    }

    /// Get recent open PRs from the repository.
    async fn get_open_prs(&self, hours: u64) -> Result<Vec<PullRequest>, Error> {
        let output = run_gh_command(
            &[
                "pr",
                "list",
                "--repo",
                &self.base.config.repository,
                "--state",
                "open",
                "--json",
                "number,title,body,author,createdAt,updatedAt,headRefName,headRefOid,comments,reviews",
            ],
            true,
        )
        .await?;

        let prs: Vec<PullRequest> = match output {
            Some(json) => serde_json::from_str(&json)?,
            None => return Ok(Vec::new()),
        };

        // Filter by recent activity
        let cutoff = Utc::now() - Duration::hours(hours as i64);
        let recent_prs: Vec<PullRequest> = prs
            .into_iter()
            .filter(|pr| {
                let updated_at: DateTime<Utc> = pr
                    .updated_at
                    .as_deref()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or_else(Utc::now);
                updated_at >= cutoff
            })
            .collect();

        Ok(recent_prs)
    }

    /// Process a single PR.
    async fn process_single_pr(&self, pr: &PullRequest) -> Result<(), Error> {
        let pr_number = pr.number;

        // Check if we should process this PR
        if !self.base.should_process_item(pr_number, "pr") {
            return Ok(());
        }

        // Get comments as (body, author) pairs
        let comments: Vec<(String, String)> = pr
            .comments
            .as_ref()
            .map(|c| {
                c.iter()
                    .map(|comment| {
                        (
                            comment.body.clone(),
                            comment
                                .author
                                .as_ref()
                                .map(|a| a.login.clone())
                                .unwrap_or_default(),
                        )
                    })
                    .collect()
            })
            .unwrap_or_default();

        // Check for trigger
        let body = pr.body.as_deref().unwrap_or("");
        let author = pr.author.as_ref().map(|a| a.login.as_str()).unwrap_or("");

        let trigger_info = self
            .base
            .security_manager
            .check_trigger_comment(body, author, &comments);

        let trigger_info = match trigger_info {
            Some(info) => info,
            None => return Ok(()), // No trigger found
        };

        info!(
            "PR #{}: [{}][{}] by {}",
            pr_number,
            trigger_info.action,
            trigger_info.agent.as_deref().unwrap_or("auto"),
            trigger_info.username
        );

        // Perform security check using the loaded security config
        let action = format!("pr_{}", trigger_info.action);

        let (is_allowed, reason) = self.base.security_manager.perform_full_security_check(
            &trigger_info.username,
            &action,
            &self.base.config.repository,
        );

        if !is_allowed {
            warn!("Security check failed for PR #{}: {}", pr_number, reason);
            self.base
                .post_security_rejection(pr_number, &reason, "pr")
                .await?;
            return Ok(());
        }

        // Handle the action
        match trigger_info.action.as_str() {
            "approved" => {
                self.handle_approved(pr, &trigger_info).await?;
            },
            "review" => {
                self.handle_review(pr).await?;
            },
            "summarize" => {
                self.handle_summarize(pr).await?;
            },
            _ => {
                debug!("Unknown action: {}", trigger_info.action);
            },
        }

        Ok(())
    }

    /// Handle approved action (apply fixes from review).
    async fn handle_approved(
        &self,
        pr: &PullRequest,
        trigger_info: &crate::security::manager::TriggerInfo,
    ) -> Result<(), Error> {
        let pr_number = pr.number;
        let requested_agent = trigger_info.agent.as_deref();

        // Select an agent
        let agent = match self.agent_registry.select_agent(requested_agent).await {
            Some(a) => a,
            None => {
                let comment = format!(
                    "{} **Agent Unavailable**\n\n\
                    No AI agents are currently available to process this request.\n\n\
                    Requested: {}\n\n\
                    Please ensure the required agent CLI is installed and configured.\n\n\
                    *This comment was generated by the AI agent automation system.*",
                    self.base.agent_tag,
                    requested_agent.unwrap_or("auto")
                );
                self.base.post_comment(pr_number, &comment, "pr").await?;
                return Ok(());
            },
        };

        let agent_display_name = agent.trigger_keyword();

        // Post starting work comment
        let comment = format!(
            "{} I'm analyzing this PR using **{}** and will apply any necessary fixes.\n\n\
            *This comment was generated by the AI agent automation system.*",
            self.base.agent_tag, agent_display_name
        );
        self.base.post_comment(pr_number, &comment, "pr").await?;

        // Build the prompt from PR content and reviews
        let pr_body = pr.body.as_deref().unwrap_or("");
        let branch = pr.head_ref_name.as_deref().unwrap_or("unknown");

        // Collect review comments
        let reviews_text: String = pr
            .reviews
            .as_ref()
            .map(|reviews| {
                reviews
                    .iter()
                    .filter_map(|r| {
                        r.body.as_ref().map(|body| {
                            let author = r
                                .author
                                .as_ref()
                                .map(|a| a.login.as_str())
                                .unwrap_or("unknown");
                            format!("**{} ({}):**\n{}", author, r.state, body)
                        })
                    })
                    .collect::<Vec<_>>()
                    .join("\n\n")
            })
            .unwrap_or_default();

        let prompt = format!(
            "PR #{}: {}\n\n\
            Branch: {}\n\n\
            Description:\n{}\n\n\
            Review Comments:\n{}\n\n\
            Please analyze the review feedback and provide suggestions for fixes. \
            If code changes are needed, provide the implementation.",
            pr_number, pr.title, branch, pr_body, reviews_text
        );

        // Create context for the agent
        let context = AgentContext::for_implementation(pr_number, &pr.title, branch);

        info!("Executing agent {} for PR #{}", agent.name(), pr_number);

        match agent.generate_code(&prompt, &context).await {
            Ok(response) => {
                let truncated = if response.len() > 60000 {
                    format!(
                        "{}...\n\n*Response truncated due to length.*",
                        &response[..60000]
                    )
                } else {
                    response
                };

                let comment = format!(
                    "{} **Analysis and Fixes from {}**\n\n\
                    {}\n\n\
                    ---\n\
                    *This comment was generated by the AI agent automation system.*",
                    self.base.agent_tag, agent_display_name, truncated
                );
                self.base.post_comment(pr_number, &comment, "pr").await?;

                info!(
                    "Successfully processed PR #{} with agent {}",
                    pr_number,
                    agent.name()
                );
            },
            Err(e) => {
                error!("Agent {} failed for PR #{}: {}", agent.name(), pr_number, e);
                self.base
                    .post_error_comment(pr_number, &e.to_string(), "pr")
                    .await?;
            },
        }

        Ok(())
    }

    /// Handle review request.
    async fn handle_review(&self, pr: &PullRequest) -> Result<(), Error> {
        let pr_number = pr.number;

        // Select an agent with review capability
        let agent = match self
            .agent_registry
            .select_for_capability(AgentCapability::CodeReview, None)
            .await
        {
            Some(a) => a,
            None => {
                let comment = format!(
                    "{} **Review Unavailable**\n\n\
                    No AI agents with review capability are currently available.\n\n\
                    *This comment was generated by the AI agent automation system.*",
                    self.base.agent_tag
                );
                self.base.post_comment(pr_number, &comment, "pr").await?;
                return Ok(());
            },
        };

        // Get diff for review
        let diff = self.get_pr_diff(pr_number).await?;

        // Build review prompt
        let pr_body = pr.body.as_deref().unwrap_or("");
        let branch = pr.head_ref_name.as_deref().unwrap_or("unknown");

        let prompt = format!(
            "Please review this pull request:\n\n\
            PR #{}: {}\n\n\
            Branch: {}\n\n\
            Description:\n{}\n\n\
            Diff:\n```diff\n{}\n```\n\n\
            Provide a thorough code review covering:\n\
            - Code quality and style\n\
            - Potential bugs or issues\n\
            - Security concerns\n\
            - Performance implications\n\
            - Suggested improvements",
            pr_number, pr.title, branch, pr_body, diff
        );

        let context = AgentContext::for_review(pr_number, &pr.title);

        info!(
            "Executing review with agent {} for PR #{}",
            agent.name(),
            pr_number
        );

        match agent.review(&prompt).await {
            Ok(response) => {
                let truncated = if response.len() > 60000 {
                    format!(
                        "{}...\n\n*Response truncated due to length.*",
                        &response[..60000]
                    )
                } else {
                    response
                };

                let comment = format!(
                    "{} **Code Review by {}**\n\n\
                    {}\n\n\
                    ---\n\
                    *This comment was generated by the AI agent automation system.*",
                    self.base.agent_tag,
                    agent.trigger_keyword(),
                    truncated
                );
                self.base.post_comment(pr_number, &comment, "pr").await?;
            },
            Err(e) => {
                error!("Review failed for PR #{}: {}", pr_number, e);
                self.base
                    .post_error_comment(pr_number, &e.to_string(), "pr")
                    .await?;
            },
        }

        Ok(())
    }

    /// Get the diff for a PR.
    async fn get_pr_diff(&self, pr_number: i64) -> Result<String, Error> {
        let output = run_gh_command(
            &[
                "pr",
                "diff",
                &pr_number.to_string(),
                "--repo",
                &self.base.config.repository,
            ],
            false,
        )
        .await?;

        // Limit diff size to prevent overly long prompts
        let diff = output.unwrap_or_default();
        if diff.len() > 50000 {
            Ok(format!("{}...\n\n*Diff truncated to 50KB*", &diff[..50000]))
        } else {
            Ok(diff)
        }
    }

    /// Handle summarize request.
    async fn handle_summarize(&self, pr: &PullRequest) -> Result<(), Error> {
        let body_preview = pr
            .body
            .as_deref()
            .unwrap_or("")
            .chars()
            .take(200)
            .collect::<String>();

        let branch = pr.head_ref_name.as_deref().unwrap_or("unknown");

        let comment = format!(
            "{} **PR Summary:**\n\n\
            **Title:** {}\n\
            **Branch:** {}\n\
            **Description:** {}{}",
            self.base.agent_tag,
            pr.title,
            branch,
            body_preview,
            if pr.body.as_ref().map(|b| b.len()).unwrap_or(0) > 200 {
                "..."
            } else {
                ""
            }
        );
        self.base.post_comment(pr.number, &comment, "pr").await?;

        Ok(())
    }
}

#[async_trait::async_trait]
impl Monitor for PrMonitor {
    async fn process_items(&self) -> Result<(), Error> {
        info!(
            "Processing PRs for repository: {}",
            self.base.config.repository
        );

        // Ensure GitHub CLI is available
        self.base.ensure_gh_available().await?;

        if self.base.config.review_only_mode {
            info!("Running in review-only mode");
        }

        let prs = self.get_open_prs(24).await?;
        info!("Found {} recent open PRs", prs.len());

        for pr in &prs {
            if let Err(e) = self.process_single_pr(pr).await {
                warn!("Error processing PR #{}: {}", pr.number, e);
            }
        }

        Ok(())
    }

    async fn run_continuous(&self, interval_secs: u64) -> Result<(), Error> {
        info!(
            "Running PR monitor continuously (interval: {}s)",
            interval_secs
        );

        self.base
            .run_continuous_impl(|| self.process_items(), interval_secs, "PrMonitor")
            .await
    }

    fn name(&self) -> &str {
        "PrMonitor"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pr_deserialization() {
        let json = r#"{
            "number": 42,
            "title": "Test PR",
            "body": "PR body",
            "author": {"login": "testuser"},
            "createdAt": "2024-01-01T00:00:00Z",
            "headRefName": "feature-branch",
            "headRefOid": "abc123",
            "comments": [],
            "reviews": []
        }"#;

        let pr: PullRequest = serde_json::from_str(json).unwrap();
        assert_eq!(pr.number, 42);
        assert_eq!(pr.title, "Test PR");
    }
}
