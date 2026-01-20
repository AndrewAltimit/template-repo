//! Agent iteration tracking module.
//!
//! Tracks agent iteration counts from PR comments to prevent infinite loops.
//! Supports the `[CONTINUE]` command to extend iteration limits.

use lazy_static::lazy_static;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use tracing::{debug, info};

use crate::error::Error;
use crate::utils::run_gh_command;

lazy_static! {
    /// Pattern for agent metadata markers in comments.
    /// Format: <!-- agent-metadata:type=TYPE:iteration=N -->
    static ref AGENT_MARKER_PATTERN: Regex =
        Regex::new(r"<!-- agent-metadata:type=([a-z-]+):iteration=(\d+)").unwrap();

    /// Pattern for [CONTINUE] command (case-insensitive).
    static ref CONTINUE_PATTERN: Regex =
        Regex::new(r"(?i)\[CONTINUE\]").unwrap();
}

/// Valid agent types for iteration tracking.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AgentType {
    ReviewFix,
    FailureFix,
}

impl AgentType {
    /// Parse agent type from string.
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
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

    /// Get a human-readable name for this agent type.
    pub fn display_name(&self) -> &'static str {
        match self {
            Self::ReviewFix => "Review Response Agent",
            Self::FailureFix => "Failure Handler Agent",
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

    // Get repository from environment
    let repo = std::env::var("GITHUB_REPOSITORY")
        .map_err(|_| Error::Config("GITHUB_REPOSITORY environment variable not set".to_string()))?;

    // Fetch all PR comments
    let comments = fetch_pr_comments(&repo, pr_number).await?;

    // Build admin set (lowercase for case-insensitive comparison)
    let admin_set: HashSet<String> = agent_admins.iter().map(|a| a.to_lowercase()).collect();

    debug!("Agent admins: {:?}", admin_set);

    // Count iterations and [CONTINUE] commands
    let mut iteration_count = 0u32;
    let mut continue_count = 0u32;
    let agent_type_str = agent_type.as_str();

    for comment in &comments {
        let body = comment.body.as_deref().unwrap_or("");
        let author = comment
            .user
            .as_ref()
            .map(|u| u.login.to_lowercase())
            .unwrap_or_default();

        // Check for agent iteration marker
        if let Some(caps) = AGENT_MARKER_PATTERN.captures(body) {
            if let Some(comment_type) = caps.get(1) {
                if comment_type.as_str() == agent_type_str {
                    iteration_count += 1;
                    debug!(
                        "Found iteration marker for {}: count now {}",
                        agent_type_str, iteration_count
                    );
                }
            }
        }

        // Check for [CONTINUE] from admin
        if admin_set.contains(&author) && CONTINUE_PATTERN.is_match(body) {
            continue_count += 1;
            debug!(
                "Found [CONTINUE] from admin {}: count now {}",
                author, continue_count
            );
        }
    }

    // Calculate effective max: base + (continue_count * base)
    let effective_max = max_iterations + (continue_count * max_iterations);
    let exceeded_max = iteration_count >= effective_max;
    let should_skip = exceeded_max;

    info!(
        "Iteration check complete: count={}, effective_max={} (base={} + {}x extensions), exceeded={}",
        iteration_count, effective_max, max_iterations, continue_count, exceeded_max
    );

    Ok(IterationCheckResult {
        iteration_count,
        max_iterations,
        effective_max,
        continue_count,
        exceeded_max,
        should_skip,
        agent_type: agent_type_str.to_string(),
    })
}

/// Fetch all comments from a PR.
async fn fetch_pr_comments(repo: &str, pr_number: u64) -> Result<Vec<GitHubComment>, Error> {
    let endpoint = format!("repos/{}/issues/{}/comments", repo, pr_number);

    let output: Option<String> = run_gh_command(&["api", &endpoint, "--paginate"], true).await?;

    let json_str = output.unwrap_or_else(|| "[]".to_string());

    // Parse JSON - gh api --paginate returns concatenated JSON arrays
    // We need to handle both single array and multiple arrays
    let comments: Vec<GitHubComment> = if json_str.trim().starts_with('[') {
        // Try parsing as single array first
        match serde_json::from_str::<Vec<GitHubComment>>(&json_str) {
            Ok(c) => c,
            Err(_) => {
                // If that fails, try splitting on ][ and parsing each
                let mut all_comments = Vec::new();
                let mut depth = 0;
                let mut start = 0;

                for (i, c) in json_str.char_indices() {
                    match c {
                        '[' => depth += 1,
                        ']' => {
                            depth -= 1;
                            if depth == 0 {
                                let slice = &json_str[start..=i];
                                if let Ok(mut parsed) =
                                    serde_json::from_str::<Vec<GitHubComment>>(slice)
                                {
                                    all_comments.append(&mut parsed);
                                }
                                start = i + 1;
                            }
                        }
                        _ => {}
                    }
                }
                all_comments
            }
        }
    } else {
        Vec::new()
    };

    debug!("Fetched {} comments from PR #{}", comments.len(), pr_number);
    Ok(comments)
}

/// Output iteration check results in GitHub Actions format.
pub fn output_github_actions(result: &IterationCheckResult) {
    // Write to GITHUB_OUTPUT if available
    if let Ok(output_file) = std::env::var("GITHUB_OUTPUT") {
        if let Ok(mut file) = std::fs::OpenOptions::new().append(true).open(&output_file) {
            use std::io::Write;
            let _ = writeln!(file, "iteration_count={}", result.iteration_count);
            let _ = writeln!(file, "effective_max={}", result.effective_max);
            let _ = writeln!(file, "continue_count={}", result.continue_count);
            let _ = writeln!(file, "exceeded_max={}", result.exceeded_max);
            let _ = writeln!(file, "should_skip={}", result.should_skip);
        }
    }

    // Also print to stdout for visibility
    println!("iteration_count={}", result.iteration_count);
    println!("effective_max={}", result.effective_max);
    println!("continue_count={}", result.continue_count);
    println!("exceeded_max={}", result.exceeded_max);
    println!("should_skip={}", result.should_skip);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_agent_type_from_str() {
        assert_eq!(
            AgentType::from_str("review-fix"),
            Some(AgentType::ReviewFix)
        );
        assert_eq!(
            AgentType::from_str("failure-fix"),
            Some(AgentType::FailureFix)
        );
        assert_eq!(
            AgentType::from_str("REVIEW-FIX"),
            Some(AgentType::ReviewFix)
        );
        assert_eq!(AgentType::from_str("invalid"), None);
    }

    #[test]
    fn test_agent_marker_pattern() {
        let text = "<!-- agent-metadata:type=review-fix:iteration=3 -->";
        let caps = AGENT_MARKER_PATTERN.captures(text).unwrap();
        assert_eq!(caps.get(1).unwrap().as_str(), "review-fix");
        assert_eq!(caps.get(2).unwrap().as_str(), "3");
    }

    #[test]
    fn test_continue_pattern() {
        assert!(CONTINUE_PATTERN.is_match("[CONTINUE]"));
        assert!(CONTINUE_PATTERN.is_match("[continue]"));
        assert!(CONTINUE_PATTERN.is_match("[Continue]"));
        assert!(CONTINUE_PATTERN.is_match("Please [CONTINUE] the work"));
        assert!(!CONTINUE_PATTERN.is_match("CONTINUE"));
        assert!(!CONTINUE_PATTERN.is_match("[RESET]"));
    }
}
