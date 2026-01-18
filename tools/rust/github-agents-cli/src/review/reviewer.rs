//! Main PR reviewer orchestrator.
//!
//! Coordinates the full review workflow: fetch, prompt, review, verify, post.

use std::collections::HashSet;
use std::fs;
use std::path::Path;
use std::process::Command;

use super::agents::{self, ReviewAgent};
use super::condenser::condense_if_needed;
use super::config::PRReviewConfig;
use super::diff::{
    FileStats, PRMetadata, get_changed_files, get_current_commit_sha,
    get_files_changed_since_commit, get_pr_diff, mark_new_changes_in_diff,
};
use super::prompt::build_review_prompt;
use super::reactions::{fetch_reaction_config, fix_reaction_urls};
use super::verification::verify_claims;
use crate::error::{Error, Result};

/// State file directory for tracking reviewed commits
const STATE_DIR: &str = ".github/.pr-review-state";

/// Incremental review state
#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct ReviewState {
    last_reviewed_commit: String,
    last_review_timestamp: String,
}

/// PR Reviewer orchestrator
pub struct PRReviewer {
    config: PRReviewConfig,
    agent: Box<dyn ReviewAgent>,
    dry_run: bool,
}

impl PRReviewer {
    /// Create a new PR reviewer with the given configuration
    pub async fn new(
        config: PRReviewConfig,
        agent_override: Option<&str>,
        dry_run: bool,
    ) -> Result<Self> {
        let agent_name = agent_override.unwrap_or(&config.default_agent);

        let agent = agents::select_agent(agent_name)
            .await
            .ok_or_else(|| Error::Config(format!("Agent '{}' not available", agent_name)))?;

        tracing::info!("Using review agent: {}", agent.name());

        Ok(Self {
            config,
            agent,
            dry_run,
        })
    }

    /// Run the full review workflow for a PR
    pub async fn review_pr(&self, pr_number: u64, force_full: bool) -> Result<String> {
        tracing::info!("Starting review for PR #{}", pr_number);

        // 1. Fetch PR metadata
        let metadata = PRMetadata::from_gh_cli(pr_number)?;
        tracing::info!("PR: {} by {}", metadata.title, metadata.author);

        // 2. Check for incremental review
        let (is_incremental, last_commit) = if force_full || !self.config.incremental_enabled {
            (false, None)
        } else {
            self.check_incremental_state(pr_number)?
        };

        if is_incremental {
            tracing::info!(
                "Incremental review from commit: {}",
                last_commit.as_deref().unwrap_or("unknown")
            );
        } else {
            tracing::info!("Full review (no previous state or force_full)");
        }

        // 3. Fetch PR diff
        let full_diff = get_pr_diff(&metadata.base_branch)?;
        let changed_files = get_changed_files(&metadata.base_branch)?;

        // 4. Mark new files if incremental
        let (diff, _new_files) = if is_incremental {
            if let Some(ref commit) = last_commit {
                let new = get_files_changed_since_commit(commit)?;
                let new_set: HashSet<String> = new.into_iter().collect();
                let marked_diff = mark_new_changes_in_diff(&full_diff, &new_set);
                (marked_diff, new_set)
            } else {
                (full_diff, HashSet::new())
            }
        } else {
            (full_diff, HashSet::new())
        };

        // 5. Get file stats
        let stats = FileStats::from_git_diff(&metadata.base_branch)?;
        tracing::info!(
            "Files: {} (+{} -{})",
            stats.files_changed,
            stats.lines_added,
            stats.lines_deleted
        );

        // 6. Fetch and bucket comments
        let comment_context = if self.config.include_comment_context {
            self.fetch_bucketed_comments(pr_number)?
        } else {
            String::new()
        };

        // 7. Get previous issues if incremental
        let previous_issues = if is_incremental {
            self.get_previous_issues(pr_number).ok()
        } else {
            None
        };

        // 8. Build review prompt
        let prompt = build_review_prompt(
            &metadata,
            &stats,
            &diff,
            &comment_context,
            is_incremental,
            previous_issues.as_deref(),
        );

        tracing::debug!("Prompt length: {} chars", prompt.len());

        // 9. Call AI for review
        tracing::info!("Calling {} for review...", self.agent.name());
        let mut review = self.agent.review(&prompt).await?;
        tracing::info!(
            "Received review ({} words)",
            super::prompt::count_words(&review)
        );

        // 10. Verify claims if enabled
        if self.config.verify_claims {
            let verification = verify_claims(&review, &changed_files);
            if verification.had_invalid_claims {
                tracing::warn!(
                    "Review had {} invalid claims, using cleaned version",
                    verification.invalid_claims.len()
                );
                review = verification.cleaned;
            }
        }

        // 11. Condense if over threshold
        review = condense_if_needed(
            &review,
            self.config.max_words,
            self.config.condensation_threshold,
            self.agent.as_ref(),
        )
        .await?;

        // 12. Fix reaction URLs
        if !self.config.reaction_config_url.is_empty() {
            match fetch_reaction_config(Some(&self.config.reaction_config_url)).await {
                Ok(config) => {
                    review = fix_reaction_urls(&review, &config);
                }
                Err(e) => {
                    tracing::warn!("Failed to fetch reaction config: {}", e);
                }
            }
        }

        // 13. Post review (unless dry run)
        if self.dry_run {
            tracing::info!("Dry run - not posting review");
            println!("\n--- REVIEW PREVIEW ---\n");
            println!("{}", review);
            println!("\n--- END PREVIEW ---\n");
        } else {
            self.post_review(pr_number, &review)?;
            tracing::info!("Review posted to PR #{}", pr_number);

            // 14. Save reviewed commit state
            self.save_review_state(pr_number)?;
        }

        Ok(review)
    }

    /// Check if we have previous review state for incremental review
    fn check_incremental_state(&self, pr_number: u64) -> Result<(bool, Option<String>)> {
        let state_path = format!("{}/{}.json", STATE_DIR, pr_number);

        if !Path::new(&state_path).exists() {
            return Ok((false, None));
        }

        let content = fs::read_to_string(&state_path).map_err(|e| Error::Io(e))?;

        let state: ReviewState = serde_json::from_str(&content)
            .map_err(|e| Error::Config(format!("Invalid state: {}", e)))?;

        Ok((true, Some(state.last_reviewed_commit)))
    }

    /// Save review state after posting
    fn save_review_state(&self, pr_number: u64) -> Result<()> {
        // Create state directory if needed
        fs::create_dir_all(STATE_DIR).map_err(|e| Error::Io(e))?;

        let commit = get_current_commit_sha()?;
        let state = ReviewState {
            last_reviewed_commit: commit,
            last_review_timestamp: chrono::Utc::now().to_rfc3339(),
        };

        let state_path = format!("{}/{}.json", STATE_DIR, pr_number);
        let json = serde_json::to_string_pretty(&state)?;
        fs::write(&state_path, json).map_err(|e| Error::Io(e))?;

        tracing::debug!("Saved review state to {}", state_path);
        Ok(())
    }

    /// Fetch bucketed comments via board-manager CLI
    fn fetch_bucketed_comments(&self, pr_number: u64) -> Result<String> {
        // First, fetch comments via gh CLI
        let comments_output = Command::new("gh")
            .args([
                "api",
                &format!("repos/{{owner}}/{{repo}}/issues/{}/comments", pr_number),
                "--jq",
                ".",
            ])
            .output()
            .map_err(|e| Error::Io(e))?;

        if !comments_output.status.success() {
            tracing::warn!("Failed to fetch PR comments");
            return Ok(String::new());
        }

        let comments_json = String::from_utf8_lossy(&comments_output.stdout);

        // Pipe to board-manager bucket-comments
        let bucket_output = Command::new("board-manager")
            .args(["bucket-comments", "--filter-noise"])
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped())
            .spawn()
            .and_then(|mut child| {
                use std::io::Write;
                if let Some(ref mut stdin) = child.stdin {
                    stdin.write_all(comments_json.as_bytes())?;
                }
                child.wait_with_output()
            })
            .map_err(|e| Error::Io(e))?;

        if !bucket_output.status.success() {
            tracing::warn!("board-manager bucket-comments failed");
            return Ok(String::new());
        }

        Ok(String::from_utf8_lossy(&bucket_output.stdout).to_string())
    }

    /// Get previous issues from last review (for incremental)
    fn get_previous_issues(&self, pr_number: u64) -> Result<String> {
        // Try to fetch the last review comment from the bot
        let output = Command::new("gh")
            .args([
                "api",
                &format!("repos/{{owner}}/{{repo}}/issues/{}/comments", pr_number),
                "--jq",
                r#".[] | select(.user.type == "Bot" or .user.login == "github-actions[bot]") | .body"#,
            ])
            .output()
            .map_err(|e| Error::Io(e))?;

        if !output.status.success() {
            return Err(Error::Config(
                "Failed to fetch previous reviews".to_string(),
            ));
        }

        let body = String::from_utf8_lossy(&output.stdout);

        // Extract issues from the previous review
        // Look for lines starting with [CRITICAL], [BUG], [WARNING], [SUGGESTION]
        let mut issues = Vec::new();
        for line in body.lines() {
            let trimmed = line.trim();
            if trimmed.starts_with("- [CRITICAL]")
                || trimmed.starts_with("- [BUG]")
                || trimmed.starts_with("- [WARNING]")
                || trimmed.starts_with("- [SUGGESTION]")
            {
                issues.push(trimmed.to_string());
            }
        }

        if issues.is_empty() {
            return Err(Error::Config("No previous issues found".to_string()));
        }

        Ok(issues.join("\n"))
    }

    /// Post review comment to PR
    fn post_review(&self, pr_number: u64, review: &str) -> Result<()> {
        // Write review to temp file to avoid shell escaping issues
        let temp_path = format!("/tmp/pr-review-{}.md", pr_number);
        fs::write(&temp_path, review).map_err(|e| Error::Io(e))?;

        let output = Command::new("gh")
            .args([
                "pr",
                "comment",
                &pr_number.to_string(),
                "--body-file",
                &temp_path,
            ])
            .output()
            .map_err(|e| Error::Io(e))?;

        // Clean up temp file
        let _ = fs::remove_file(&temp_path);

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(Error::GhCommandFailed {
                exit_code: output.status.code().unwrap_or(-1),
                stdout: String::from_utf8_lossy(&output.stdout).to_string(),
                stderr: stderr.to_string(),
            });
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_state_serialization() {
        let state = ReviewState {
            last_reviewed_commit: "abc123".to_string(),
            last_review_timestamp: "2024-01-15T10:00:00Z".to_string(),
        };

        let json = serde_json::to_string(&state).unwrap();
        assert!(json.contains("abc123"));

        let parsed: ReviewState = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.last_reviewed_commit, "abc123");
    }
}
