//! Backlog refinement monitor for multi-agent issue review.
//!
//! This module orchestrates multiple AI agents reviewing backlog items
//! and posting unique insights as comments.

use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::AtomicBool;

use chrono::{DateTime, Duration, Utc};
use regex::Regex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tracing::{debug, error, info, warn};

use super::base::{BaseMonitor, Monitor};
use crate::agents::{Agent, AgentContext, AgentRegistry};
use crate::error::Error;
use crate::utils::run_gh_command;

/// Represents an insight from agent review.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RefinementInsight {
    /// Name of the agent that generated this insight
    pub agent_name: String,
    /// Issue number this insight is for
    pub issue_number: i64,
    /// The insight content
    pub content: String,
    /// Type of insight (implementation, quality, blocker, decomposition)
    pub insight_type: String,
    /// Confidence level (0.0-1.0)
    pub confidence: f64,
    /// When this insight was generated
    pub timestamp: DateTime<Utc>,
}

impl RefinementInsight {
    /// Create a new refinement insight.
    pub fn new(
        agent_name: String,
        issue_number: i64,
        content: String,
        insight_type: String,
        confidence: f64,
    ) -> Self {
        Self {
            agent_name,
            issue_number,
            content,
            insight_type,
            confidence,
            timestamp: Utc::now(),
        }
    }

    /// Generate a fingerprint for this insight.
    pub fn fingerprint(&self) -> String {
        let content = format!(
            "{}|{}|{}",
            self.agent_name,
            self.issue_number,
            &self.content[..self.content.len().min(100)]
        );
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        let result = hasher.finalize();
        hex::encode(&result[..6])
    }

    /// Generate GitHub comment body.
    pub fn to_comment_body(&self) -> String {
        format!(
            "### Insight from {}\n\n\
            {}\n\n\
            ---\n\
            *Backlog refinement by {} on {}*\n\
            *This is an automated analysis - human review recommended*\n\n\
            <!-- backlog-refinement:{}:{}:{} -->",
            self.agent_name.to_uppercase(),
            self.content,
            self.agent_name,
            self.timestamp.format("%Y-%m-%d"),
            self.agent_name,
            self.timestamp.format("%Y-%m-%d"),
            self.fingerprint()
        )
    }
}

/// Represents an action to take on an issue.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IssueAction {
    /// Type of action (close, update_title, update_body, add_label, remove_label, link_pr)
    pub action_type: String,
    /// Issue number to act on
    pub issue_number: i64,
    /// Action details (varies by action type)
    pub details: HashMap<String, String>,
    /// Reason for this action
    pub reason: String,
    /// Username who triggered this action
    pub triggered_by: String,
    /// Whether this action has been executed
    pub executed: bool,
}

/// Result of refining a single issue.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct RefinementResult {
    /// Issue number that was refined
    pub issue_number: i64,
    /// Issue title
    pub issue_title: String,
    /// Number of insights added
    pub insights_added: usize,
    /// Number of insights skipped (duplicates, etc.)
    pub insights_skipped: usize,
    /// Agents that reviewed this issue
    pub agents_reviewed: Vec<String>,
    /// Actions taken on this issue
    pub actions_taken: Vec<IssueAction>,
    /// Error message if refinement failed
    pub error: Option<String>,
}

/// Issue data for refinement.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RefinementIssue {
    pub number: i64,
    pub title: String,
    pub body: Option<String>,
    pub labels: Option<Vec<Label>>,
    pub created_at: String,
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
    #[serde(rename = "createdAt")]
    pub created_at: Option<String>,
}

/// Author information.
#[derive(Debug, Deserialize)]
pub struct Author {
    pub login: String,
}

/// Configuration for the refinement monitor.
#[derive(Debug, Clone)]
pub struct RefinementConfig {
    /// Minimum issue age in days to review
    pub min_age_days: i64,
    /// Maximum issue age in days to review
    pub max_age_days: i64,
    /// Labels to exclude from review
    pub exclude_labels: Vec<String>,
    /// Maximum issues to review per run
    pub max_issues_per_run: usize,
    /// Maximum comments to add per issue
    pub max_comments_per_issue: usize,
    /// Days before same agent can comment again
    pub agent_cooldown_days: i64,
    /// Minimum insight length to post
    pub min_insight_length: usize,
    /// Maximum insight length to post
    pub max_insight_length: usize,
    /// If true, don't post comments
    pub dry_run: bool,
    /// If true, allow agents to manage issues
    pub enable_issue_management: bool,
    /// Usernames with maintainer authority
    pub agent_admins: Vec<String>,
}

impl Default for RefinementConfig {
    fn default() -> Self {
        Self {
            min_age_days: 3,
            max_age_days: 90,
            exclude_labels: vec![
                "blocked".to_string(),
                "wontfix".to_string(),
                "in-progress".to_string(),
            ],
            max_issues_per_run: 10,
            max_comments_per_issue: 2,
            agent_cooldown_days: 14,
            min_insight_length: 50,
            max_insight_length: 60000,
            dry_run: false,
            enable_issue_management: false,
            agent_admins: Vec::new(),
        }
    }
}

/// Agent-specific prompts for different perspectives.
pub struct AgentPrompts;

impl AgentPrompts {
    /// Get the architectural review prompt for Claude.
    pub fn claude(title: &str, body: &str, comments: &str) -> String {
        format!(
            r#"Review this GitHub issue from an ARCHITECTURAL perspective.

Issue: {}
Description:
{}

Existing comments:
{}

Consider:
1. Are there design patterns that would help implementation?
2. Are there existing utilities in the codebase that could be reused?
3. Are there potential breaking changes or migration needs?
4. What's the recommended implementation order if multiple components?

IMPORTANT: Only respond if you have a UNIQUE insight not already in the issue or comments.
If you have nothing new to add, respond with exactly: NO_NEW_INSIGHT

If you have an insight, format it as:
INSIGHT_TYPE: (implementation|quality|blocker|decomposition)
CONFIDENCE: (0.0-1.0)
INSIGHT:
[Your insight here - be specific and actionable]"#,
            title, body, comments
        )
    }

    /// Get the quality/security review prompt for Gemini.
    pub fn gemini(title: &str, body: &str, comments: &str) -> String {
        format!(
            r#"Review this GitHub issue for QUALITY and SECURITY considerations.

Issue: {}
Description:
{}

Existing comments:
{}

Consider:
1. Are there security implications to be aware of?
2. Are there edge cases not mentioned in the issue?
3. What test scenarios should be covered?
4. Are there related issues that should be linked?

IMPORTANT: Only respond if you have a UNIQUE insight not already captured.
If everything is already covered, respond with exactly: NO_NEW_INSIGHT

If you have an insight, format it as:
INSIGHT_TYPE: (implementation|quality|blocker|decomposition)
CONFIDENCE: (0.0-1.0)
INSIGHT:
[Your insight here - be specific and actionable]"#,
            title, body, comments
        )
    }

    /// Get the implementation review prompt for Codex.
    pub fn codex(title: &str, body: &str, comments: &str) -> String {
        format!(
            r#"Review this GitHub issue from an IMPLEMENTATION perspective.

Issue: {}
Description:
{}

Existing comments:
{}

Consider:
1. What's the estimated complexity (XS/S/M/L/XL)?
2. Are there performance considerations?
3. What dependencies or blockers exist?
4. Can you suggest a concrete implementation approach?

IMPORTANT: Only add if you have NEW information to contribute.
If the implementation path is already clear, respond with exactly: NO_NEW_INSIGHT

If you have an insight, format it as:
INSIGHT_TYPE: (implementation|quality|blocker|decomposition)
CONFIDENCE: (0.0-1.0)
INSIGHT:
[Your insight here - be specific and actionable]"#,
            title, body, comments
        )
    }

    /// Get the maintainability review prompt for OpenCode.
    pub fn opencode(title: &str, body: &str, comments: &str) -> String {
        format!(
            r#"Review this GitHub issue for MAINTAINABILITY concerns.

Issue: {}
Description:
{}

Existing comments:
{}

Consider:
1. Will this create technical debt?
2. Are there documentation requirements?
3. Does this need coordination with other systems?
4. Should this be broken into smaller issues?

IMPORTANT: Only add a comment if you have something UNIQUE to contribute.
If no new insights, respond with exactly: NO_NEW_INSIGHT

If you have an insight, format it as:
INSIGHT_TYPE: (implementation|quality|blocker|decomposition)
CONFIDENCE: (0.0-1.0)
INSIGHT:
[Your insight here - be specific and actionable]"#,
            title, body, comments
        )
    }

    /// Get prompt for a given agent name.
    pub fn for_agent(agent_name: &str, title: &str, body: &str, comments: &str) -> Option<String> {
        match agent_name.to_lowercase().as_str() {
            "claude" => Some(Self::claude(title, body, comments)),
            "gemini" => Some(Self::gemini(title, body, comments)),
            "codex" => Some(Self::codex(title, body, comments)),
            "opencode" => Some(Self::opencode(title, body, comments)),
            _ => None,
        }
    }
}

/// Refinement monitor that orchestrates multi-agent backlog review.
pub struct RefinementMonitor {
    base: BaseMonitor,
    config: RefinementConfig,
    agent_registry: AgentRegistry,
    /// Regex pattern for matching refinement markers in comments
    marker_pattern: Regex,
}

impl RefinementMonitor {
    /// Maximum characters for issue body to prevent context window exhaustion.
    const MAX_BODY_LENGTH: usize = 5000;

    /// Create a new refinement monitor.
    pub fn new(running: Arc<AtomicBool>, config: RefinementConfig) -> Result<Self, Error> {
        let marker_pattern =
            Regex::new(r"<!-- backlog-refinement:(\w+):(\d{4}-\d{2}-\d{2}):(\w+) -->")
                .map_err(|e| Error::Config(format!("Invalid marker pattern: {}", e)))?;

        Ok(Self {
            base: BaseMonitor::new(running)?,
            config,
            agent_registry: AgentRegistry::new(),
            marker_pattern,
        })
    }

    /// Run the refinement process.
    pub async fn run(
        &self,
        agent_names: Option<Vec<&str>>,
    ) -> Result<Vec<RefinementResult>, Error> {
        let agents_to_use: Vec<String> = agent_names
            .map(|names| names.into_iter().map(String::from).collect())
            .unwrap_or_else(|| {
                vec![
                    "claude".to_string(),
                    "gemini".to_string(),
                    "codex".to_string(),
                    "opencode".to_string(),
                ]
            });

        info!(
            "Starting backlog refinement with agents: {:?}",
            agents_to_use
        );

        // Get issues to refine
        let issues = self.get_issues_to_refine().await?;
        info!("Found {} issues to refine", issues.len());

        let mut results = Vec::new();

        for issue in issues.into_iter().take(self.config.max_issues_per_run) {
            let result = self.refine_issue(&issue, &agents_to_use).await;
            results.push(result);
        }

        // Log summary
        let total_insights: usize = results.iter().map(|r| r.insights_added).sum();
        info!(
            "Refinement complete: {} issues reviewed, {} insights added",
            results.len(),
            total_insights
        );

        Ok(results)
    }

    /// Get issues that need refinement.
    async fn get_issues_to_refine(&self) -> Result<Vec<RefinementIssue>, Error> {
        let cutoff_min = Utc::now() - Duration::days(self.config.max_age_days);
        let cutoff_max = Utc::now() - Duration::days(self.config.min_age_days);

        let search_query = format!(
            "created:{}..{}",
            cutoff_min.format("%Y-%m-%d"),
            cutoff_max.format("%Y-%m-%d")
        );

        let output = run_gh_command(
            &[
                "issue",
                "list",
                "--repo",
                &self.base.config.repository,
                "--state",
                "open",
                "--search",
                &search_query,
                "--json",
                "number,title,body,labels,createdAt",
                "--limit",
                "100",
            ],
            true,
        )
        .await?;

        let issues: Vec<RefinementIssue> = match output {
            Some(json) => serde_json::from_str(&json)?,
            None => return Ok(Vec::new()),
        };

        // Filter by excluded labels
        let filtered: Vec<RefinementIssue> = issues
            .into_iter()
            .filter(|issue| {
                let labels: Vec<&str> = issue
                    .labels
                    .as_ref()
                    .map(|l| l.iter().map(|label| label.name.as_str()).collect())
                    .unwrap_or_default();

                !labels
                    .iter()
                    .any(|label| self.config.exclude_labels.contains(&label.to_string()))
            })
            .collect();

        Ok(filtered)
    }

    /// Refine a single issue with multiple agents.
    async fn refine_issue(
        &self,
        issue: &RefinementIssue,
        agent_names: &[String],
    ) -> RefinementResult {
        let mut result = RefinementResult {
            issue_number: issue.number,
            issue_title: issue.title.clone(),
            ..Default::default()
        };

        // Get existing comments
        let existing_comments = match self.get_issue_comments(issue.number).await {
            Ok(comments) => comments,
            Err(e) => {
                result.error = Some(format!("Failed to get comments: {}", e));
                return result;
            }
        };

        let existing_refinements = self.extract_existing_refinements(&existing_comments);
        let mut comments_added = 0;

        for agent_name in agent_names {
            if comments_added >= self.config.max_comments_per_issue {
                break;
            }

            // Check cooldown
            if self.is_agent_on_cooldown(agent_name, &existing_refinements) {
                debug!(
                    "Agent {} on cooldown for issue #{}",
                    agent_name, issue.number
                );
                continue;
            }

            // Get agent
            let agent = match self.agent_registry.get(agent_name) {
                Some(a) => a,
                None => {
                    warn!("Agent {} not available", agent_name);
                    continue;
                }
            };

            // Check if agent is available
            if !agent.is_available().await {
                debug!("Agent {} not available", agent_name);
                continue;
            }

            result.agents_reviewed.push(agent_name.clone());

            // Get insight from agent
            let insight = self
                .get_agent_insight(agent.as_ref(), agent_name, issue, &existing_comments)
                .await;

            match insight {
                Some(insight) => {
                    if self.post_insight(&insight).await {
                        result.insights_added += 1;
                        comments_added += 1;
                    } else {
                        result.insights_skipped += 1;
                    }
                }
                None => {
                    result.insights_skipped += 1;
                }
            }
        }

        result
    }

    /// Get comments on an issue.
    async fn get_issue_comments(&self, issue_number: i64) -> Result<Vec<Comment>, Error> {
        let output = run_gh_command(
            &[
                "issue",
                "view",
                &issue_number.to_string(),
                "--repo",
                &self.base.config.repository,
                "--json",
                "comments",
            ],
            false,
        )
        .await?;

        match output {
            Some(json) => {
                #[derive(Deserialize)]
                struct CommentsWrapper {
                    comments: Vec<Comment>,
                }
                let wrapper: CommentsWrapper = serde_json::from_str(&json)?;
                Ok(wrapper.comments)
            }
            None => Ok(Vec::new()),
        }
    }

    /// Extract existing refinement markers from comments.
    fn extract_existing_refinements(&self, comments: &[Comment]) -> HashMap<String, DateTime<Utc>> {
        let mut refinements = HashMap::new();

        for comment in comments {
            for cap in self.marker_pattern.captures_iter(&comment.body) {
                if let (Some(agent_name), Some(date_str)) = (cap.get(1), cap.get(2)) {
                    if let Ok(date) =
                        chrono::NaiveDate::parse_from_str(date_str.as_str(), "%Y-%m-%d")
                    {
                        let datetime = date
                            .and_hms_opt(0, 0, 0)
                            .map(|dt| DateTime::<Utc>::from_naive_utc_and_offset(dt, Utc))
                            .unwrap_or_else(Utc::now);

                        let name = agent_name.as_str().to_lowercase();
                        if !refinements.contains_key(&name) || datetime > refinements[&name] {
                            refinements.insert(name, datetime);
                        }
                    }
                }
            }
        }

        refinements
    }

    /// Check if agent is on cooldown for this issue.
    fn is_agent_on_cooldown(
        &self,
        agent_name: &str,
        existing_refinements: &HashMap<String, DateTime<Utc>>,
    ) -> bool {
        let name = agent_name.to_lowercase();
        if let Some(last_refinement) = existing_refinements.get(&name) {
            let cooldown = Duration::days(self.config.agent_cooldown_days);
            Utc::now() - *last_refinement < cooldown
        } else {
            false
        }
    }

    /// Get an insight from an agent for an issue.
    async fn get_agent_insight(
        &self,
        agent: &dyn Agent,
        agent_name: &str,
        issue: &RefinementIssue,
        existing_comments: &[Comment],
    ) -> Option<RefinementInsight> {
        // Format comments for context
        let comment_text: String = existing_comments
            .iter()
            .rev()
            .take(5)
            .map(|c| {
                let author = c
                    .author
                    .as_ref()
                    .map(|a| a.login.as_str())
                    .unwrap_or("unknown");
                let body_preview = &c.body[..c.body.len().min(200)];
                format!("- {}: {}...", author, body_preview)
            })
            .collect::<Vec<_>>()
            .join("\n\n");

        // Truncate body
        let body = issue.body.as_deref().unwrap_or("(no description)");
        let truncated_body = if body.len() > Self::MAX_BODY_LENGTH {
            format!(
                "{}... (truncated at {} chars)",
                &body[..Self::MAX_BODY_LENGTH],
                Self::MAX_BODY_LENGTH
            )
        } else {
            body.to_string()
        };

        // Get prompt for this agent
        let prompt = AgentPrompts::for_agent(
            agent_name,
            &issue.title,
            &truncated_body,
            if comment_text.is_empty() {
                "(no comments)"
            } else {
                &comment_text
            },
        )?;

        // Execute the agent
        let context = AgentContext::for_review(issue.number, &issue.title);

        match agent.review(&prompt).await {
            Ok(response) => {
                if response.contains("NO_NEW_INSIGHT") {
                    return None;
                }
                self.parse_insight_response(&response, agent_name, issue.number)
            }
            Err(e) => {
                error!("Agent {} failed: {}", agent_name, e);
                None
            }
        }
    }

    /// Parse agent response into an insight.
    fn parse_insight_response(
        &self,
        response: &str,
        agent_name: &str,
        issue_number: i64,
    ) -> Option<RefinementInsight> {
        // Extract insight type
        let insight_type = if let Some(cap) = Regex::new(r"INSIGHT_TYPE:\s*(\w+)")
            .ok()
            .and_then(|re| re.captures(response))
        {
            cap.get(1)
                .map(|m| m.as_str().to_lowercase())
                .unwrap_or_else(|| "implementation".to_string())
        } else {
            "implementation".to_string()
        };

        // Extract confidence
        let confidence = if let Some(cap) = Regex::new(r"CONFIDENCE:\s*([\d.]+)")
            .ok()
            .and_then(|re| re.captures(response))
        {
            cap.get(1)
                .and_then(|m| m.as_str().parse().ok())
                .unwrap_or(0.7)
        } else {
            0.7
        };

        // Extract content
        let content = if response.contains("INSIGHT:") {
            response.split("INSIGHT:").nth(1).unwrap_or(response).trim()
        } else {
            response
        };

        // Clean up content (remove HTML comments)
        let content = Regex::new(r"<!--.*?-->")
            .ok()
            .map(|re| re.replace_all(content, ""))
            .unwrap_or_else(|| content.into())
            .trim()
            .to_string();

        // Validate length
        if content.len() < self.config.min_insight_length {
            return None;
        }

        let content = if content.len() > self.config.max_insight_length {
            format!("{}...", &content[..self.config.max_insight_length])
        } else {
            content
        };

        Some(RefinementInsight::new(
            agent_name.to_string(),
            issue_number,
            content,
            insight_type,
            confidence,
        ))
    }

    /// Post an insight as a comment.
    async fn post_insight(&self, insight: &RefinementInsight) -> bool {
        if self.config.dry_run {
            info!(
                "[DRY RUN] Would post insight from {} to #{}: {}...",
                insight.agent_name,
                insight.issue_number,
                &insight.content[..insight.content.len().min(50)]
            );
            return true;
        }

        let comment_body = insight.to_comment_body();

        let result = run_gh_command(
            &[
                "issue",
                "comment",
                &insight.issue_number.to_string(),
                "--repo",
                &self.base.config.repository,
                "--body",
                &comment_body,
            ],
            false,
        )
        .await;

        match result {
            Ok(Some(_)) => {
                info!(
                    "Posted insight from {} to issue #{}",
                    insight.agent_name, insight.issue_number
                );
                true
            }
            Ok(None) => {
                // Command succeeded but no output
                info!(
                    "Posted insight from {} to issue #{}",
                    insight.agent_name, insight.issue_number
                );
                true
            }
            Err(e) => {
                error!(
                    "Failed to post comment to issue #{}: {}",
                    insight.issue_number, e
                );
                false
            }
        }
    }
}

#[async_trait::async_trait]
impl Monitor for RefinementMonitor {
    async fn process_items(&self) -> Result<(), Error> {
        info!(
            "Processing refinement for repository: {}",
            self.base.config.repository
        );

        // Ensure GitHub CLI is available
        self.base.ensure_gh_available().await?;

        let results = self.run(None).await?;

        // Log summary
        let total_insights: usize = results.iter().map(|r| r.insights_added).sum();
        let total_skipped: usize = results.iter().map(|r| r.insights_skipped).sum();
        let errors: Vec<_> = results.iter().filter(|r| r.error.is_some()).collect();

        info!(
            "Refinement cycle complete: {} issues, {} insights added, {} skipped, {} errors",
            results.len(),
            total_insights,
            total_skipped,
            errors.len()
        );

        Ok(())
    }

    async fn run_continuous(&self, interval_secs: u64) -> Result<(), Error> {
        info!(
            "Running refinement monitor continuously (interval: {}s)",
            interval_secs
        );

        self.base
            .run_continuous_impl(|| self.process_items(), interval_secs, "RefinementMonitor")
            .await
    }

    fn name(&self) -> &str {
        "RefinementMonitor"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_refinement_insight_fingerprint() {
        let insight = RefinementInsight::new(
            "claude".to_string(),
            42,
            "Test insight content".to_string(),
            "implementation".to_string(),
            0.8,
        );

        let fingerprint = insight.fingerprint();
        assert_eq!(fingerprint.len(), 12);
    }

    #[test]
    fn test_refinement_insight_to_comment() {
        let insight = RefinementInsight::new(
            "claude".to_string(),
            42,
            "Test insight".to_string(),
            "implementation".to_string(),
            0.8,
        );

        let comment = insight.to_comment_body();
        assert!(comment.contains("Insight from CLAUDE"));
        assert!(comment.contains("Test insight"));
        assert!(comment.contains("backlog-refinement:claude:"));
    }

    #[test]
    fn test_agent_prompts() {
        let prompt = AgentPrompts::claude("Test Title", "Test Body", "Test Comments");
        assert!(prompt.contains("ARCHITECTURAL"));
        assert!(prompt.contains("Test Title"));

        let prompt = AgentPrompts::gemini("Test Title", "Test Body", "Test Comments");
        assert!(prompt.contains("QUALITY and SECURITY"));

        let prompt = AgentPrompts::codex("Test Title", "Test Body", "Test Comments");
        assert!(prompt.contains("IMPLEMENTATION"));

        let prompt = AgentPrompts::opencode("Test Title", "Test Body", "Test Comments");
        assert!(prompt.contains("MAINTAINABILITY"));
    }

    #[test]
    fn test_config_default() {
        let config = RefinementConfig::default();
        assert_eq!(config.min_age_days, 3);
        assert_eq!(config.max_age_days, 90);
        assert_eq!(config.max_issues_per_run, 10);
        assert_eq!(config.agent_cooldown_days, 14);
        assert!(!config.dry_run);
    }
}
