//! Issue monitor implementation.
//!
//! Monitors GitHub issues for automation triggers from authorized users.
//!
//! Supported triggers: `[Approved][Agent]` (implementation), `[Review]`,
//! `[Debug]`, `[Summarize]` and `[Close]`.

use std::sync::Arc;
use std::sync::atomic::AtomicBool;

use chrono::Utc;
use serde::Deserialize;
use tracing::{error, info, warn};

use super::base::{
    Author, BaseMonitor, GhComment, ItemKind, Label, Monitor, comment_views, is_recent, parse_time,
};
use crate::agents::{AgentCapability, AgentContext};
use crate::error::Error;
use crate::security::TriggerInfo;
use crate::utils::run_gh_command;
use crate::utils::text::truncate_str;

const KIND: ItemKind = ItemKind::Issue;

/// Issue data from GitHub API.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Issue {
    pub number: u64,
    pub title: String,
    pub body: Option<String>,
    pub author: Option<Author>,
    pub created_at: String,
    pub updated_at: Option<String>,
    pub labels: Option<Vec<Label>>,
    pub comments: Option<Vec<GhComment>>,
}

/// Issue monitor that watches for automation triggers on GitHub issues.
pub struct IssueMonitor {
    base: BaseMonitor,
}

impl IssueMonitor {
    /// Create a new issue monitor.
    pub fn new(running: Arc<AtomicBool>) -> Result<Self, Error> {
        Ok(Self {
            base: BaseMonitor::new(running)?,
        })
    }

    /// Get open issues with activity inside the lookback window.
    async fn get_recent_issues(&self) -> Result<Vec<Issue>, Error> {
        let output = run_gh_command(
            &[
                "issue",
                "list",
                "--repo",
                &self.base.config.repository,
                "--state",
                "open",
                "--limit",
                "100",
                "--json",
                "number,title,body,author,createdAt,updatedAt,labels,comments",
            ],
            true,
        )
        .await?
        .unwrap_or_default();

        let issues: Vec<Issue> = serde_json::from_str(output.trim())?;
        let now = Utc::now();
        Ok(issues
            .into_iter()
            .filter(|i| is_recent(i.updated_at.as_deref(), &i.created_at, now))
            .collect())
    }

    /// Process a single issue.
    async fn process_single_issue(&self, issue: &Issue) -> Result<(), Error> {
        if !self.base.should_process_item(issue.number, KIND) {
            return Ok(());
        }

        let comments = comment_views(issue.comments.as_deref());
        let body = issue.body.as_deref().unwrap_or("");
        let author = issue
            .author
            .as_ref()
            .map(|a| a.login.as_str())
            .unwrap_or("");

        let Some(trigger) = self
            .base
            .resolve_trigger(
                KIND,
                issue.number,
                body,
                author,
                parse_time(Some(&issue.created_at)),
                &comments,
            )
            .await?
        else {
            return Ok(());
        };

        match trigger.action.as_str() {
            "approved" => self.handle_implementation(issue, &trigger).await,
            "close" => {
                self.base
                    .close_item(KIND, issue.number, &trigger.username)
                    .await
            },
            "summarize" => self.handle_summarize(issue).await,
            "review" => self.handle_analysis(issue, &trigger, false).await,
            "debug" => self.handle_analysis(issue, &trigger, true).await,
            other => {
                self.base
                    .reply(
                        KIND,
                        issue.number,
                        &format!("Unsupported action `{}`.", other),
                    )
                    .await
            },
        }
    }

    /// Handle `[Approved]`: ask the agent for an implementation.
    async fn handle_implementation(
        &self,
        issue: &Issue,
        trigger: &TriggerInfo,
    ) -> Result<(), Error> {
        let number = issue.number;
        if self.base.config.review_only_mode {
            return self
                .base
                .reply(
                    KIND,
                    number,
                    "**Review-only mode**\n\nImplementation requests are disabled for this run \
                     (REVIEW_ONLY_MODE=true). Use `[Review]` or `[Summarize]` instead.",
                )
                .await;
        }

        let agent = match self
            .base
            .agent_registry
            .select_agent(trigger.agent.as_deref())
            .await
        {
            Ok(a) => a,
            Err(e) => {
                return self
                    .base
                    .post_agent_error(KIND, number, "agent selection", &e)
                    .await;
            },
        };
        let display = agent.trigger_keyword().to_string();

        self.base
            .reply(
                KIND,
                number,
                &format!(
                    "I'm starting work on this issue using **{}**!\n\nThis typically takes a few minutes.",
                    display
                ),
            )
            .await?;

        let prompt = format!(
            "Issue #{}: {}\n\n{}\n\n\
             Please analyze this issue and provide a solution. \
             If this requires code changes, provide the implementation.",
            number,
            issue.title,
            issue.body.as_deref().unwrap_or("")
        );
        let context = AgentContext::for_implementation(
            number,
            &issue.title,
            &format!("issue-{}-implementation", number),
        );

        info!("Executing agent {} for issue #{}", agent.name(), number);
        match agent.generate_code(&prompt, &context).await {
            Ok(response) => {
                self.base
                    .post_agent_output(
                        KIND,
                        number,
                        &format!("Implementation Response from {}", display),
                        &response,
                    )
                    .await?;
                info!("Processed issue #{} with agent {}", number, agent.name());
                Ok(())
            },
            Err(e) => {
                error!("Agent {} failed for issue #{}: {}", agent.name(), number, e);
                self.base.post_agent_error(KIND, number, &display, &e).await
            },
        }
    }

    /// Handle `[Summarize]`: deterministic summary (no agent call).
    async fn handle_summarize(&self, issue: &Issue) -> Result<(), Error> {
        let labels: Vec<&str> = issue
            .labels
            .as_deref()
            .unwrap_or_default()
            .iter()
            .map(|l| l.name.as_str())
            .collect();
        let body = issue.body.as_deref().unwrap_or("");
        let preview = truncate_str(body, 200);
        let ellipsis = if preview.len() < body.len() {
            "..."
        } else {
            ""
        };

        let text = format!(
            "**Issue Summary:**\n\n**Title:** {}\n**Labels:** {}\n**Description:** {}{}",
            issue.title,
            if labels.is_empty() {
                "None".to_string()
            } else {
                labels.join(", ")
            },
            crate::security::neutralize_triggers(preview),
            ellipsis
        );
        self.base.reply(KIND, issue.number, &text).await
    }

    /// Handle `[Review]` / `[Debug]`: text-only analysis by an agent.
    async fn handle_analysis(
        &self,
        issue: &Issue,
        trigger: &TriggerInfo,
        is_debug: bool,
    ) -> Result<(), Error> {
        let number = issue.number;
        let capability = if is_debug {
            AgentCapability::Debugging
        } else {
            AgentCapability::CodeReview
        };
        let agent = match self
            .base
            .agent_registry
            .select_for_capability(capability, trigger.agent.as_deref())
            .await
        {
            Ok(a) => a,
            Err(e) => {
                return self
                    .base
                    .post_agent_error(KIND, number, "agent selection", &e)
                    .await;
            },
        };

        let focus = if is_debug {
            "Debug this issue:\n\
             - Identify the most likely root cause(s)\n\
             - Point to the relevant code paths\n\
             - Propose concrete steps to reproduce and fix"
        } else {
            "Analyze the issue for:\n\
             - Clarity and completeness\n\
             - Technical feasibility\n\
             - Potential edge cases\n\
             - Suggested implementation approach"
        };
        let prompt = format!(
            "Please review this issue and provide feedback:\n\n\
             Issue #{}: {}\n\n{}\n\n{}",
            number,
            issue.title,
            issue.body.as_deref().unwrap_or(""),
            focus
        );

        let context = AgentContext::for_review(number, &issue.title);
        info!(
            "Executing {} with agent {} for issue #{}",
            if is_debug { "debug" } else { "review" },
            agent.name(),
            number
        );
        let heading = format!(
            "Issue {} by {}",
            if is_debug { "Debug Analysis" } else { "Review" },
            agent.trigger_keyword()
        );
        match agent.generate_code(&prompt, &context).await {
            Ok(response) => {
                self.base
                    .post_agent_output(KIND, number, &heading, &response)
                    .await
            },
            Err(e) => {
                error!("Analysis failed for issue #{}: {}", number, e);
                self.base
                    .post_agent_error(KIND, number, agent.trigger_keyword(), &e)
                    .await
            },
        }
    }
}

#[async_trait::async_trait]
impl Monitor for IssueMonitor {
    async fn process_items(&self) -> Result<(), Error> {
        info!(
            "Processing issues for repository: {}",
            self.base.config.repository
        );
        self.base.ensure_gh_available().await?;
        if self.base.config.review_only_mode {
            info!("Running in review-only mode");
        }

        let issues = self.get_recent_issues().await?;
        info!("Found {} recently active open issues", issues.len());

        for issue in &issues {
            if !self.base.is_running() {
                return Err(Error::Interrupted);
            }
            if let Err(e) = self.process_single_issue(issue).await {
                warn!("Error processing issue #{}: {}", issue.number, e);
            }
        }
        Ok(())
    }

    async fn run_continuous(&self, interval_secs: u64) -> Result<(), Error> {
        self.base
            .run_continuous_impl(|| self.process_items(), interval_secs, "IssueMonitor")
            .await
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
            "comments": [{"body": "[Approved]", "author": {"login": "a"}, "createdAt": "2024-01-02T00:00:00Z"}]
        }"#;

        let issue: Issue = serde_json::from_str(json).unwrap();
        assert_eq!(issue.number, 42);
        assert_eq!(issue.title, "Test Issue");
        assert_eq!(comment_views(issue.comments.as_deref())[0].author, "a");
    }
}
