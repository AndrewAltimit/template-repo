//! Main PR reviewer orchestrator.
//!
//! Coordinates the full review workflow: fetch, prompt, review, verify, post.

use std::collections::HashSet;
use std::fs;
use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};

use super::agents::{self, ReviewAgent};
use super::condenser::condense_if_needed;
use super::config::{FullConfig, PRReviewConfig, ReviewProfile};
use super::diff::{
    FileStats, PRMetadata, get_changed_files, get_current_commit_sha,
    get_files_changed_since_commit, get_pr_diff, mark_new_changes_in_diff,
};
use super::editor::edit_review;
use super::prompt::{build_review_prompt, count_words};
use super::reactions::{fetch_reaction_config, fix_reaction_urls};
use super::sanitize::{is_sanitizable_failure, strip_emojis};
use super::verification::verify_claims;
use crate::error::{Error, Result};
use crate::security::commit::is_valid_sha;
use crate::security::trigger::is_bot_login;
use crate::security::{AGENT_COMMENT_MARKER, neutralize_triggers};
use crate::utils::parse_paginated_array;
use crate::utils::text::capitalize;

/// State file directory for tracking reviewed commits
const STATE_DIR: &str = ".github/.pr-review-state";

/// Incremental review state
#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct ReviewState {
    last_reviewed_commit: String,
    last_review_timestamp: String,
}

/// Everything gathered from git/GitHub before prompting the agent.
struct ReviewInputs {
    diff: String,
    changed_files: Vec<String>,
    stats: FileStats,
    comment_context: String,
    previous_issues: Option<String>,
    is_incremental: bool,
}

/// PR Reviewer orchestrator
pub struct PRReviewer {
    config: PRReviewConfig,
    /// Lowercased logins (admins + trusted sources) whose markers we honor
    trusted_logins: Vec<String>,
    agent: Box<dyn ReviewAgent>,
    editor_agent: Option<Box<dyn ReviewAgent>>,
    dry_run: bool,
    /// Optional review profile with focused instructions
    profile: Option<ReviewProfile>,
}

impl PRReviewer {
    /// Create a new PR reviewer with an optional review profile.
    ///
    /// Model precedence: profile model > agent default.
    pub async fn new_with_profile(
        config: PRReviewConfig,
        agent_override: Option<&str>,
        dry_run: bool,
        profile: Option<ReviewProfile>,
    ) -> Result<Self> {
        let agent_name = agent_override.unwrap_or(&config.default_agent).to_string();
        let model = profile.as_ref().and_then(|p| p.model.clone());
        let agent = agents::select_agent_with_model(&agent_name, model).await?;
        tracing::info!("Using review agent: {} ({})", agent.name(), agent.model());

        let editor_agent = if config.editor_enabled {
            tracing::info!("Editor pass enabled, using: {}", config.editor_agent);
            match agents::select_agent(&config.editor_agent).await {
                Ok(a) => Some(a),
                Err(e) => {
                    tracing::warn!("Editor agent unavailable, skipping editor pass: {}", e);
                    None
                },
            }
        } else {
            None
        };

        let trusted_logins = FullConfig::load_or_default()
            .map(|c| c.trusted_logins())
            .unwrap_or_default();

        Ok(Self {
            config,
            trusted_logins,
            agent,
            editor_agent,
            dry_run,
            profile,
        })
    }

    /// Run the full review workflow for a PR
    pub async fn review_pr(&self, pr_number: u64, force_full: bool) -> Result<String> {
        tracing::info!("Starting review for PR #{}", pr_number);

        let metadata = PRMetadata::from_gh_cli(pr_number)?;
        tracing::info!("PR: {} by {}", metadata.title, metadata.author);

        let inputs = self.gather_inputs(pr_number, &metadata, force_full)?;
        let prompt = self.build_prompt(&metadata, &inputs);
        tracing::debug!("Prompt length: {} chars", prompt.len());

        let (review, filtered_claims) =
            self.generate_review(&prompt, &inputs.changed_files).await?;

        let commit_sha = get_current_commit_sha().unwrap_or_default();
        let comment = self.format_github_comment(
            &review,
            &commit_sha,
            inputs.is_incremental,
            filtered_claims,
        );

        if self.dry_run {
            tracing::info!("Dry run - not posting review");
            println!("\n--- REVIEW PREVIEW ---\n");
            println!("{}", comment);
            println!("\n--- END PREVIEW ---\n");
        } else {
            self.post_review(pr_number, &comment)?;
            tracing::info!("Review posted to PR #{}", pr_number);
            if let Err(e) = self.save_review_state(pr_number, &commit_sha) {
                tracing::warn!("Failed to save review state: {}", e);
            }
        }

        Ok(review)
    }

    /// Collect diff, stats, comment context and incremental state.
    fn gather_inputs(
        &self,
        pr_number: u64,
        metadata: &PRMetadata,
        force_full: bool,
    ) -> Result<ReviewInputs> {
        let last_commit = if force_full || !self.config.incremental_enabled {
            None
        } else {
            self.find_incremental_base(pr_number)
        };
        let is_incremental = last_commit.is_some();
        match &last_commit {
            Some(c) => tracing::info!("Incremental review from commit: {}", c),
            None => tracing::info!("Full review (no previous state or force_full)"),
        }

        let full_diff = get_pr_diff(&metadata.base_branch)?;
        let changed_files = get_changed_files(&metadata.base_branch)?;

        let diff = match &last_commit {
            Some(commit) => {
                let new: HashSet<String> = get_files_changed_since_commit(commit)?
                    .into_iter()
                    .collect();
                mark_new_changes_in_diff(&full_diff, &new)
            },
            None => full_diff,
        };

        let stats = FileStats::from_git_diff(&metadata.base_branch)?;
        tracing::info!(
            "Files: {} (+{} -{})",
            stats.files_changed,
            stats.lines_added,
            stats.lines_deleted
        );

        let comment_context = if self.config.include_comment_context {
            fetch_bucketed_comments(pr_number)
        } else {
            String::new()
        };

        let previous_issues = if is_incremental {
            get_previous_issues(pr_number)
        } else {
            None
        };

        Ok(ReviewInputs {
            diff,
            changed_files,
            stats,
            comment_context,
            previous_issues,
            is_incremental,
        })
    }

    fn build_prompt(&self, metadata: &PRMetadata, inputs: &ReviewInputs) -> String {
        let prompt = build_review_prompt(
            metadata,
            &inputs.stats,
            &inputs.diff,
            &inputs.comment_context,
            inputs.is_incremental,
            inputs.previous_issues.as_deref(),
        );
        match &self.profile {
            Some(profile) => {
                tracing::info!("Applying review profile: {}", profile.display_name);
                format!(
                    "## Review Profile: {}\n\n**Focus:** {}\n\n{}\n\n---\n\n{}",
                    profile.display_name, profile.focus, profile.instructions, prompt
                )
            },
            None => prompt,
        }
    }

    /// Call the agent, then verify, condense, edit and post-process the review.
    ///
    /// Returns the final review text and the number of filtered claims.
    async fn generate_review(
        &self,
        prompt: &str,
        changed_files: &[String],
    ) -> Result<(String, usize)> {
        tracing::info!("Calling {} for review...", self.agent.name());
        let mut review = self.agent.review(prompt).await?;
        tracing::info!("Received review ({} words)", count_words(&review));

        let mut filtered_claims = 0;
        if self.config.verify_claims {
            let verification = verify_claims(&review, changed_files);
            if verification.had_invalid_claims {
                filtered_claims = verification.invalid_claims.len();
                tracing::warn!(
                    "Review had {} invalid claims, using cleaned version",
                    filtered_claims
                );
                review = verification.cleaned;
            }
        }

        match condense_if_needed(
            &review,
            self.config.max_words,
            self.config.condensation_threshold,
            self.agent.as_ref(),
        )
        .await
        {
            Ok(condensed) => review = condensed,
            Err(e) => tracing::warn!("Condensation failed, using original review: {}", e),
        }

        if let Some(editor) = &self.editor_agent {
            tracing::info!("Running editor pass with {}...", editor.name());
            match edit_review(&review, editor.as_ref()).await {
                Ok(edited) => {
                    tracing::info!(
                        "Editor pass complete ({} -> {} words)",
                        count_words(&review),
                        count_words(&edited)
                    );
                    review = edited;
                },
                Err(e) => tracing::warn!("Editor pass failed, using original review: {}", e),
            }
        }

        if !self.config.reaction_config_url.is_empty() {
            match fetch_reaction_config(Some(&self.config.reaction_config_url)).await {
                Ok(config) => review = fix_reaction_urls(&review, &config),
                Err(e) => tracing::warn!("Failed to fetch reaction config: {}", e),
            }
        }

        if review.trim().is_empty() {
            return Err(Error::Config(
                "Agent returned empty or whitespace-only review, skipping post".to_string(),
            ));
        }

        // Model output must never carry live trigger/command keywords
        Ok((neutralize_triggers(&review), filtered_claims))
    }

    /// Determine the commit the previous review covered, if it can be trusted.
    ///
    /// Sources, in order:
    /// 1. A local state file that is *not* tracked by git (a PR could commit
    ///    a crafted state file to make the reviewer skip its changes).
    /// 2. The newest review marker for this agent posted by a trusted account
    ///    (bots, agent admins, trusted sources).
    ///
    /// The commit must be a valid SHA and an ancestor of `HEAD`; after a
    /// force-push the previous review no longer applies and a full review runs.
    fn find_incremental_base(&self, pr_number: u64) -> Option<String> {
        let candidate = self
            .state_file_commit(pr_number)
            .or_else(|| self.last_reviewed_commit_from_comments(pr_number))?;

        if !is_valid_sha(&candidate) {
            tracing::warn!("Ignoring malformed previous-review commit {:?}", candidate);
            return None;
        }
        let is_ancestor = Command::new("git")
            .args(["merge-base", "--is-ancestor", &candidate, "HEAD"])
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
        if !is_ancestor {
            tracing::info!(
                "Previous review commit {} is not an ancestor of HEAD; doing a full review",
                candidate
            );
            return None;
        }
        Some(candidate)
    }

    fn state_file_commit(&self, pr_number: u64) -> Option<String> {
        let state_path = format!("{}/{}.json", STATE_DIR, pr_number);
        if !Path::new(&state_path).exists() {
            return None;
        }
        let tracked = Command::new("git")
            .args(["ls-files", "--error-unmatch", "--", &state_path])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(true);
        if tracked {
            tracing::warn!(
                "Ignoring {} because it is tracked in git (possibly supplied by the PR)",
                state_path
            );
            return None;
        }
        let content = fs::read_to_string(&state_path).ok()?;
        let state: ReviewState = serde_json::from_str(&content).ok()?;
        Some(state.last_reviewed_commit)
    }

    fn is_trusted_marker_author(&self, login: &str) -> bool {
        is_bot_login(login) || self.trusted_logins.contains(&login.to_lowercase())
    }

    /// Find the last reviewed commit from trusted PR comment markers
    fn last_reviewed_commit_from_comments(&self, pr_number: u64) -> Option<String> {
        let output = Command::new("gh")
            .args(["pr", "view", &pr_number.to_string(), "--json", "comments"])
            .output()
            .ok()?;
        if !output.status.success() {
            return None;
        }

        let json: serde_json::Value = serde_json::from_slice(&output.stdout).ok()?;
        let comments = json.get("comments")?.as_array()?;
        let marker_prefix = format!("<!-- {}-review-marker:commit:", self.agent.name());

        comments.iter().rev().find_map(|comment| {
            let author = comment.pointer("/author/login")?.as_str()?;
            if !self.is_trusted_marker_author(author) {
                return None;
            }
            extract_marker_commit(comment.get("body")?.as_str()?, &marker_prefix)
        })
    }

    /// Save review state after posting
    fn save_review_state(&self, pr_number: u64, commit: &str) -> Result<()> {
        if !is_valid_sha(commit) {
            return Ok(());
        }
        fs::create_dir_all(STATE_DIR)?;
        let state = ReviewState {
            last_reviewed_commit: commit.to_string(),
            last_review_timestamp: chrono::Utc::now().to_rfc3339(),
        };
        let state_path = format!("{}/{}.json", STATE_DIR, pr_number);
        fs::write(&state_path, serde_json::to_string_pretty(&state)?)?;
        tracing::debug!("Saved review state to {}", state_path);
        Ok(())
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

        // Include commit SHA in marker for incremental tracking
        let marker = if commit_sha.is_empty() {
            format!("<!-- {}-review-marker -->", agent_name)
        } else {
            format!(
                "<!-- {}-review-marker:commit:{} -->",
                agent_name, commit_sha
            )
        };

        let base_type = match &self.profile {
            Some(profile) => profile.display_name.clone(),
            None if is_incremental => "Review".to_string(),
            None => "Code Review".to_string(),
        };
        let review_type = if is_incremental {
            format!("Incremental {}", base_type)
        } else {
            base_type
        };

        let incremental_note = if is_incremental {
            "\n*This is an incremental review focusing on changes since the last review.*\n"
        } else {
            ""
        };

        let agent_display = capitalize(agent_name);
        format!(
            "## {} AI {}\n{}\n{}\n{}\n{}\n\n---\n*Generated by {} AI ({}). Supplementary to human reviews.*\n",
            agent_display,
            review_type,
            marker,
            AGENT_COMMENT_MARKER,
            incremental_note,
            inject_filtered_note(review, filtered_claims),
            agent_display,
            self.agent.model(),
        )
    }

    /// Post review comment to PR, retrying once after stripping emojis if
    /// gh-validator rejects the body.
    fn post_review(&self, pr_number: u64, formatted: &str) -> Result<()> {
        let mut file = tempfile::Builder::new()
            .prefix(&format!("pr-review-{}-", pr_number))
            .suffix(".md")
            .tempfile()?;
        file.write_all(formatted.as_bytes())?;
        file.flush()?;
        let temp_path = file.path().to_string_lossy().into_owned();

        let mut args = vec![
            "pr".to_string(),
            "comment".to_string(),
            pr_number.to_string(),
            "--body-file".to_string(),
            temp_path,
            // Strip invalid reaction images instead of failing the entire review
            "--gh-validator-strip-invalid-images".to_string(),
        ];
        // Explicit repo avoids detection issues on self-hosted runners
        if let Ok(repo) = std::env::var("GITHUB_REPOSITORY")
            && !repo.is_empty()
        {
            args.push("--repo".to_string());
            args.push(repo);
        }

        let output = Command::new("gh").args(&args).output()?;
        if output.status.success() {
            return Ok(());
        }

        let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
        let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
        tracing::error!("gh pr comment failed - stderr: {}", stderr.trim());

        // gh-validator rejects Unicode emojis (which agents still occasionally
        // emit despite the prompt); a one-shot failure would drop the review.
        if is_sanitizable_failure(&stderr) {
            let (sanitized, replaced) = strip_emojis(formatted);
            if replaced > 0 {
                tracing::warn!(
                    "Sanitizing review after gh-validator rejection: replaced {} emoji character(s), retrying",
                    replaced
                );
                fs::write(file.path(), &sanitized)?;
                let retry = Command::new("gh").args(&args).output()?;
                if retry.status.success() {
                    tracing::info!("Review posted after sanitization retry");
                    return Ok(());
                }
                return Err(Error::GhCommandFailed {
                    exit_code: retry.status.code().unwrap_or(-1),
                    stdout: String::from_utf8_lossy(&retry.stdout).into_owned(),
                    stderr: String::from_utf8_lossy(&retry.stderr).into_owned(),
                });
            }
            tracing::warn!(
                "gh-validator reported emoji rejection but no emojis found in body; not retrying"
            );
        }

        Err(Error::GhCommandFailed {
            exit_code: output.status.code().unwrap_or(-1),
            stdout,
            stderr,
        })
    }
}

/// Extract a SHA from `<!-- <agent>-review-marker:commit:<sha> -->`.
fn extract_marker_commit(body: &str, marker_prefix: &str) -> Option<String> {
    let start = body.find(marker_prefix)? + marker_prefix.len();
    let rest = &body[start..];
    let end = rest.find(" -->")?;
    let commit = &rest[..end];
    is_valid_sha(commit).then(|| commit.to_string())
}

/// Add a note about filtered (hallucinated) claims to the Notes section,
/// creating one before the reaction image when absent.
fn inject_filtered_note(review: &str, filtered_claims: usize) -> String {
    if filtered_claims == 0 {
        return review.to_string();
    }
    let note = format!(
        "- {} claim(s) were automatically filtered as potential hallucinations (file:line content didn't match claims)",
        filtered_claims
    );

    if let Some(notes_pos) = review.find("## Notes") {
        return match review[notes_pos..].find('\n') {
            Some(nl) => {
                let insert = notes_pos + nl + 1;
                format!("{}{}\n{}", &review[..insert], note, &review[insert..])
            },
            None => format!("{}\n{}", review, note),
        };
    }
    match review.find("![") {
        Some(pos) => format!(
            "{}\n## Notes\n{}\n\n{}",
            review[..pos].trim_end(),
            note,
            &review[pos..]
        ),
        None => format!("{}\n{}", review, note),
    }
}

/// Fetch PR comments and bucket them by trust level via `board-manager`.
///
/// Any failure (API error, board-manager missing) degrades to "no comment
/// context" rather than failing the review.
fn fetch_bucketed_comments(pr_number: u64) -> String {
    let output = match Command::new("gh")
        .args([
            "api",
            "--paginate",
            &format!("repos/{{owner}}/{{repo}}/issues/{}/comments", pr_number),
        ])
        .output()
    {
        Ok(o) if o.status.success() => o,
        _ => {
            tracing::warn!("Failed to fetch PR comments");
            return String::new();
        },
    };

    // Merge paginated pages into a single JSON array for board-manager
    let comments: Vec<serde_json::Value> =
        match parse_paginated_array(&String::from_utf8_lossy(&output.stdout)) {
            Ok(c) => c,
            Err(e) => {
                tracing::warn!("Failed to parse PR comments: {}", e);
                return String::new();
            },
        };
    let comments_json = serde_json::Value::Array(comments).to_string();

    let board_manager = [
        "./tools/rust/board-manager/target/release/board-manager",
        "tools/rust/board-manager/target/release/board-manager",
    ]
    .into_iter()
    .find(|p| Path::new(p).exists())
    .unwrap_or("board-manager");

    let result = Command::new(board_manager)
        .args(["bucket-comments", "--filter-noise"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .and_then(|mut child| {
            if let Some(mut stdin) = child.stdin.take() {
                stdin.write_all(comments_json.as_bytes())?;
            }
            child.wait_with_output()
        });

    match result {
        Ok(out) if out.status.success() => String::from_utf8_lossy(&out.stdout).into_owned(),
        Ok(out) => {
            tracing::warn!(
                "board-manager bucket-comments failed: {}",
                String::from_utf8_lossy(&out.stderr).trim()
            );
            String::new()
        },
        Err(e) => {
            tracing::warn!("board-manager unavailable, skipping comment context: {}", e);
            String::new()
        },
    }
}

/// Get previous issues from bot review comments (for incremental reviews)
fn get_previous_issues(pr_number: u64) -> Option<String> {
    let output = Command::new("gh")
        .args([
            "api",
            "--paginate",
            &format!("repos/{{owner}}/{{repo}}/issues/{}/comments", pr_number),
            "--jq",
            r#".[] | select(.user.type == "Bot" or .user.login == "github-actions[bot]") | .body"#,
        ])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let issues = extract_issue_lines(&String::from_utf8_lossy(&output.stdout));
    (!issues.is_empty()).then(|| issues.join("\n"))
}

/// Lines of the form `- [CRITICAL|BUG|WARNING|SUGGESTION] ...`.
fn extract_issue_lines(body: &str) -> Vec<String> {
    const PREFIXES: &[&str] = &["- [CRITICAL]", "- [BUG]", "- [WARNING]", "- [SUGGESTION]"];
    body.lines()
        .map(str::trim)
        .filter(|l| PREFIXES.iter().any(|p| l.starts_with(p)))
        .map(str::to_string)
        .collect()
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
        let parsed: ReviewState = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.last_reviewed_commit, "abc123");
    }

    #[test]
    fn test_extract_marker_commit() {
        let prefix = "<!-- claude-review-marker:commit:";
        assert_eq!(
            extract_marker_commit(
                "x <!-- claude-review-marker:commit:abcdef1234 --> y",
                prefix
            ),
            Some("abcdef1234".to_string())
        );
        assert_eq!(
            extract_marker_commit("<!-- claude-review-marker:commit:--output=x -->", prefix),
            None
        );
        assert_eq!(extract_marker_commit("no marker", prefix), None);
    }

    #[test]
    fn test_inject_filtered_note() {
        assert_eq!(inject_filtered_note("body", 0), "body");

        let with_notes = "## Issues\n- x\n## Notes\n- existing\n";
        let out = inject_filtered_note(with_notes, 2);
        assert!(out.contains("## Notes\n- 2 claim(s)"));
        assert!(out.contains("- existing"));

        let with_reaction = "## Issues\n- x\n\n![Reaction](https://e/x.webp)";
        let out = inject_filtered_note(with_reaction, 1);
        assert!(out.contains("## Notes\n- 1 claim(s)"));
        assert!(out.ends_with("![Reaction](https://e/x.webp)"));
    }

    #[test]
    fn test_extract_issue_lines() {
        let body = "## Issues\n- [BUG] `a.rs:1` - x\n  - [WARNING] nested\ntext [BUG] inline";
        assert_eq!(
            extract_issue_lines(body),
            vec!["- [BUG] `a.rs:1` - x", "- [WARNING] nested"]
        );
    }
}
