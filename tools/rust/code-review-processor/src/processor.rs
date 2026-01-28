//! Core processing logic for code review results.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use tracing::{debug, info};

use crate::cli::Args;
use crate::git::GitOperations;
use crate::github::GitHubClient;

/// Review result from AgentCore (matches the response schema).
///
/// The schema does not use a type discriminator - we determine the variant
/// based on whether `file_changes` is present.
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ReviewResponse {
    pub review_markdown: String,
    pub severity: String,
    pub findings_count: u32,
    #[serde(default)]
    pub file_changes: Option<Vec<FileChange>>,
    #[serde(default)]
    pub pr_title: Option<String>,
    #[serde(default)]
    pub pr_description: Option<String>,
}

impl ReviewResponse {
    /// Check if this is a review-with-fixes response.
    pub fn has_fixes(&self) -> bool {
        self.file_changes
            .as_ref()
            .map(|c| !c.is_empty())
            .unwrap_or(false)
    }

    /// Get file changes, if any.
    pub fn file_changes(&self) -> &[FileChange] {
        self.file_changes.as_deref().unwrap_or(&[])
    }
}

/// Legacy enum for backwards compatibility with tagged JSON.
#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ReviewResult {
    /// Review-only result (no apply_fixes)
    ReviewOnly {
        review_markdown: String,
        severity: String,
        findings_count: u32,
    },
    /// Review with fix suggestions
    WithFixes {
        review_markdown: String,
        severity: String,
        findings_count: u32,
        file_changes: Vec<FileChange>,
        #[serde(default)]
        pr_title: Option<String>,
        #[serde(default)]
        pr_description: Option<String>,
    },
}

impl From<ReviewResult> for ReviewResponse {
    fn from(result: ReviewResult) -> Self {
        match result {
            ReviewResult::ReviewOnly {
                review_markdown,
                severity,
                findings_count,
            } => ReviewResponse {
                review_markdown,
                severity,
                findings_count,
                file_changes: None,
                pr_title: None,
                pr_description: None,
            },
            ReviewResult::WithFixes {
                review_markdown,
                severity,
                findings_count,
                file_changes,
                pr_title,
                pr_description,
            } => ReviewResponse {
                review_markdown,
                severity,
                findings_count,
                file_changes: Some(file_changes),
                pr_title,
                pr_description,
            },
        }
    }
}

/// Try to parse JSON as either the new schema format or legacy tagged format.
pub fn parse_review_json(json: &str) -> Result<ReviewResponse> {
    // First try the new untagged format (what the agent actually produces)
    if let Ok(response) = serde_json::from_str::<ReviewResponse>(json) {
        return Ok(response);
    }

    // Fall back to tagged format for backwards compatibility
    let result: ReviewResult =
        serde_json::from_str(json).context("Failed to parse review JSON")?;
    Ok(result.into())
}

/// A file change with diff.
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct FileChange {
    pub path: String,
    pub diff: String,
    #[serde(default)]
    pub original_sha: Option<String>,
}

/// Result of processing.
#[derive(Debug)]
pub enum ProcessingResult {
    /// Review was posted as a comment
    ReviewPosted,
    /// Changes were committed
    ChangesCommitted,
    /// PR was created
    PrCreated { pr_number: u64, pr_url: String },
    /// No action was taken
    NoAction,
}

/// Processes code review results.
pub struct ReviewProcessor {
    repository: Option<String>,
    dry_run: bool,
    git: GitOperations,
    github: GitHubClient,
}

impl ReviewProcessor {
    /// Create a new processor.
    pub fn new(repository: Option<String>, dry_run: bool) -> Self {
        Self {
            repository,
            dry_run,
            git: GitOperations::new(dry_run),
            github: GitHubClient::new(dry_run),
        }
    }

    /// Process the review result based on CLI flags.
    pub async fn process(&self, review: &ReviewResponse, args: &Args) -> Result<ProcessingResult> {
        // If no action flags, just return
        if !args.post_comment && !args.commit_changes && !args.create_pr {
            return Ok(ProcessingResult::NoAction);
        }

        let repository = args
            .repository
            .as_ref()
            .or(self.repository.as_ref())
            .context("Repository not specified. Use --repository or set GITHUB_REPOSITORY")?;

        // Post comment if requested
        if args.post_comment {
            self.post_comment(repository, &review.review_markdown, args.pr_number)
                .await?;
        }

        let file_changes = review.file_changes();
        let has_changes = review.has_fixes();

        // Apply changes if requested and there are changes
        if args.commit_changes && has_changes {
            self.apply_changes(file_changes).await?;
            self.git.commit(&args.commit_message).await?;
        }

        // Create PR if requested and there are changes
        if args.create_pr && has_changes {
            // Create a new branch if not specified
            let branch_name = args.branch.clone().unwrap_or_else(|| {
                format!("code-review-fixes-{}", chrono::Utc::now().timestamp())
            });

            // Create and push branch
            self.git.create_branch(&branch_name).await?;

            // Apply changes if not already done
            if !args.commit_changes {
                self.apply_changes(file_changes).await?;
                self.git.commit(&args.commit_message).await?;
            }

            self.git.push(&branch_name).await?;

            // Create PR
            let title = review.pr_title.as_deref().unwrap_or("Code review fixes");
            let description = review
                .pr_description
                .as_deref()
                .unwrap_or(&review.review_markdown);

            let (pr_number, pr_url) = self
                .github
                .create_pr(repository, title, description, &branch_name, &args.base_branch)
                .await?;

            return Ok(ProcessingResult::PrCreated { pr_number, pr_url });
        }

        if args.commit_changes && has_changes {
            Ok(ProcessingResult::ChangesCommitted)
        } else if args.post_comment {
            Ok(ProcessingResult::ReviewPosted)
        } else {
            Ok(ProcessingResult::NoAction)
        }
    }

    /// Post a comment on a PR.
    async fn post_comment(
        &self,
        repository: &str,
        markdown: &str,
        pr_number: Option<u64>,
    ) -> Result<()> {
        let pr = pr_number.context("PR number required for --post-comment")?;

        if self.dry_run {
            info!("[DRY RUN] Would post comment to {repository} PR #{pr}");
            debug!("Comment content:\n{markdown}");
            return Ok(());
        }

        self.github.post_pr_comment(repository, pr, markdown).await
    }

    /// Apply file changes from diffs.
    async fn apply_changes(&self, changes: &[FileChange]) -> Result<()> {
        for change in changes {
            if self.dry_run {
                info!("[DRY RUN] Would apply diff to {}", change.path);
                debug!("Diff:\n{}", change.diff);
                continue;
            }

            // Apply the diff using patch
            self.git.apply_diff(&change.path, &change.diff).await?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Test the new untagged schema format (what the agent produces)
    #[test]
    fn test_review_only_schema_format() {
        // Use serde_json to build the test data properly
        let json_value = serde_json::json!({
            "review_markdown": "Code Review - Looks good!",
            "severity": "low",
            "findings_count": 1
        });
        let json = serde_json::to_string(&json_value).unwrap();

        let review = parse_review_json(&json).unwrap();
        assert!(review.review_markdown.contains("Looks good"));
        assert_eq!(review.severity, "low");
        assert_eq!(review.findings_count, 1);
        assert!(!review.has_fixes());
    }

    #[test]
    fn test_review_with_fixes_schema_format() {
        let json_value = serde_json::json!({
            "review_markdown": "Security Issue Found",
            "severity": "critical",
            "findings_count": 1,
            "file_changes": [{
                "path": "src/db.rs",
                "diff": "--- a/src/db.rs\n+++ b/src/db.rs"
            }],
            "pr_title": "fix(security): patch vulnerability",
            "pr_description": "This PR fixes the security issue."
        });
        let json = serde_json::to_string(&json_value).unwrap();

        let review = parse_review_json(&json).unwrap();
        assert!(review.has_fixes());
        assert_eq!(review.file_changes().len(), 1);
        assert_eq!(review.file_changes()[0].path, "src/db.rs");
        assert_eq!(
            review.pr_title.as_deref(),
            Some("fix(security): patch vulnerability")
        );
    }

    #[test]
    fn test_review_with_empty_file_changes() {
        let json_value = serde_json::json!({
            "review_markdown": "No issues found",
            "severity": "info",
            "findings_count": 0,
            "file_changes": []
        });
        let json = serde_json::to_string(&json_value).unwrap();

        let review = parse_review_json(&json).unwrap();
        assert!(!review.has_fixes()); // Empty array means no fixes
        assert!(review.file_changes().is_empty());
    }

    #[test]
    fn test_file_change_with_original_sha() {
        let json_value = serde_json::json!({
            "review_markdown": "Review",
            "severity": "medium",
            "findings_count": 1,
            "file_changes": [{
                "path": "src/main.rs",
                "diff": "diff content",
                "original_sha": "abc123def456"
            }]
        });
        let json = serde_json::to_string(&json_value).unwrap();

        let review = parse_review_json(&json).unwrap();
        assert_eq!(
            review.file_changes()[0].original_sha.as_deref(),
            Some("abc123def456")
        );
    }

    // Test legacy tagged format (backwards compatibility)
    #[test]
    fn test_legacy_review_only_format() {
        let json_value = serde_json::json!({
            "type": "review_only",
            "review_markdown": "Looks good!",
            "severity": "low",
            "findings_count": 1
        });
        let json = serde_json::to_string(&json_value).unwrap();

        let review = parse_review_json(&json).unwrap();
        assert!(review.review_markdown.contains("Looks good"));
        assert!(!review.has_fixes());
    }

    #[test]
    fn test_legacy_with_fixes_format() {
        let json_value = serde_json::json!({
            "type": "with_fixes",
            "review_markdown": "Review",
            "severity": "medium",
            "findings_count": 2,
            "file_changes": [{"path": "src/main.rs", "diff": "diff content"}],
            "pr_title": "Fix issues",
            "pr_description": "This PR fixes issues"
        });
        let json = serde_json::to_string(&json_value).unwrap();

        let review = parse_review_json(&json).unwrap();
        assert!(review.has_fixes());
        assert_eq!(review.file_changes().len(), 1);
        assert_eq!(review.pr_title.as_deref(), Some("Fix issues"));
    }

    #[test]
    fn test_realistic_agent_response() {
        // A realistic response an agent might produce
        let json_value = serde_json::json!({
            "review_markdown": "## Code Review\n\n### Critical Issues\n\n1. SQL injection in query_user",
            "severity": "critical",
            "findings_count": 1,
            "file_changes": [{
                "path": "src/db.rs",
                "diff": "--- a/src/db.rs\n+++ b/src/db.rs\n@@ -1 +1 @@\n-bad\n+good"
            }],
            "pr_title": "fix(security): prevent SQL injection",
            "pr_description": "Fixes SQL injection vulnerability."
        });
        let json = serde_json::to_string(&json_value).unwrap();

        let review = parse_review_json(&json).unwrap();
        assert_eq!(review.severity, "critical");
        assert_eq!(review.findings_count, 1);
        assert!(review.has_fixes());
        assert!(review.review_markdown.contains("SQL injection"));
    }

    #[test]
    fn test_invalid_json_fails() {
        let json = "{ invalid json }";
        assert!(parse_review_json(json).is_err());
    }

    #[test]
    fn test_all_severity_levels() {
        for severity in &["critical", "high", "medium", "low", "info"] {
            let json_value = serde_json::json!({
                "review_markdown": "Test",
                "severity": severity,
                "findings_count": 0
            });
            let json = serde_json::to_string(&json_value).unwrap();
            let review = parse_review_json(&json).unwrap();
            assert_eq!(review.severity, *severity);
        }
    }

    #[test]
    fn test_processor_dry_run() {
        let processor = ReviewProcessor::new(Some("owner/repo".to_string()), true);
        assert!(processor.dry_run);
    }

    #[test]
    fn test_multiline_markdown_in_json() {
        // Test that newlines in JSON are preserved
        let json_value = serde_json::json!({
            "review_markdown": "Line 1\nLine 2\n\n## Header",
            "severity": "low",
            "findings_count": 0
        });
        let json = serde_json::to_string(&json_value).unwrap();

        let review = parse_review_json(&json).unwrap();
        // The newlines should be actual newlines in the parsed string
        assert!(review.review_markdown.contains('\n'));
        assert!(review.review_markdown.contains("Header"));
    }

    #[test]
    fn test_diff_with_special_characters() {
        // Test that diffs with special characters parse correctly
        let json_value = serde_json::json!({
            "review_markdown": "Review",
            "severity": "medium",
            "findings_count": 1,
            "file_changes": [{
                "path": "test.rs",
                "diff": "--- a/test.rs\n+++ b/test.rs\n@@ -1,3 +1,3 @@\n-let x = \"hello\";\n+let x = \"world\";"
            }]
        });
        let json = serde_json::to_string(&json_value).unwrap();

        let review = parse_review_json(&json).unwrap();
        assert!(review.has_fixes());
        let diff = &review.file_changes()[0].diff;
        assert!(diff.contains("hello"));
        assert!(diff.contains("world"));
    }
}
