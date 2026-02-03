//! Issue monitor implementation.
//!
//! Monitors GitHub issues for automation triggers from authorized users.

use std::sync::Arc;
use std::sync::atomic::AtomicBool;

use chrono::{DateTime, Duration, Utc};
use serde::Deserialize;
use tracing::{debug, error, info, warn};

use super::base::{BaseMonitor, Monitor};
use crate::agents::{AgentContext, AgentRegistry};
use crate::error::Error;
use crate::utils::run_gh_command;

/// Issue data from GitHub API.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Issue {
    pub number: i64,
    pub title: String,
    pub body: Option<String>,
    pub author: Option<Author>,
    pub created_at: String,
    pub updated_at: Option<String>,
    pub labels: Option<Vec<Label>>,
    pub comments: Option<Vec<Comment>>,
}

/// Author information.
#[derive(Debug, Deserialize)]
pub struct Author {
    pub login: String,
}

/// Label information.
#[derive(Debug, Deserialize)]
pub struct Label {
    pub name: String,
}

/// Comment information.
#[derive(Debug, Deserialize)]
pub struct Comment {
    pub body: String,
    pub author: Option<Author>,
}

/// Issue monitor that watches for automation triggers on GitHub issues.
pub struct IssueMonitor {
    base: BaseMonitor,
    /// Agent registry for selecting and executing agents
    agent_registry: AgentRegistry,
}

impl IssueMonitor {
    /// Create a new issue monitor.
    pub fn new(running: Arc<AtomicBool>) -> Result<Self, Error> {
        Ok(Self {
            base: BaseMonitor::new(running)?,
            agent_registry: AgentRegistry::new(),
        })
    }

    /// Get recent open issues from the repository.
    async fn get_open_issues(&self, hours: u64) -> Result<Vec<Issue>, Error> {
        let output = run_gh_command(
            &[
                "issue",
                "list",
                "--repo",
                &self.base.config.repository,
                "--state",
                "open",
                "--json",
                "number,title,body,author,createdAt,updatedAt,labels,comments",
            ],
            true,
        )
        .await?;

        let issues: Vec<Issue> = match output {
            Some(json) => serde_json::from_str(&json)?,
            None => return Ok(Vec::new()),
        };

        // Filter by recent activity
        let cutoff = Utc::now() - Duration::hours(hours as i64);
        let recent_issues: Vec<Issue> = issues
            .into_iter()
            .filter(|issue| {
                // On parse failure, use epoch (1970-01-01) to treat as old, not new
                // This prevents malformed timestamps from being incorrectly flagged as new
                let created_at: DateTime<Utc> = issue
                    .created_at
                    .parse()
                    .unwrap_or_else(|_| DateTime::<Utc>::MIN_UTC);
                created_at >= cutoff
            })
            .collect();

        Ok(recent_issues)
    }

    /// Process a single issue.
    async fn process_single_issue(&self, issue: &Issue) -> Result<(), Error> {
        let issue_number = issue.number;

        // Check if we should process this issue
        if !self.base.should_process_item(issue_number, "issue") {
            return Ok(());
        }

        // Get comments as (body, author) pairs
        let comments: Vec<(String, String)> = issue
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
        let body = issue.body.as_deref().unwrap_or("");
        let author = issue
            .author
            .as_ref()
            .map(|a| a.login.as_str())
            .unwrap_or("");

        let trigger_info = self
            .base
            .security_manager
            .check_trigger_comment(body, author, &comments);

        let trigger_info = match trigger_info {
            Some(info) => info,
            None => return Ok(()), // No trigger found
        };

        info!(
            "Issue #{}: [{}][{}] by {}",
            issue_number,
            trigger_info.action,
            trigger_info.agent.as_deref().unwrap_or("auto"),
            trigger_info.username
        );

        // Perform security check (use a mutable reference)
        let action = format!("issue_{}", trigger_info.action);

        // Create a temporary mutable security manager for the check
        let mut security_manager = crate::security::SecurityManager::new();
        let (is_allowed, reason) = security_manager.perform_full_security_check(
            &trigger_info.username,
            &action,
            &self.base.config.repository,
        );

        if !is_allowed {
            warn!(
                "Security check failed for issue #{}: {}",
                issue_number, reason
            );
            self.base
                .post_security_rejection(issue_number, &reason, "issue")
                .await?;
            return Ok(());
        }

        // Handle the action
        match trigger_info.action.as_str() {
            "approved" | "fix" | "implement" => {
                self.handle_implementation(issue, &trigger_info).await?;
            },
            "close" => {
                self.handle_close(issue_number, &trigger_info.username)
                    .await?;
            },
            "summarize" => {
                self.handle_summarize(issue).await?;
            },
            "review" => {
                self.handle_review(issue).await?;
            },
            _ => {
                debug!("Unknown action: {}", trigger_info.action);
            },
        }

        Ok(())
    }

    /// Handle implementation request.
    async fn handle_implementation(
        &self,
        issue: &Issue,
        trigger_info: &crate::security::manager::TriggerInfo,
    ) -> Result<(), Error> {
        let issue_number = issue.number;
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
                self.base
                    .post_comment(issue_number, &comment, "issue")
                    .await?;
                return Ok(());
            },
        };

        let agent_display_name = agent.trigger_keyword();

        // Post starting work comment
        let comment = format!(
            "{} I'm starting work on this issue using **{}**!\n\n\
            This typically takes a few minutes.\n\n\
            *This comment was generated by the AI agent automation system.*",
            self.base.agent_tag, agent_display_name
        );
        self.base
            .post_comment(issue_number, &comment, "issue")
            .await?;

        // Build the prompt from issue content
        let issue_body = issue.body.as_deref().unwrap_or("");
        let prompt = format!(
            "Issue #{}: {}\n\n{}\n\n\
            Please analyze this issue and provide a solution. \
            If this requires code changes, provide the implementation.",
            issue_number, issue.title, issue_body
        );

        // Create context for the agent
        let context = AgentContext::for_implementation(
            issue_number,
            &issue.title,
            &format!("issue-{}-implementation", issue_number),
        );

        // Execute the agent
        info!(
            "Executing agent {} for issue #{}",
            agent.name(),
            issue_number
        );

        match agent.generate_code(&prompt, &context).await {
            Ok(response) => {
                // Format and post the response
                let truncated = if response.len() > 60000 {
                    format!(
                        "{}...\n\n*Response truncated due to length.*",
                        &response[..60000]
                    )
                } else {
                    response
                };

                let comment = format!(
                    "{} **Implementation Response from {}**\n\n\
                    {}\n\n\
                    ---\n\
                    *This comment was generated by the AI agent automation system.*",
                    self.base.agent_tag, agent_display_name, truncated
                );
                self.base
                    .post_comment(issue_number, &comment, "issue")
                    .await?;

                info!(
                    "Successfully processed issue #{} with agent {}",
                    issue_number,
                    agent.name()
                );
            },
            Err(e) => {
                error!(
                    "Agent {} failed for issue #{}: {}",
                    agent.name(),
                    issue_number,
                    e
                );

                let error_msg = match &e {
                    Error::AgentTimeout { timeout, .. } => {
                        format!("The agent timed out after {} seconds.", timeout)
                    },
                    Error::AgentExecutionFailed { stderr, .. } => {
                        let truncated_stderr = if stderr.len() > 500 {
                            format!("{}...", &stderr[..500])
                        } else {
                            stderr.clone()
                        };
                        format!("Agent execution failed:\n```\n{}\n```", truncated_stderr)
                    },
                    Error::AgentNotAvailable { reason, .. } => {
                        format!("Agent is not available: {}", reason)
                    },
                    _ => format!("An error occurred: {}", e),
                };

                let comment = format!(
                    "{} **Implementation Error with {}**\n\n\
                    {}\n\n\
                    Please try again or use a different agent.\n\n\
                    *This comment was generated by the AI agent automation system.*",
                    self.base.agent_tag, agent_display_name, error_msg
                );
                self.base
                    .post_comment(issue_number, &comment, "issue")
                    .await?;
            },
        }

        Ok(())
    }

    /// Handle close request.
    async fn handle_close(&self, issue_number: i64, username: &str) -> Result<(), Error> {
        info!("Closing issue #{}", issue_number);

        run_gh_command(
            &[
                "issue",
                "close",
                &issue_number.to_string(),
                "--repo",
                &self.base.config.repository,
            ],
            true,
        )
        .await?;

        let comment = format!(
            "{} Issue closed as requested by {}.\n\n\
            *This comment was generated by the AI agent automation system.*",
            self.base.agent_tag, username
        );
        self.base
            .post_comment(issue_number, &comment, "issue")
            .await?;

        Ok(())
    }

    /// Handle summarize request.
    async fn handle_summarize(&self, issue: &Issue) -> Result<(), Error> {
        let labels: Vec<&str> = issue
            .labels
            .as_ref()
            .map(|l| l.iter().map(|label| label.name.as_str()).collect())
            .unwrap_or_default();

        let body_preview = issue
            .body
            .as_deref()
            .unwrap_or("")
            .chars()
            .take(200)
            .collect::<String>();

        let comment = format!(
            "{} **Issue Summary:**\n\n\
            **Title:** {}\n\
            **Labels:** {}\n\
            **Description:** {}{}",
            self.base.agent_tag,
            issue.title,
            if labels.is_empty() {
                "None".to_string()
            } else {
                labels.join(", ")
            },
            body_preview,
            if issue.body.as_ref().map(|b| b.len()).unwrap_or(0) > 200 {
                "..."
            } else {
                ""
            }
        );
        self.base
            .post_comment(issue.number, &comment, "issue")
            .await?;

        Ok(())
    }

    /// Handle review request.
    async fn handle_review(&self, issue: &Issue) -> Result<(), Error> {
        let issue_number = issue.number;

        // Select an agent with review capability
        let agent = match self
            .agent_registry
            .select_for_capability(crate::agents::AgentCapability::CodeReview, None)
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
                self.base
                    .post_comment(issue_number, &comment, "issue")
                    .await?;
                return Ok(());
            },
        };

        // Build review prompt
        let issue_body = issue.body.as_deref().unwrap_or("");
        let prompt = format!(
            "Please review this issue and provide feedback:\n\n\
            Issue #{}: {}\n\n{}\n\n\
            Analyze the issue for:\n\
            - Clarity and completeness\n\
            - Technical feasibility\n\
            - Potential edge cases\n\
            - Suggested implementation approach",
            issue_number, issue.title, issue_body
        );

        let context = AgentContext::for_review(issue_number, &issue.title);

        info!(
            "Executing review with agent {} for issue #{}",
            agent.name(),
            issue_number
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
                    "{} **Issue Review by {}**\n\n\
                    {}\n\n\
                    ---\n\
                    *This comment was generated by the AI agent automation system.*",
                    self.base.agent_tag,
                    agent.trigger_keyword(),
                    truncated
                );
                self.base
                    .post_comment(issue_number, &comment, "issue")
                    .await?;
            },
            Err(e) => {
                error!("Review failed for issue #{}: {}", issue_number, e);
                self.base
                    .post_error_comment(issue_number, &e.to_string(), "issue")
                    .await?;
            },
        }

        Ok(())
    }
}

#[async_trait::async_trait]
impl Monitor for IssueMonitor {
    async fn process_items(&self) -> Result<(), Error> {
        info!(
            "Processing issues for repository: {}",
            self.base.config.repository
        );

        // Ensure GitHub CLI is available
        self.base.ensure_gh_available().await?;

        if self.base.config.review_only_mode {
            info!("Running in review-only mode");
        }

        let issues = self.get_open_issues(24).await?;
        info!("Found {} recent open issues", issues.len());

        for issue in &issues {
            if let Err(e) = self.process_single_issue(issue).await {
                warn!("Error processing issue #{}: {}", issue.number, e);
            }
        }

        Ok(())
    }

    async fn run_continuous(&self, interval_secs: u64) -> Result<(), Error> {
        info!(
            "Running issue monitor continuously (interval: {}s)",
            interval_secs
        );

        self.base
            .run_continuous_impl(|| self.process_items(), interval_secs, "IssueMonitor")
            .await
    }

    fn name(&self) -> &str {
        "IssueMonitor"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_issue_deserialization() {
        let json = r#"{
            "number": 42,
            "title": "Test Issue",
            "body": "Issue body",
            "author": {"login": "testuser"},
            "createdAt": "2024-01-01T00:00:00Z",
            "labels": [{"name": "bug"}],
            "comments": []
        }"#;

        let issue: Issue = serde_json::from_str(json).unwrap();
        assert_eq!(issue.number, 42);
        assert_eq!(issue.title, "Test Issue");
    }
}
