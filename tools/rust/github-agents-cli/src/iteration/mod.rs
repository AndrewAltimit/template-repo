//! Agent iteration tracking module.
//!
//! Tracks agent iteration counts from PR comments to prevent infinite loops.
//! Supports the `[CONTINUE]` command (from agent admins) to extend limits.
//!
//! Counting rules:
//! - Each comment carrying `<!-- agent-metadata:type=TYPE:iteration=N -->`
//!   for the requested type counts as one iteration. Markers are counted
//!   regardless of author: a forged marker can only *stop* automation early,
//!   which is the fail-safe direction.
//! - `...:limit-reached` markers (posted when the limit is hit) are notices,
//!   not iterations, and are not counted.
//! - `[CONTINUE]` counts only when written by an agent admin, outside code,
//!   quotes and HTML comments, and not inside tool-generated comments.

use std::sync::LazyLock;

use regex::Regex;
use serde::{Deserialize, Serialize};
use tracing::{debug, info};

use crate::error::Error;
use crate::security::trigger::{contains_continue_command, is_agent_generated};
use crate::utils::{parse_paginated_array, run_gh_command};

/// Pattern for agent metadata markers in comments.
/// Format: `<!-- agent-metadata:type=TYPE:iteration=N[:limit-reached] -->`
static AGENT_MARKER_PATTERN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"<!-- agent-metadata:type=([a-z-]+):iteration=(\d+)(:limit-reached)?")
        .expect("valid marker regex")
});

/// Valid agent types for iteration tracking.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AgentType {
    ReviewFix,
    FailureFix,
}

impl AgentType {
    /// Parse agent type from string.
    pub fn parse(s: &str) -> Option<Self> {
        match s.trim().to_lowercase().as_str() {
            "review-fix" => Some(Self::ReviewFix),
            "failure-fix" => Some(Self::FailureFix),
            _ => None,
        }
    }

    /// Get the string identifier for this agent type.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::ReviewFix => "review-fix",
            Self::FailureFix => "failure-fix",
        }
    }
}

/// Result of an iteration check.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IterationCheckResult {
    /// Current iteration count for this agent type.
    pub iteration_count: u32,
    /// Base maximum iterations (before [CONTINUE] multipliers).
    pub max_iterations: u32,
    /// Effective maximum after applying [CONTINUE] multipliers.
    pub effective_max: u32,
    /// Number of [CONTINUE] commands found from admins.
    pub continue_count: u32,
    /// Whether the current iteration exceeds the effective max.
    pub exceeded_max: bool,
    /// Whether this run should be skipped.
    pub should_skip: bool,
    /// The agent type that was checked.
    pub agent_type: String,
}

/// GitHub comment structure (subset of fields we need).
#[derive(Debug, Deserialize)]
struct GitHubComment {
    body: Option<String>,
    user: Option<GitHubUser>,
}

#[derive(Debug, Deserialize)]
struct GitHubUser {
    login: String,
}

/// Check agent iteration count from PR comments.
pub async fn check_iteration(
    pr_number: u64,
    agent_type: AgentType,
    max_iterations: u32,
    agent_admins: &[String],
) -> Result<IterationCheckResult, Error> {
    info!(
        "Checking iteration count for PR #{}, agent type: {}",
        pr_number,
        agent_type.as_str()
    );

    let repo = std::env::var("GITHUB_REPOSITORY")
        .ok()
        .filter(|r| !r.is_empty())
        .ok_or_else(|| Error::EnvNotSet("GITHUB_REPOSITORY".to_string()))?;

    let comments = fetch_pr_comments(&repo, pr_number).await?;
    Ok(evaluate(
        &comments,
        agent_type,
        max_iterations,
        agent_admins,
    ))
}

/// Pure counting logic (separated for testing).
fn evaluate(
    comments: &[GitHubComment],
    agent_type: AgentType,
    max_iterations: u32,
    agent_admins: &[String],
) -> IterationCheckResult {
    let agent_type_str = agent_type.as_str();
    let mut iteration_count = 0u32;
    let mut continue_count = 0u32;

    for comment in comments {
        let body = comment.body.as_deref().unwrap_or("");
        let author = comment
            .user
            .as_ref()
            .map(|u| u.login.as_str())
            .unwrap_or("");

        if let Some(caps) = AGENT_MARKER_PATTERN.captures(body)
            && &caps[1] == agent_type_str
            && caps.get(3).is_none()
        {
            iteration_count += 1;
            debug!(
                "Iteration marker for {}: count now {}",
                agent_type_str, iteration_count
            );
        }

        let is_admin = agent_admins.iter().any(|a| a.eq_ignore_ascii_case(author));
        let tool_generated = is_agent_generated(body) || body.contains("<!-- agent-metadata:");
        if is_admin && !tool_generated && contains_continue_command(body) {
            continue_count += 1;
            debug!(
                "[CONTINUE] from admin {}: count now {}",
                author, continue_count
            );
        }
    }

    // Effective max: base + (continue_count * base), saturating on overflow
    let effective_max =
        max_iterations.saturating_add(continue_count.saturating_mul(max_iterations));
    let exceeded_max = iteration_count >= effective_max;

    info!(
        "Iteration check complete: count={}, effective_max={} (base={} + {}x extensions), exceeded={}",
        iteration_count, effective_max, max_iterations, continue_count, exceeded_max
    );

    IterationCheckResult {
        iteration_count,
        max_iterations,
        effective_max,
        continue_count,
        exceeded_max,
        should_skip: exceeded_max,
        agent_type: agent_type_str.to_string(),
    }
}

/// Fetch all comments from a PR (all pages).
async fn fetch_pr_comments(repo: &str, pr_number: u64) -> Result<Vec<GitHubComment>, Error> {
    let endpoint = format!("repos/{}/issues/{}/comments?per_page=100", repo, pr_number);
    let output = run_gh_command(&["api", &endpoint, "--paginate"], true)
        .await?
        .unwrap_or_default();
    let comments: Vec<GitHubComment> = parse_paginated_array(&output)?;
    debug!("Fetched {} comments from PR #{}", comments.len(), pr_number);
    Ok(comments)
}

/// Output iteration check results in GitHub Actions format.
pub fn output_github_actions(result: &IterationCheckResult) -> Result<(), Error> {
    let lines = format!(
        "iteration_count={}\neffective_max={}\ncontinue_count={}\nexceeded_max={}\nshould_skip={}\n",
        result.iteration_count,
        result.effective_max,
        result.continue_count,
        result.exceeded_max,
        result.should_skip
    );

    if let Ok(output_file) = std::env::var("GITHUB_OUTPUT")
        && !output_file.is_empty()
    {
        use std::io::Write;
        let mut file = std::fs::OpenOptions::new()
            .append(true)
            .create(true)
            .open(&output_file)?;
        file.write_all(lines.as_bytes())?;
    }

    print!("{}", lines);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn c(body: &str, login: &str) -> GitHubComment {
        GitHubComment {
            body: Some(body.to_string()),
            user: Some(GitHubUser {
                login: login.to_string(),
            }),
        }
    }

    fn admins() -> Vec<String> {
        vec!["Admin".to_string()]
    }

    #[test]
    fn test_agent_type_parse() {
        assert_eq!(AgentType::parse("review-fix"), Some(AgentType::ReviewFix));
        assert_eq!(AgentType::parse("failure-fix"), Some(AgentType::FailureFix));
        assert_eq!(AgentType::parse("REVIEW-FIX"), Some(AgentType::ReviewFix));
        assert_eq!(AgentType::parse("invalid"), None);
    }

    #[test]
    fn test_counts_only_matching_type() {
        let comments = vec![
            c("<!-- agent-metadata:type=review-fix:iteration=1 -->", "bot"),
            c(
                "<!-- agent-metadata:type=failure-fix:iteration=1 -->",
                "bot",
            ),
            c(
                "<!-- agent-metadata:type=review-fix-hallucination:iteration=1 -->",
                "bot",
            ),
            c("<!-- agent-metadata:type=review-fix:iteration=2 -->", "bot"),
        ];
        let r = evaluate(&comments, AgentType::ReviewFix, 5, &admins());
        assert_eq!(r.iteration_count, 2);
        assert!(!r.exceeded_max);
    }

    #[test]
    fn test_limit_reached_notice_not_counted() {
        let comments = vec![
            c(
                "<!-- agent-metadata:type=failure-fix:iteration=1 -->",
                "bot",
            ),
            c(
                "<!-- agent-metadata:type=failure-fix:iteration=1:limit-reached -->",
                "github-actions[bot]",
            ),
        ];
        let r = evaluate(&comments, AgentType::FailureFix, 1, &admins());
        assert_eq!(r.iteration_count, 1);
        assert!(r.exceeded_max);
    }

    #[test]
    fn test_continue_extends_limit() {
        let mut comments: Vec<GitHubComment> = (0..3)
            .map(|i| {
                c(
                    &format!("<!-- agent-metadata:type=review-fix:iteration={i} -->"),
                    "bot",
                )
            })
            .collect();
        let r = evaluate(&comments, AgentType::ReviewFix, 3, &admins());
        assert!(r.should_skip);

        comments.push(c("[CONTINUE]", "admin"));
        let r = evaluate(&comments, AgentType::ReviewFix, 3, &admins());
        assert_eq!(r.continue_count, 1);
        assert_eq!(r.effective_max, 6);
        assert!(!r.should_skip);
    }

    #[test]
    fn test_continue_requires_admin_and_directive_context() {
        let comments = vec![
            c("[CONTINUE]", "mallory"),
            // Limit notice text that merely mentions the command
            c("An agent admin can comment `[CONTINUE]` to extend", "admin"),
            c("> [CONTINUE]", "admin"),
            c(
                "[CONTINUE] <!-- agent-metadata:type=review-fix:iteration=1:limit-reached -->",
                "admin",
            ),
        ];
        let r = evaluate(&comments, AgentType::ReviewFix, 5, &admins());
        assert_eq!(r.continue_count, 0);
    }

    #[test]
    fn test_effective_max_saturates() {
        let comments: Vec<GitHubComment> = (0..3).map(|_| c("[CONTINUE]", "admin")).collect();
        let r = evaluate(&comments, AgentType::ReviewFix, u32::MAX, &admins());
        assert_eq!(r.effective_max, u32::MAX);
    }

    #[test]
    fn test_marker_pattern() {
        let caps = AGENT_MARKER_PATTERN
            .captures("<!-- agent-metadata:type=review-fix:iteration=3 -->")
            .unwrap();
        assert_eq!(&caps[1], "review-fix");
        assert_eq!(&caps[2], "3");
        assert!(caps.get(3).is_none());
    }
}
