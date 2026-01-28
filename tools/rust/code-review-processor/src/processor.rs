//! Core processing logic for code review results.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use tracing::{debug, info};

use crate::cli::Args;
use crate::git::GitOperations;
use crate::github::GitHubClient;

/// Review result from AgentCore (matches the response schema).
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
    pub async fn process(&self, review: &ReviewResult, args: &Args) -> Result<ProcessingResult> {
        // If no action flags, just return
        if !args.post_comment && !args.commit_changes && !args.create_pr {
            return Ok(ProcessingResult::NoAction);
        }

        let repository = args
            .repository
            .as_ref()
            .or(self.repository.as_ref())
            .context("Repository not specified. Use --repository or set GITHUB_REPOSITORY")?;

        // Handle based on review type
        match review {
            ReviewResult::ReviewOnly { review_markdown, .. } => {
                if args.post_comment {
                    self.post_comment(repository, review_markdown, args.pr_number)
                        .await?;
                    return Ok(ProcessingResult::ReviewPosted);
                }
                Ok(ProcessingResult::NoAction)
            }
            ReviewResult::WithFixes {
                review_markdown,
                file_changes,
                pr_title,
                pr_description,
                ..
            } => {
                // Post comment if requested
                if args.post_comment {
                    self.post_comment(repository, review_markdown, args.pr_number)
                        .await?;
                }

                // Apply changes if requested
                if args.commit_changes && !file_changes.is_empty() {
                    self.apply_changes(file_changes).await?;
                    self.git.commit(&args.commit_message).await?;
                }

                // Create PR if requested
                if args.create_pr && !file_changes.is_empty() {
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
                    let title = pr_title
                        .as_deref()
                        .unwrap_or("Code review fixes");
                    let description = pr_description
                        .as_deref()
                        .unwrap_or(review_markdown);

                    let (pr_number, pr_url) = self
                        .github
                        .create_pr(repository, title, description, &branch_name, &args.base_branch)
                        .await?;

                    return Ok(ProcessingResult::PrCreated { pr_number, pr_url });
                }

                if args.commit_changes {
                    Ok(ProcessingResult::ChangesCommitted)
                } else if args.post_comment {
                    Ok(ProcessingResult::ReviewPosted)
                } else {
                    Ok(ProcessingResult::NoAction)
                }
            }
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

    #[test]
    fn test_review_only_deserialization() {
        let json = r#"{"type": "review_only", "review_markdown": "Looks good!", "severity": "low", "findings_count": 1}"#;

        let review: ReviewResult = serde_json::from_str(json).unwrap();
        match review {
            ReviewResult::ReviewOnly { review_markdown, .. } => {
                assert!(review_markdown.contains("Looks good"));
            }
            _ => panic!("Expected ReviewOnly"),
        }
    }

    #[test]
    fn test_with_fixes_deserialization() {
        let json = r#"{"type": "with_fixes", "review_markdown": "Review", "severity": "medium", "findings_count": 2, "file_changes": [{"path": "src/main.rs", "diff": "diff content"}], "pr_title": "Fix issues", "pr_description": "This PR fixes issues"}"#;

        let review: ReviewResult = serde_json::from_str(json).unwrap();
        match review {
            ReviewResult::WithFixes { file_changes, pr_title, .. } => {
                assert_eq!(file_changes.len(), 1);
                assert_eq!(pr_title.as_deref(), Some("Fix issues"));
            }
            _ => panic!("Expected WithFixes"),
        }
    }
}
