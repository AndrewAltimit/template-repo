//! Orchestration: turn a parsed review plus CLI flags into git/GitHub actions.

use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use serde::Serialize;
use tracing::{info, warn};

use crate::cli::Args;
use crate::comment;
use crate::git::{ApplyMethod, GitOperations};
use crate::github::GitHubClient;
use crate::patch;
use crate::review::{Review, ReviewStatus, Severity};

/// Everything the processor did, for `--output-format json`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Summary {
    /// Whether this was a dry run (no mutations performed).
    pub dry_run: bool,
    /// Review severity.
    pub severity: Severity,
    /// Findings reported by the agent.
    pub findings_count: u32,
    /// Endpoint review ID, if the input was a full envelope.
    pub review_id: Option<String>,
    /// Endpoint status, if the input was a full envelope.
    pub review_status: Option<ReviewStatus>,
    /// Whether a PR comment was posted (or would have been, in a dry run).
    pub comment_posted: bool,
    /// Files touched by the applied fixes.
    pub files_changed: Vec<String>,
    /// How the fixes were applied, if they were.
    pub apply_method: Option<&'static str>,
    /// SHA of the fix commit (never set in a dry run).
    pub commit_sha: Option<String>,
    /// Whether a commit was made.
    pub made_changes: bool,
    /// Branch that was pushed / used as the PR head.
    pub branch: Option<String>,
    /// Whether a push was performed (or would have been, in a dry run).
    pub pushed: bool,
    /// Number of the created PR (0 in a dry run or if unparseable).
    pub pr_number: Option<u64>,
    /// URL of the created PR.
    pub pr_url: Option<String>,
    /// The `--fail-on-severity` threshold, if given.
    pub severity_threshold: Option<Severity>,
    /// Whether the severity met the threshold (exit code 3).
    pub threshold_exceeded: bool,
}

impl Summary {
    fn new(review: &Review, args: &Args) -> Self {
        let meta = review.meta.as_ref();
        Self {
            dry_run: args.dry_run,
            severity: review.severity,
            findings_count: review.findings_count,
            review_id: meta.and_then(|m| m.review_id.clone()),
            review_status: meta.and_then(|m| m.status),
            comment_posted: false,
            files_changed: Vec::new(),
            apply_method: None,
            commit_sha: None,
            made_changes: false,
            branch: None,
            pushed: false,
            pr_number: None,
            pr_url: None,
            severity_threshold: args.fail_on_severity,
            threshold_exceeded: args.fail_on_severity.is_some_and(|t| review.severity >= t),
        }
    }
}

/// Processes code review results.
pub struct ReviewProcessor {
    dry_run: bool,
    git: GitOperations,
    github: GitHubClient,
}

impl ReviewProcessor {
    /// Create a processor operating on the current working directory.
    pub fn new(dry_run: bool) -> Self {
        Self::with_clients(
            GitOperations::new(dry_run),
            GitHubClient::new(dry_run),
            dry_run,
        )
    }

    /// Create a processor with explicit git and GitHub clients.
    pub fn with_clients(git: GitOperations, github: GitHubClient, dry_run: bool) -> Self {
        Self {
            dry_run,
            git,
            github,
        }
    }

    /// Run the actions requested by `args` for `review`.
    ///
    /// The comment is posted before fixes are applied, so the review is
    /// visible even if the fixes turn out not to apply.
    pub fn process(&self, review: &Review, args: &Args) -> Result<Summary> {
        let repository = args.validate()?;
        let mut summary = Summary::new(review, args);

        if args.branch.is_some() && !args.create_pr {
            warn!("--branch only applies to --create-pr; ignoring it");
        }
        if review.agent_failed() {
            warn!("The review agent did not commit a validated result (status: failed)");
        }

        if args.post_comment {
            // Validated above: both are present when --post-comment is set.
            let repository = repository.context("Repository required for --post-comment")?;
            let pr = args
                .pr_number
                .context("PR number required for --post-comment")?;
            let body = comment::format_comment(review, args.raw_comment);
            self.github.post_pr_comment(repository, pr, &body)?;
            summary.comment_posted = true;
        }

        if !(args.commit_changes || args.create_pr) {
            return Ok(summary);
        }
        if !review.has_fixes() {
            info!("Review contains no file changes; nothing to commit");
            return Ok(summary);
        }

        let prepared = patch::prepare_changes(review.file_changes())?;
        self.git.check_original_shas(&prepared);

        let pr_branch = if args.create_pr {
            let name = args.branch.clone().unwrap_or_else(default_branch_name);
            self.git.create_branch(&name)?;
            Some(name)
        } else {
            None
        };

        let method = self.git.apply_patch(&patch::combine(&prepared))?;
        summary.apply_method = Some(apply_method_name(method));
        let paths: Vec<&str> = prepared.iter().map(|c| c.path.as_str()).collect();
        self.git.stage(&paths)?;
        let sha = self.git.commit(&args.commit_message, &paths)?;
        summary.files_changed = paths.iter().map(|p| (*p).to_string()).collect();
        summary.made_changes = sha.is_some();
        summary.commit_sha = sha;
        let committed = summary.made_changes || self.dry_run;

        if let Some(branch) = pr_branch {
            summary.branch = Some(branch.clone());
            if !committed {
                warn!("Fixes produced no changes; not pushing or creating a PR");
                return Ok(summary);
            }
            let repository = repository.context("Repository required for --create-pr")?;
            self.git.push(&branch)?;
            summary.pushed = true;
            let (number, url) = self.github.create_pr(
                repository,
                &comment::format_pr_title(review),
                &comment::format_pr_body(review),
                &branch,
                &args.base_branch,
            )?;
            info!(pr_number = number, pr_url = %url, "Pull request created");
            summary.pr_number = Some(number);
            summary.pr_url = Some(url);
        } else if args.push && committed {
            let branch = match self.git.current_branch() {
                Ok(Some(branch)) => branch,
                Ok(None) => anyhow::bail!("Cannot --push from a detached HEAD"),
                Err(_) if self.dry_run => "HEAD".to_string(),
                Err(e) => return Err(e),
            };
            self.git.push(&branch)?;
            summary.pushed = true;
            summary.branch = Some(branch);
        }

        Ok(summary)
    }
}

fn apply_method_name(method: ApplyMethod) -> &'static str {
    match method {
        ApplyMethod::GitApply => "git-apply",
        ApplyMethod::GitApplyIgnoreWhitespace => "git-apply-ignore-whitespace",
        ApplyMethod::Patch => "patch",
    }
}

fn default_branch_name() -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_secs());
    format!("code-review-fixes-{secs}")
}

#[cfg(test)]
mod tests {
    use clap::Parser;

    use super::*;
    use crate::review::parse_review_json;

    fn args(extra: &[&str]) -> Args {
        let mut argv = vec!["code-review-processor", "--repository", "owner/repo"];
        argv.extend_from_slice(extra);
        Args::try_parse_from(argv).unwrap()
    }

    fn review(severity: &str) -> Review {
        parse_review_json(&format!(
            r#"{{"review_markdown": "r", "severity": "{severity}", "findings_count": 2}}"#
        ))
        .unwrap()
    }

    #[test]
    fn no_flags_is_a_no_op() {
        let summary = ReviewProcessor::new(true)
            .process(&review("low"), &args(&[]))
            .unwrap();
        assert!(!summary.comment_posted);
        assert!(!summary.made_changes);
        assert!(!summary.threshold_exceeded);
    }

    #[test]
    fn dry_run_comment_is_reported() {
        let a = args(&["--dry-run", "--post-comment", "--pr-number", "5"]);
        let summary = ReviewProcessor::new(true)
            .process(&review("low"), &a)
            .unwrap();
        assert!(summary.comment_posted);
        assert!(summary.dry_run);
    }

    #[test]
    fn fixes_requested_without_file_changes_is_a_no_op() {
        let a = args(&["--dry-run", "--commit-changes", "--create-pr"]);
        let summary = ReviewProcessor::new(true)
            .process(&review("low"), &a)
            .unwrap();
        assert!(summary.pr_url.is_none());
        assert!(summary.files_changed.is_empty());
    }

    #[test]
    fn invalid_arguments_fail_before_side_effects() {
        let a = args(&["--post-comment"]);
        assert!(
            ReviewProcessor::new(true)
                .process(&review("low"), &a)
                .is_err()
        );
    }

    #[test]
    fn severity_threshold() {
        let p = ReviewProcessor::new(true);
        let a = args(&["--fail-on-severity", "high"]);
        assert!(
            p.process(&review("critical"), &a)
                .unwrap()
                .threshold_exceeded
        );
        assert!(p.process(&review("high"), &a).unwrap().threshold_exceeded);
        assert!(!p.process(&review("medium"), &a).unwrap().threshold_exceeded);
    }

    #[test]
    fn default_branch_name_is_prefixed() {
        assert!(default_branch_name().starts_with("code-review-fixes-"));
    }

    #[test]
    fn summary_serializes() {
        let summary = ReviewProcessor::new(true)
            .process(&review("low"), &args(&[]))
            .unwrap();
        let json = serde_json::to_value(&summary).unwrap();
        assert_eq!(json["severity"], "low");
        assert_eq!(json["findings_count"], 2);
        assert_eq!(json["made_changes"], false);
    }
}
