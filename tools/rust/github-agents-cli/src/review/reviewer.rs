//! Main PR reviewer orchestrator.
//!
//! Coordinates the full review workflow: fetch, prompt, review, verify, post.

use std::collections::HashSet;
use std::fs;
use std::path::Path;
use std::process::Command;

use super::agents::{self, ReviewAgent};
use super::condenser::condense_if_needed;
use super::config::{FullConfig, PRReviewConfig};
use super::diff::{
    FileStats, PRMetadata, get_changed_files, get_current_commit_sha,
    get_files_changed_since_commit, get_pr_diff, mark_new_changes_in_diff,
};
use super::editor::edit_review;
use super::prompt::build_review_prompt;
use super::reactions::{fetch_reaction_config, fix_reaction_urls};
use super::verification::verify_claims;
use crate::error::{Error, Result};

use std::io::Write;
use std::process::Stdio;

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
    editor_agent: Option<Box<dyn ReviewAgent>>,
    dry_run: bool,
}

impl PRReviewer {
    /// Create a new PR reviewer with the given configuration
    pub async fn new(
        config: PRReviewConfig,
        agent_override: Option<&str>,
        dry_run: bool,
    ) -> Result<Self> {
        // Load full config to get model overrides
        let full_config = FullConfig::load(None).ok();
        let agent_name = agent_override.unwrap_or(&config.default_agent);

        // Only apply model overrides for Gemini (other agents use their own defaults)
        let (review_model, condenser_model) = if agent_name.eq_ignore_ascii_case("gemini") {
            if let Some(ref fc) = full_config {
                (
                    Some(fc.gemini_review_model()),
                    Some(fc.gemini_condenser_model()),
                )
            } else {
                (None, None)
            }
        } else {
            (None, None)
        };

        let agent = agents::select_agent_with_models(agent_name, review_model, condenser_model)
            .await
            .ok_or_else(|| Error::Config(format!("Agent '{}' not available", agent_name)))?;

        tracing::info!("Using review agent: {}", agent.name());

        // Create editor agent if enabled
        let editor_agent = if config.editor_enabled {
            let editor_name = &config.editor_agent;
            tracing::info!("Editor pass enabled, using: {}", editor_name);
            agents::select_agent(editor_name).await
        } else {
            None
        };

        Ok(Self {
            config,
            agent,
            editor_agent,
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
        let mut filtered_claims_count = 0;
        if self.config.verify_claims {
            let verification = verify_claims(&review, &changed_files);
            if verification.had_invalid_claims {
                filtered_claims_count = verification.invalid_claims.len();
                tracing::warn!(
                    "Review had {} invalid claims, using cleaned version",
                    filtered_claims_count
                );
                review = verification.cleaned;
            }
        }

        // 11. Condense if over threshold (with fallback on failure)
        match condense_if_needed(
            &review,
            self.config.max_words,
            self.config.condensation_threshold,
            self.agent.as_ref(),
        )
        .await
        {
            Ok(condensed) => review = condensed,
            Err(e) => {
                tracing::warn!("Condensation failed, using original review: {}", e);
                // Continue with original review rather than aborting
            },
        }

        // 11.5. Editor pass to clean up formatting (if enabled)
        if let Some(ref editor) = self.editor_agent {
            tracing::info!("Running editor pass with {}...", editor.name());
            match edit_review(&review, editor.as_ref()).await {
                Ok(edited) => {
                    let old_words = super::prompt::count_words(&review);
                    let new_words = super::prompt::count_words(&edited);
                    tracing::info!(
                        "Editor pass complete ({} -> {} words)",
                        old_words,
                        new_words
                    );
                    review = edited;
                },
                Err(e) => {
                    tracing::warn!("Editor pass failed, using original review: {}", e);
                    // Continue with unedited review
                },
            }
        }

        // 12. Fix reaction URLs
        if !self.config.reaction_config_url.is_empty() {
            match fetch_reaction_config(Some(&self.config.reaction_config_url)).await {
                Ok(config) => {
                    review = fix_reaction_urls(&review, &config);
                },
                Err(e) => {
                    tracing::warn!("Failed to fetch reaction config: {}", e);
                },
            }
        }

        // 12.5. Validate review is not empty (catches blank agent responses)
        if review.trim().is_empty() {
            return Err(Error::Config(
                "Agent returned empty or whitespace-only review, skipping post".to_string(),
            ));
        }

        // 13. Get current commit SHA for tracking
        let commit_sha = get_current_commit_sha().unwrap_or_default();

        // 14. Post review (unless dry run)
        if self.dry_run {
            tracing::info!("Dry run - not posting review");
            println!("\n--- REVIEW PREVIEW ---\n");
            println!(
                "{}",
                self.format_github_comment(
                    &review,
                    &commit_sha,
                    is_incremental,
                    filtered_claims_count
                )
            );
            println!("\n--- END PREVIEW ---\n");
        } else {
            self.post_review(
                pr_number,
                &review,
                &commit_sha,
                is_incremental,
                filtered_claims_count,
            )?;
            tracing::info!("Review posted to PR #{}", pr_number);

            // 15. Save reviewed commit state
            self.save_review_state(pr_number)?;
        }

        Ok(review)
    }

    /// Check if we have previous review state for incremental review
    fn check_incremental_state(&self, pr_number: u64) -> Result<(bool, Option<String>)> {
        // First, try local state file
        let state_path = format!("{}/{}.json", STATE_DIR, pr_number);

        if Path::new(&state_path).exists() {
            if let Ok(content) = fs::read_to_string(&state_path) {
                if let Ok(state) = serde_json::from_str::<ReviewState>(&content) {
                    return Ok((true, Some(state.last_reviewed_commit)));
                }
            }
        }

        // Fallback: Look for commit marker in PR comments
        // This handles cases where state file is missing but we have previous reviews
        if let Some(commit) = self.find_last_reviewed_commit_from_comments(pr_number) {
            return Ok((true, Some(commit)));
        }

        Ok((false, None))
    }

    /// Find the last reviewed commit from PR comment markers
    fn find_last_reviewed_commit_from_comments(&self, pr_number: u64) -> Option<String> {
        let agent_name = self.agent.name();

        // Fetch PR comments
        let output = Command::new("gh")
            .args(["pr", "view", &pr_number.to_string(), "--json", "comments"])
            .output()
            .ok()?;

        if !output.status.success() {
            return None;
        }

        let comments: serde_json::Value = serde_json::from_slice(&output.stdout).ok()?;
        let comments_array = comments.get("comments")?.as_array()?;

        // Look for the most recent review with commit marker (search in reverse order)
        let marker_pattern = format!("<!-- {}-review-marker:commit:", agent_name);

        for comment in comments_array.iter().rev() {
            let body = comment.get("body")?.as_str()?;
            if let Some(start) = body.find(&marker_pattern) {
                let after_prefix = &body[start + marker_pattern.len()..];
                if let Some(end) = after_prefix.find(" -->") {
                    let commit = &after_prefix[..end];
                    // Validate it looks like a commit SHA (hex chars)
                    if commit.chars().all(|c| c.is_ascii_hexdigit()) && !commit.is_empty() {
                        return Some(commit.to_string());
                    }
                }
            }
        }

        None
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
        // Try multiple paths: local build, CI artifact location, or PATH
        let board_manager_paths = [
            "./tools/rust/board-manager/target/release/board-manager",
            "tools/rust/board-manager/target/release/board-manager",
            "board-manager",
        ];

        let board_manager = board_manager_paths
            .iter()
            .find(|p| Path::new(p).exists())
            .unwrap_or(&"board-manager");

        let bucket_output = Command::new(board_manager)
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

    /// Summarize comment chain using Claude Code to identify false positives and overrides
    ///
    /// This provides context to other review agents about what issues have been
    /// already addressed, identified as false positives, or explicitly overridden.
    fn summarize_comment_chain(&self, pr_number: u64) -> Result<String> {
        // Check if Claude CLI is available
        let claude_path = find_claude_binary();
        if claude_path.is_none() {
            tracing::info!("Claude CLI not available, skipping comment chain summary");
            return Ok(String::new());
        }
        let claude_path = claude_path.unwrap();

        // Fetch all PR comments
        let comments_output = Command::new("gh")
            .args([
                "pr",
                "view",
                &pr_number.to_string(),
                "--json",
                "comments",
                "--jq",
                ".comments[].body",
            ])
            .output()
            .map_err(|e| Error::Io(e))?;

        if !comments_output.status.success() || comments_output.stdout.is_empty() {
            tracing::info!("No comments to summarize");
            return Ok(String::new());
        }

        let comments = String::from_utf8_lossy(&comments_output.stdout);
        if comments.trim().is_empty() {
            return Ok(String::new());
        }

        tracing::info!("Summarizing comment chain with Claude Code...");

        let prompt = format!(
            r#"Analyze these PR comments and extract a BRIEF summary for AI code reviewers.

Focus ONLY on:
1. **False Positives**: Issues flagged by reviewers that were later determined to be incorrect
2. **Overrides/Skip**: Explicit requests from maintainers to ignore certain issues
3. **Resolved Issues**: Issues that have been explicitly marked as fixed

Output format (be concise):
```
FALSE POSITIVES:
- [Brief description of false positive and why]

SKIP/OVERRIDE:
- [What to skip and why, per maintainer]

RESOLVED:
- [Issues confirmed fixed]
```

If none found in a category, write "None identified."

Comments to analyze:
---
{}
---"#,
            comments
        );

        // Call Claude Code CLI
        let mut child = Command::new(&claude_path)
            .arg("--print")
            .arg("--dangerously-skip-permissions")
            .arg("--model")
            .arg("haiku") // Use haiku for speed - this is just summarization
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| Error::Config(format!("Failed to spawn Claude CLI: {}", e)))?;

        // Write prompt to stdin
        if let Some(ref mut stdin) = child.stdin {
            stdin
                .write_all(prompt.as_bytes())
                .map_err(|e| Error::Config(format!("Failed to write to Claude stdin: {}", e)))?;
        }
        drop(child.stdin.take());

        // Wait with timeout (2 minutes for summarization)
        let output = child
            .wait_with_output()
            .map_err(|e| Error::Config(format!("Claude CLI failed: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            tracing::warn!("Claude summarization failed: {}", stderr);
            return Ok(String::new());
        }

        let summary = String::from_utf8_lossy(&output.stdout).to_string();
        tracing::info!("Comment chain summary generated ({} chars)", summary.len());

        Ok(summary)
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

    /// Format the review as a GitHub comment with metadata
    fn format_github_comment(
        &self,
        review: &str,
        commit_sha: &str,
        is_incremental: bool,
        filtered_claims: usize,
    ) -> String {
        let agent_name = self.agent.name();
        let model_name = self.agent.model();

        // Include commit SHA in marker for incremental tracking
        let marker = if commit_sha.is_empty() {
            format!("<!-- {}-review-marker -->", agent_name)
        } else {
            format!(
                "<!-- {}-review-marker:commit:{} -->",
                agent_name, commit_sha
            )
        };

        let review_type = if is_incremental {
            "Incremental Review"
        } else {
            "Code Review"
        };

        let incremental_note = if is_incremental {
            "\n*This is an incremental review focusing on changes since the last review.*\n"
        } else {
            ""
        };

        // Capitalize first letter of agent name for display
        let agent_display = {
            let mut chars = agent_name.chars();
            match chars.next() {
                None => String::new(),
                Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
            }
        };

        // Add note about filtered claims if any
        let filtered_note = if filtered_claims > 0 {
            format!(
                "\n- {} claim(s) were automatically filtered as potential hallucinations (file:line content didn't match claims)",
                filtered_claims
            )
        } else {
            String::new()
        };

        // Inject filtered note into the Notes section if present, otherwise append before reaction
        let review_with_note = if filtered_claims > 0 && review.contains("## Notes") {
            // Find the Notes section and inject the filtered note after the header
            if let Some(notes_pos) = review.find("## Notes") {
                let after_notes = &review[notes_pos..];
                if let Some(newline_pos) = after_notes.find('\n') {
                    let insert_pos = notes_pos + newline_pos + 1;
                    format!(
                        "{}{}\n{}",
                        &review[..insert_pos],
                        filtered_note.trim_start_matches('\n'),
                        &review[insert_pos..]
                    )
                } else {
                    format!("{}{}", review, filtered_note)
                }
            } else {
                format!("{}{}", review, filtered_note)
            }
        } else if filtered_claims > 0 {
            // No Notes section, append the note before the reaction image if present
            if let Some(reaction_pos) = review.find("![") {
                format!(
                    "{}\n## Notes\n{}\n\n{}",
                    review[..reaction_pos].trim_end(),
                    filtered_note.trim_start_matches('\n'),
                    &review[reaction_pos..]
                )
            } else {
                format!("{}{}", review, filtered_note)
            }
        } else {
            review.to_string()
        };

        format!(
            "## {} AI {}\n{}\n{}\n{}\n\n---\n*Generated by {} AI ({}). Supplementary to human reviews.*\n",
            agent_display,
            review_type,
            marker,
            incremental_note,
            review_with_note,
            agent_display,
            model_name
        )
    }

    /// Post review comment to PR
    fn post_review(
        &self,
        pr_number: u64,
        review: &str,
        commit_sha: &str,
        is_incremental: bool,
        filtered_claims: usize,
    ) -> Result<()> {
        // Format review with metadata marker
        let formatted =
            self.format_github_comment(review, commit_sha, is_incremental, filtered_claims);

        // Write review to temp file to avoid shell escaping issues
        let temp_path = format!("/tmp/pr-review-{}.md", pr_number);
        fs::write(&temp_path, &formatted).map_err(|e| Error::Io(e))?;

        let mut args = vec![
            "pr".to_string(),
            "comment".to_string(),
            pr_number.to_string(),
            "--body-file".to_string(),
            temp_path.clone(),
            // Strip invalid reaction images instead of failing the entire review
            "--gh-validator-strip-invalid-images".to_string(),
        ];

        // Explicitly specify repo to avoid issues on self-hosted runners
        // where gh may not detect the repo from git remotes
        if let Ok(repo) = std::env::var("GITHUB_REPOSITORY") {
            args.push("--repo".to_string());
            args.push(repo);
        }

        let output = Command::new("gh")
            .args(&args)
            .output()
            .map_err(|e| Error::Io(e))?;

        // Clean up temp file
        let _ = fs::remove_file(&temp_path);

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            tracing::error!("gh pr comment failed - stderr: {}", stderr.trim());
            if !stdout.trim().is_empty() {
                tracing::error!("gh pr comment failed - stdout: {}", stdout.trim());
            }
            return Err(Error::GhCommandFailed {
                exit_code: output.status.code().unwrap_or(-1),
                stdout,
                stderr,
            });
        }

        Ok(())
    }
}

/// Find the claude binary by trying to execute it directly
/// (avoids `which` command which may not be available in Docker)
fn find_claude_binary() -> Option<String> {
    let candidates = ["claude", "/usr/local/bin/claude", "/usr/bin/claude"];

    // Also check NVM paths
    let home = std::env::var("HOME").unwrap_or_default();
    let nvm_paths = [
        format!("{}/.nvm/versions/node/v22.16.0/bin/claude", home),
        format!("{}/.nvm/versions/node/v20.18.0/bin/claude", home),
    ];

    // Try each candidate by executing --version
    for candidate in candidates.iter().chain(
        nvm_paths
            .iter()
            .map(|s| s.as_str())
            .collect::<Vec<_>>()
            .iter(),
    ) {
        if let Ok(output) = Command::new(candidate).arg("--version").output() {
            if output.status.success() {
                return Some(candidate.to_string());
            }
        }
    }

    None
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
