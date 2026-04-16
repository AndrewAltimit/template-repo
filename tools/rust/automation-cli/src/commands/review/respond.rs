use std::collections::HashSet;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::{Result, bail};
use clap::Args;
use gh_validator::{SecretMasker, load_config as load_secrets_config};

use super::trust::{TrustConfig, TrustLevel};
use crate::shared::{output, process, project};

static TEMP_COUNTER: AtomicU64 = AtomicU64::new(0);

/// Prompt size limits (Claude ~200k token window, ~4 chars/token)
const MAX_REVIEW_CONTENT_CHARS: usize = 80_000;
const MAX_CLAUDE_MD_CHARS: usize = 8_000;
const MAX_PR_COMMENTS_CHARS: usize = 20_000;
const MAX_TOTAL_PROMPT_CHARS: usize = 150_000;

#[derive(Args)]
pub struct RespondArgs {
    /// PR number
    pub pr_number: u64,
    /// Branch name
    pub branch: String,
    /// Current iteration count
    #[arg(default_value = "1")]
    pub iteration: u32,
    /// Maximum iterations
    #[arg(default_value = "5")]
    pub max_iterations: u32,
}

pub fn run(args: RespondArgs) -> Result<()> {
    let root = project::find_project_root()?;
    std::env::set_current_dir(&root)?;

    output::header("Agent Review Response");
    output::info(&format!("PR Number: {}", args.pr_number));
    output::info(&format!("Branch: {}", args.branch));
    output::info(&format!(
        "Iteration: {} / {}",
        args.iteration, args.max_iterations
    ));

    // Safety check: git repository
    if !Path::new(".git").exists() {
        bail!("not in a git repository");
    }

    // Fetch and categorize PR comments
    output::step("Fetching PR comments with trust categorization...");
    let pr_comments = fetch_categorized_comments(args.pr_number, &root)?;

    // Collect review feedback BEFORE git operations
    let mut review_content = String::new();
    collect_review_content(&mut review_content)?;

    // Configure git authentication
    configure_git()?;

    // Checkout the PR branch
    output::step(&format!("Checking out branch: {}", args.branch));
    let _ = process::run("git", &["fetch", "origin", &args.branch]);
    process::run("git", &["checkout", &args.branch])?;

    if review_content.is_empty() {
        output::warn("No review feedback found, nothing to do");
        post_comment(args.pr_number, "No review feedback found to process.")?;
        report_no_commit();
        return Ok(());
    }

    // Truncate review content if needed
    truncate_in_place(&mut review_content, MAX_REVIEW_CONTENT_CHARS);
    output::info(&format!("Review content: {} chars", review_content.len()));

    // Step 1: Run precommit autoformat (formats + restages changed files)
    output::header("Step 1: Running precommit autoformat");
    run_precommit_autoformat();

    // Step 2: Invoke Claude
    output::header("Step 2: Invoking Claude for review feedback");

    let claude_md_context = load_claude_md(MAX_CLAUDE_MD_CHARS);
    let prompt = build_prompt(&args, &review_content, &claude_md_context, &pr_comments);

    // Validate prompt size
    if prompt.len() > MAX_TOTAL_PROMPT_CHARS {
        output::warn(&format!(
            "Prompt exceeds recommended limit ({} > {MAX_TOTAL_PROMPT_CHARS})",
            prompt.len()
        ));
    }

    let claude_outcome = run_claude_streamed(&prompt, args.iteration)?;
    let claude_output = claude_outcome.text.clone();

    // Step 3: Run precommit checks (autoformat + lint)
    output::header("Step 3: Running precommit checks");
    run_precommit_autoformat();

    // Capture lint failures so we can feed them back to Claude if needed
    let lint_failures = run_precommit_lint_capture();
    if !lint_failures.is_empty() {
        output::warn("Precommit lint check found issues -- invoking Claude to fix");
        let lint_fix_prompt = format!(
            "The following lint/format issues were found after your changes. \
             Please fix them. Make only the minimal changes needed to resolve these errors.\n\n\
             ## Lint Failures\n\n{lint_failures}\n\n\
             Fix these issues now using the Edit tool. Do NOT add comments explaining \
             the fixes -- just apply the minimal correction."
        );
        let _ = run_claude_streamed(&lint_fix_prompt, args.iteration);

        // Re-run autoformat + restage after lint fixes
        run_precommit_autoformat();

        // Verify lint fixes resolved the issues
        let remaining = run_precommit_lint_capture();
        if !remaining.is_empty() {
            output::warn(
                "Lint issues remain after fix attempt -- will be caught in next iteration",
            );
        }
    }

    // Stage modifications to tracked files (avoid staging untracked temp files/artifacts)
    output::header("Step 4: Checking for changes");
    process::run("git", &["add", "-u"])?;

    let has_changes = !process::run_check("git", &["diff", "--cached", "--quiet"])?;

    let summary = extract_agent_summary(&claude_output);

    if !has_changes && summary_claims_fixes(&summary) {
        // Claude claimed fixes but produced no git diff. Two scenarios:
        // (a) Hard hallucination: zero file-mutating tool calls — Claude
        //     didn't even try to edit files.
        // (b) Soft hallucination: Claude called Edit but the content was
        //     identical (e.g., a prior iteration already applied the fix).
        //
        // In both cases, retry with concrete context: show Claude the diff
        // from the prior iteration so it can distinguish "already fixed"
        // from "still needs work." This is much more effective than the
        // generic "you didn't modify files" prompt.
        let is_hard = claude_outcome.edited_files.is_empty();
        let label = if is_hard { "hard" } else { "soft" };
        output::warn(&format!(
            "Agent {label} hallucination: claimed Fixed Issues but git diff is empty \
             ({} file-mutating tool calls) — retrying with prior-diff context",
            claude_outcome.edited_files.len()
        ));

        // Get the diff from the prior iteration commit so Claude can see
        // what was already changed. This is the key context that prevents
        // the agent from re-claiming fixes it didn't make.
        let prior_diff = get_prior_iteration_diff();

        let retry_prompt = format!(
            "## IMPORTANT: Your previous attempt produced NO file changes\n\n\
             Your summary claimed to fix issues, but `git diff` shows zero changes. \
             This means either:\n\
             1. The issues were **already fixed** by a prior iteration (most likely)\n\
             2. Your Edit calls wrote identical content (a no-op)\n\
             3. You forgot to call Edit\n\n\
             {prior_diff}\n\n\
             ## What you must do now\n\n\
             1. Read each file mentioned in the review feedback\n\
             2. Check if the issue ALREADY exists in the current code or was already fixed\n\
             3. If already fixed: list under **Ignored Issues** as \"already fixed in prior iteration\"\n\
             4. If still present: fix it with the Edit tool\n\
             5. Do NOT list anything under **Fixed Issues** unless you made an Edit call \
                that actually changes the file content\n\
             6. Do NOT invent commit SHAs — the tooling handles git\n\n\
             ## Review Feedback\n\n{review_content}\n\n\
             ## REQUIRED: Output Summary Format\n\n\
             ---AGENT-SUMMARY-START---\n\
             ### Fixed Issues\n- ...\n\
             ### Ignored Issues\n- ...\n\
             ### Deferred to Human\n- ...\n\
             ### Notes\n- ...\n\
             ---AGENT-SUMMARY-END---\n"
        );

        let retry_outcome = run_claude_streamed(&retry_prompt, args.iteration)?;
        process::run("git", &["add", "-u"])?;
        let retry_has_changes = !process::run_check("git", &["diff", "--cached", "--quiet"])?;
        let retry_summary = extract_agent_summary(&retry_outcome.text);

        if retry_has_changes {
            output::info("Retry produced actual file changes");
            return commit_and_push(
                &args,
                &if retry_summary.is_empty() {
                    summary
                } else {
                    retry_summary
                },
            );
        }

        // Still no changes after retry. If the retry summary no longer
        // claims fixes (i.e., Claude correctly categorized everything as
        // "Ignored Issues"), that's actually a success — post a clean
        // "no changes needed" comment instead of the hallucination warning.
        let final_summary = if retry_summary.is_empty() {
            summary.clone()
        } else {
            retry_summary.clone()
        };

        if !retry_summary.is_empty() && !summary_claims_fixes(&retry_summary) {
            output::info("Retry correctly identified no changes needed");
            post_decision_comment(args.pr_number, args.iteration, false, "", &final_summary)?;
            report_no_commit();
            return Ok(());
        }

        // Retry still hallucinating — post warning.
        output::warn("Retry still produced no file changes with claimed fixes");
        post_hallucination_comment(
            args.pr_number,
            args.iteration,
            &final_summary,
            retry_outcome
                .stream_log_path
                .as_deref()
                .or(claude_outcome.stream_log_path.as_deref()),
        )?;
        report_no_commit();
        return Ok(());
    }

    if !has_changes {
        output::info("No changes to commit");
        post_decision_comment(args.pr_number, args.iteration, false, "", &summary)?;
        report_no_commit();
        return Ok(());
    }

    commit_and_push(&args, &summary)
}

fn commit_and_push(args: &RespondArgs, summary: &str) -> Result<()> {
    output::step("Changes detected, creating commit...");
    let display_iter = args.iteration + 1;
    let commit_msg = format!(
        "fix: address AI review feedback (iteration {})\n\n\
         Automated fix by Claude in response to AI review feedback.\n\n\
         Iteration: {}/{}\n\n\
         Co-Authored-By: AI Review Agent <noreply@anthropic.com>",
        display_iter, display_iter, args.max_iterations
    );
    let msg_file = write_temp_file(&commit_msg)?;
    process::run("git", &["commit", "-F", &msg_file])?;
    let _ = std::fs::remove_file(&msg_file);

    // Verify the commit actually contains changes (not an empty commit).
    let diff_stat = process::run_capture("git", &["diff", "--stat", "HEAD~1..HEAD"])?;
    if diff_stat.trim().is_empty() {
        output::warn("Commit appears empty — no file changes in diff");
        post_decision_comment(args.pr_number, args.iteration, false, "", summary)?;
        report_no_commit();
        return Ok(());
    }

    let commit_full = process::run_capture("git", &["rev-parse", "HEAD"])?;
    let commit_full = commit_full.trim().to_string();
    let commit_short = process::run_capture("git", &["rev-parse", "--short", "HEAD"])?;
    let commit_short = commit_short.trim().to_string();

    // Post comment BEFORE pushing — pushing triggers a new pipeline
    // run which cancels this one, so the comment must go first.
    post_decision_comment(args.pr_number, args.iteration, true, &commit_short, summary)?;

    // Push with verification: git push alone is unreliable (can exit 0 while the
    // remote ref is unchanged). push_and_verify confirms via ls-remote that the
    // commit actually landed, handles non-fast-forward by rebasing, and retries.
    output::header("Step 5: Pushing changes");
    let branch = args.branch.clone();
    let initial_sha = commit_full.clone();
    let push_result = temporarily_disable_pre_push_hook(|| push_and_verify(&branch, &initial_sha));

    match push_result {
        Ok(final_sha) => {
            output::success(&format!(
                "Push verified: origin/{} = {}",
                args.branch, final_sha
            ));
            project::set_github_output("made_changes", "true");
            project::set_github_output("pushed", "true");
            project::set_github_output("commit_sha", &final_sha);
            Ok(())
        },
        Err(e) => {
            // Re-read HEAD in case a rebase inside push_and_verify rewrote it.
            let current_full = process::run_capture("git", &["rev-parse", "HEAD"])
                .map(|s| s.trim().to_string())
                .unwrap_or(commit_full);
            let current_short = process::run_capture("git", &["rev-parse", "--short", "HEAD"])
                .map(|s| s.trim().to_string())
                .unwrap_or(commit_short);

            // The commit exists locally but did not reach the remote. Save a
            // format-patch so the workflow can upload it as an artifact and a
            // human (or a later iteration) can recover the lost work.
            let patch_note = match save_commit_patch(&current_full) {
                Ok(path) => {
                    output::warn(&format!("Saved unpushed commit as patch: {path}"));
                    format!(
                        "\n\nThe commit was saved as `{path}` for recovery; \
                         this file is uploaded as the `unpushed-review-commit` workflow artifact."
                    )
                },
                Err(pe) => {
                    output::warn(&format!("Failed to save commit patch: {pe}"));
                    String::new()
                },
            };

            let _ = post_comment(
                args.pr_number,
                &format!(
                    "## Review Response Agent: push failed\n\
                     <!-- agent-metadata:type=review-fix-push-failure -->\n\n\
                     Commit `{current_short}` was created locally but did **not** reach the \
                     remote after multiple verified retries.\n\n\
                     **Error:** `{e}`\n\n\
                     Manual intervention required. The earlier \"Changes committed, pushing...\" \
                     comment should be considered superseded by this one.{patch_note}"
                ),
            );

            // Still report made_changes=true (the commit was created) but pushed=false
            // so downstream steps can distinguish "in flight" from "actually landed".
            project::set_github_output("made_changes", "true");
            project::set_github_output("pushed", "false");
            project::set_github_output("commit_sha", &current_full);
            Err(e)
        },
    }
}

/// Get the diff from the most recent agent commit (prior iteration) so the
/// retry prompt can show Claude what was already changed. Returns a formatted
/// string suitable for embedding in the prompt, or an empty string if no
/// prior agent commit is found.
fn get_prior_iteration_diff() -> String {
    // Check if the current HEAD is an agent commit.
    let author = process::run_capture("git", &["log", "-1", "--format=%an"]).unwrap_or_default();
    let author = author.trim();
    let is_agent = ["AI Review Agent", "AI Pipeline Agent", "AI Agent Bot"]
        .iter()
        .any(|a| a.eq_ignore_ascii_case(author));

    if !is_agent {
        return String::new();
    }

    // Verify HEAD~1 exists (shallow clones may not have it).
    if !process::run_check("git", &["rev-parse", "--verify", "HEAD~1"]).unwrap_or(false) {
        output::warn("Prior iteration diff unavailable (shallow clone or initial commit)");
        return String::new();
    }

    // Get the diff of the prior iteration's commit.
    let diff = match process::run_capture("git", &["diff", "--stat", "HEAD~1..HEAD"]) {
        Ok(d) => d,
        Err(e) => {
            output::warn(&format!("Failed to get prior iteration diff --stat: {e}"));
            return String::new();
        },
    };
    let diff = diff.trim();
    if diff.is_empty() {
        return String::new();
    }

    // Also get the full diff (truncated) so Claude can see actual changes.
    let full_diff = match process::run_capture("git", &["diff", "HEAD~1..HEAD"]) {
        Ok(d) => d,
        Err(e) => {
            output::warn(&format!("Failed to get prior iteration full diff: {e}"));
            String::new()
        },
    };
    let mut full_diff = full_diff.trim().to_string();
    if full_diff.len() > 4000 {
        let safe = full_diff.floor_char_boundary(4000);
        full_diff.truncate(safe);
        full_diff.push_str("\n... (truncated)");
    }

    format!(
        "## Prior iteration already made these changes\n\n\
         The previous agent iteration (HEAD commit by `{author}`) modified:\n\
         ```\n{diff}\n```\n\n\
         Full diff:\n```diff\n{full_diff}\n```\n\n\
         If an issue from the review feedback was addressed by these changes, \
         it is **already fixed** — list it under Ignored Issues, not Fixed Issues.\n"
    )
}

/// Mark the "no commit produced" state unambiguously in GitHub Actions outputs.
fn report_no_commit() {
    project::set_github_output("made_changes", "false");
    project::set_github_output("pushed", "false");
    project::set_github_output("commit_sha", "");
}

/// Push the current branch and verify via `git ls-remote` that the remote ref
/// actually matches local HEAD. Handles silent push failures (command reports
/// success but the remote ref is unchanged) and non-fast-forward rejections
/// (fetch + rebase + recompute expected SHA). Returns the SHA that was
/// verifiably landed on the remote.
fn push_and_verify(branch: &str, initial_sha: &str) -> Result<String> {
    const MAX_ATTEMPTS: u32 = 5;
    let mut last_err: Option<anyhow::Error> = None;
    let mut current_sha = initial_sha.to_string();

    for attempt in 1..=MAX_ATTEMPTS {
        output::info(&format!(
            "Push attempt {attempt}/{MAX_ATTEMPTS} (expected sha: {current_sha})"
        ));

        let push_result = process::run("git", &["push", "origin", branch]);

        match push_result {
            Ok(()) => match verify_remote_head(branch, &current_sha) {
                Ok(true) => return Ok(current_sha),
                Ok(false) => {
                    output::warn("Push reported success but remote ref is stale — retrying");
                    last_err = Some(anyhow::anyhow!(
                        "push verification failed: origin/{branch} does not match {current_sha}"
                    ));
                },
                Err(e) => {
                    output::warn(&format!("Could not verify remote ref: {e}"));
                    last_err = Some(e);
                },
            },
            Err(e) => {
                let msg = format!("{e}");
                output::warn(&format!("Push failed: {msg}"));
                if looks_like_non_fast_forward(&msg)
                    && let Some(new_sha) = rebase_onto_remote(branch)
                {
                    current_sha = new_sha;
                    output::info(&format!("Rebased; new local HEAD = {current_sha}"));
                }
                last_err = Some(e);
            },
        }

        if attempt < MAX_ATTEMPTS {
            let delay = 2u64.pow(attempt.min(5));
            std::thread::sleep(Duration::from_secs(delay));
        }
    }

    Err(last_err.unwrap_or_else(|| anyhow::anyhow!("push failed: exhausted retries")))
}

fn looks_like_non_fast_forward(msg: &str) -> bool {
    let lower = msg.to_lowercase();
    lower.contains("non-fast-forward")
        || lower.contains("fetch first")
        || lower.contains("updates were rejected")
}

/// Fetch the branch and rebase local onto it. Returns the new HEAD SHA on
/// success; aborts any in-progress rebase and returns None on failure so the
/// caller can retry the bare push.
fn rebase_onto_remote(branch: &str) -> Option<String> {
    output::info("Non-fast-forward detected — fetching and rebasing");
    if process::run("git", &["fetch", "origin", branch]).is_err() {
        return None;
    }
    let remote_ref = format!("origin/{branch}");
    if process::run("git", &["rebase", &remote_ref]).is_err() {
        let _ = process::run("git", &["rebase", "--abort"]);
        output::warn("Rebase failed — aborted, will retry bare push");
        return None;
    }
    process::run_capture("git", &["rev-parse", "HEAD"])
        .ok()
        .map(|s| s.trim().to_string())
}

fn verify_remote_head(branch: &str, expected_sha: &str) -> Result<bool> {
    let full_ref = format!("refs/heads/{branch}");
    let out = process::run_capture("git", &["ls-remote", "origin", &full_ref])?;
    let remote_sha = parse_ls_remote_sha(&out)
        .ok_or_else(|| anyhow::anyhow!("ls-remote returned no ref for {branch}"))?;
    output::info(&format!("Remote origin/{branch} = {remote_sha}"));
    Ok(remote_sha == expected_sha)
}

/// Extract the branch SHA from `git ls-remote` output, preferring `refs/heads/`.
fn parse_ls_remote_sha(output: &str) -> Option<String> {
    let extract_sha = |line: &str| line.split_whitespace().next().map(|s| s.to_string());
    output
        .lines()
        .find(|line| line.contains("refs/heads/"))
        .and_then(extract_sha)
}

/// Persist the unpushed commit as a `.patch` file in `$RUNNER_TEMP/review-agent-patches/`
/// so the workflow can upload it as an artifact for manual recovery.
///
/// The patch is masked through `gh-validator`'s `SecretMasker` (same `.secrets.yaml`
/// as PR-comment masking) before hitting disk. We do NOT structurally redact the
/// patch the way we do the stream log — the patch *is* the work to recover, and
/// stripping its content would make it un-applicable. Pattern-based masking
/// handles known secret formats without breaking the diff format.
///
/// Fail-closed: if `.secrets.yaml` is missing or unparseable, no patch is written.
fn save_commit_patch(sha: &str) -> Result<String> {
    let masker = load_secret_masker()?;
    let raw_patch = process::run_capture("git", &["format-patch", "-1", "HEAD", "--stdout"])?;
    let (masked_patch, _modified) = masker.mask(&raw_patch);

    let base = std::env::var("RUNNER_TEMP")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    let dir = base.join("review-agent-patches");
    std::fs::create_dir_all(&dir)?;
    let short_end = sha.len().min(12);
    let path = dir.join(format!("unpushed-{}.patch", &sha[..short_end]));
    std::fs::write(&path, masked_patch)?;
    Ok(path.to_string_lossy().to_string())
}

fn collect_review_content(content: &mut String) -> Result<()> {
    // Collect review artifacts from all reviewer agents.
    // Each reviewer saves its output to a known file path (env var or default).
    let review_sources: &[(&str, &str, &str)] = &[
        // (env_var, default_path, display_name)
        (
            "CLAUDE_SECURITY_REVIEW_PATH",
            "claude-security-review.md",
            "Claude Security Review",
        ),
        (
            "CLAUDE_QUALITY_REVIEW_PATH",
            "claude-quality-review.md",
            "Claude Quality Review",
        ),
        (
            "OPENROUTER_REVIEW_PATH",
            "openrouter-review.md",
            "OpenRouter Review",
        ),
        // Legacy (disabled but kept for backwards compatibility if force-labels used)
        ("GEMINI_REVIEW_PATH", "gemini-review.md", "Gemini Review"),
        ("CODEX_REVIEW_PATH", "codex-review.md", "Codex Review"),
    ];

    for (env_var, default_path, display_name) in review_sources {
        let path = std::env::var(env_var).unwrap_or_else(|_| default_path.to_string());
        if let Ok(text) = std::fs::read_to_string(&path)
            && !text.trim().is_empty()
        {
            output::info(&format!("Found {display_name} at: {path}"));
            content.push_str(&format!("## {display_name} Feedback\n\n"));
            content.push_str(&text);
            content.push_str("\n\n");
        }
    }
    Ok(())
}

fn fetch_categorized_comments(pr_number: u64, root: &Path) -> Result<String> {
    let repo = std::env::var("GITHUB_REPOSITORY").unwrap_or_default();
    if repo.is_empty() || !process::command_exists("gh") {
        return Ok(String::new());
    }

    let trust = TrustConfig::load(root);

    let json = match process::run_capture(
        "gh",
        &[
            "api",
            &format!("repos/{repo}/issues/{pr_number}/comments"),
            "--paginate",
        ],
    ) {
        Ok(j) => j,
        Err(_) => return Ok(String::new()),
    };

    let comments: Vec<serde_json::Value> = serde_json::from_str(&json).unwrap_or_default();

    let mut admin_comments = Vec::new();
    let mut trusted_comments = Vec::new();
    let mut other_comments = Vec::new();

    for c in &comments {
        let author = c["user"]["login"].as_str().unwrap_or("");
        let body = c["body"].as_str().unwrap_or("").trim().to_string();

        // Skip AI review markers (all reviewer agents use <!-- NAME-review-marker:commit:SHA -->)
        if body.contains("-review-marker:commit:") {
            continue;
        }
        if body.len() < 10 {
            continue;
        }

        let body = if body.len() > 2000 {
            let safe_end = body.floor_char_boundary(2000);
            format!("{}... (truncated)", &body[..safe_end])
        } else {
            body
        };

        let formatted = format!("**@{author}**: {body}");

        match trust.level(author) {
            TrustLevel::Admin => admin_comments.push(formatted),
            TrustLevel::Trusted => trusted_comments.push(formatted),
            TrustLevel::External => other_comments.push(formatted),
        }
    }

    let mut result = String::new();

    if !admin_comments.is_empty() {
        result.push_str(TrustLevel::Admin.header());
        result.push('\n');
        for c in &admin_comments {
            result.push_str(c);
            result.push('\n');
        }
        result.push('\n');
    }
    if !trusted_comments.is_empty() {
        result.push_str(TrustLevel::Trusted.header());
        result.push('\n');
        for c in &trusted_comments {
            result.push_str(c);
            result.push('\n');
        }
        result.push('\n');
    }
    if !other_comments.is_empty() {
        result.push_str(TrustLevel::External.header());
        result.push('\n');
        // Only include last 5 untrusted comments
        for c in other_comments.iter().rev().take(5).rev() {
            result.push_str(c);
            result.push('\n');
        }
        result.push('\n');
    }

    if !result.is_empty() {
        result = format!("## PR Discussion Context\n\n{result}");
    }

    // Truncate if needed
    truncate_in_place(&mut result, MAX_PR_COMMENTS_CHARS);
    Ok(result)
}

fn build_prompt(
    args: &RespondArgs,
    review_content: &str,
    claude_md: &str,
    pr_comments: &str,
) -> String {
    let mut prompt = format!(
        "You are addressing AI code review feedback for a pull request.\n\n\
         ## Iteration Status: {} of {}\n\n",
        args.iteration, args.max_iterations
    );

    if args.iteration >= 4 {
        prompt.push_str(
            "**IMPORTANT: This PR has already been through many review cycles.**\n\
             At this point, only fix issues that meet the HIGH SEVERITY threshold:\n\
             - Security vulnerabilities (injection, auth bypass, data exposure)\n\
             - Crashes or data corruption bugs\n\
             - Build/test failures\n\n\
             Do NOT fix: minor style issues, speculative edge cases, theoretical improvements.\n\n",
        );
    } else if args.iteration >= 3 {
        prompt.push_str(
            "**NOTE: This PR has been through several review cycles.**\n\
             Focus on issues with clear, demonstrable impact:\n\
             - Security vulnerabilities and correctness bugs\n\
             - Build/test failures\n\
             - Logic errors that produce wrong results\n\
             - Resource leaks or error-handling gaps at trust boundaries\n\n\
             Skip: style preferences, speculative edge cases, theoretical improvements \
             with no concrete failure scenario.\n\n",
        );
    }

    prompt.push_str(
        "## Your Task\n\
         Review the feedback from the AI reviewers below, and fix legitimate issues.\n\n\
         ## How to Work\n\
         1. **Read the files first** - Use the Read tool to examine any file mentioned\n\
         2. **Verify claims** - Check if the reported issue actually exists in the current code\n\
         3. **Check prior fixes** - A previous iteration may have already fixed an issue. \
         If the code already contains the fix, list it under \"Ignored Issues\" with \
         \"already fixed in prior iteration\", do NOT list it under \"Fixed Issues\"\n\
         4. **Assess severity** - Is this a real bug or speculative?\n\
         5. **Fix or skip** - Fix real issues; skip theoretical ones\n\n\
         ## CRITICAL: You MUST Actually Edit Files\n\
         If you decide to fix an issue, you MUST use the Edit or Write tool to modify \
         the source files. Do NOT just describe or plan changes — apply them. \
         If you list something under \"Fixed Issues\" in your summary, the corresponding \
         file MUST have been modified by an Edit or Write tool call. \
         If you cannot or choose not to modify a file, list that issue under \
         \"Ignored Issues\" or \"Deferred to Human\" instead.\n\
         Do NOT fabricate commit SHAs or claim commits exist — the tooling handles \
         git operations. Your job is only to edit files and produce the summary.\n\n",
    );

    if !claude_md.is_empty() {
        prompt.push_str(&format!(
            "\n## Codebase Context (from CLAUDE.md)\n{claude_md}\n"
        ));
    }

    if !pr_comments.is_empty() {
        prompt.push_str(&format!(
            "\n{pr_comments}\n\n\
             **IMPORTANT:** If an ADMIN comment explains a technical limitation, \
             that overrides any reviewer suggestion to the contrary.\n\n"
        ));
    }

    prompt.push_str(&format!(
        "\n## Review Feedback to Address\n\n{review_content}\n\n---\n\n\
         Please analyze the feedback above, verify each issue, and fix what's actually broken.\n\n\
         ## REQUIRED: Output Summary Format\n\n\
         After completing your work, output a summary between these markers:\n\
         ---AGENT-SUMMARY-START---\n\
         ### Fixed Issues\n- ...\n\
         ### Ignored Issues\n- ...\n\
         ### Deferred to Human\n- ...\n\
         ### Notes\n- ...\n\
         ---AGENT-SUMMARY-END---\n"
    ));

    prompt
}

fn load_claude_md(max_chars: usize) -> String {
    match std::fs::read_to_string("CLAUDE.md") {
        Ok(mut content) => {
            truncate_in_place(&mut content, max_chars);
            content
        },
        Err(_) => String::new(),
    }
}

/// Tool names that mutate files on disk. If Claude claims to have fixed
/// issues but called none of these, the claim is a hallucination.
const FILE_MUTATING_TOOLS: &[&str] = &["Edit", "Write", "MultiEdit", "NotebookEdit"];

/// Result of a Claude invocation: extracted text plus the set of files that
/// Claude actually mutated via tool_use events, plus the on-disk path of the
/// raw stream-json log (for artifact upload / post-mortem).
struct ClaudeOutcome {
    text: String,
    edited_files: HashSet<String>,
    stream_log_path: Option<String>,
}

/// Invoke Claude in non-interactive print mode with stream-json output, save
/// the raw stream as a JSONL log file, and parse it into a ClaudeOutcome.
///
/// stream-json gives us structured `tool_use` events that we can cross-check
/// against Claude's free-text summary — without this, we cannot tell whether
/// Claude actually edited files or just generated a plausible-sounding summary.
fn run_claude_streamed(prompt: &str, iteration: u32) -> Result<ClaudeOutcome> {
    let claude_cmd = if process::command_exists("claude") {
        "claude"
    } else if process::command_exists("claude-code") {
        "claude-code"
    } else {
        output::warn("Claude CLI not found, skipping AI-assisted fixes");
        return Ok(ClaudeOutcome {
            text: String::new(),
            edited_files: HashSet::new(),
            stream_log_path: None,
        });
    };

    output::step("Running Claude (-p stream-json, 20 min timeout)...");
    let prompt_file = write_temp_file(prompt)?;
    let prompt_path = Path::new(&prompt_file);

    let raw = process::run_capture_with_timeout(
        claude_cmd,
        &[
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ],
        prompt_path,
        Duration::from_secs(20 * 60),
    );

    let _ = std::fs::remove_file(&prompt_file);
    let raw = raw?;

    let (text, edited_files) = parse_claude_stream(&raw);
    let stream_log_path = save_claude_stream_log(iteration, &raw).ok();

    if let Some(ref p) = stream_log_path {
        output::info(&format!("Claude stream log saved: {p}"));
    }
    output::info(&format!(
        "Claude tool_use touched {} file(s){}",
        edited_files.len(),
        if edited_files.is_empty() {
            String::new()
        } else {
            format!(
                " ({})",
                edited_files.iter().cloned().collect::<Vec<_>>().join(", ")
            )
        }
    ));

    Ok(ClaudeOutcome {
        text,
        edited_files,
        stream_log_path,
    })
}

/// Parse stream-json output from Claude CLI. Returns concatenated assistant
/// text plus the set of file paths touched by mutating tool calls.
///
/// Claude Code emits one JSON object per line. Assistant messages carry an
/// inner `message.content` array of blocks; we walk those for `text` and
/// `tool_use` blocks. Malformed lines are skipped silently — the CLI sometimes
/// emits non-JSON warnings on stderr and we want to be robust.
fn parse_claude_stream(stream: &str) -> (String, HashSet<String>) {
    let mut text = String::new();
    let mut edited: HashSet<String> = HashSet::new();

    for line in stream.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let Ok(event) = serde_json::from_str::<serde_json::Value>(line) else {
            continue;
        };

        match event["type"].as_str() {
            Some("assistant") => {
                if let Some(blocks) = event["message"]["content"].as_array() {
                    for block in blocks {
                        match block["type"].as_str() {
                            Some("text") => {
                                if let Some(t) = block["text"].as_str() {
                                    text.push_str(t);
                                    text.push('\n');
                                }
                            },
                            Some("tool_use") => {
                                let name = block["name"].as_str().unwrap_or("");
                                if FILE_MUTATING_TOOLS.contains(&name) {
                                    let path = block["input"]["file_path"]
                                        .as_str()
                                        .or_else(|| block["input"]["notebook_path"].as_str());
                                    if let Some(p) = path {
                                        edited.insert(p.to_string());
                                    }
                                }
                            },
                            _ => {},
                        }
                    }
                }
            },
            // Some CLI versions emit a final {"type":"result","result":"..."}
            // event with the model's last response. Include it so the summary
            // marker extraction still works if the assistant text was empty.
            Some("result") => {
                if let Some(r) = event["result"].as_str() {
                    text.push_str(r);
                    text.push('\n');
                }
            },
            _ => {},
        }
    }

    (text, edited)
}

/// Save the raw Claude stream-json output to a JSONL file under
/// `$RUNNER_TEMP/review-agent-logs/`. The pr-review-fix workflow uploads this
/// directory as the `review-agent-claude-logs` artifact.
///
/// Stream content is sanitized in two passes before hitting disk:
/// 1. **Structural redaction** (`redact_tool_payloads`) — strips `Edit`/`Write`/
///    `MultiEdit` content fields and `tool_result` content bodies entirely,
///    keeping only metadata (tool name, file_path, byte counts) so we can still
///    see *what* Claude was trying to do.
/// 2. **Pattern masking** via `gh-validator`'s `SecretMasker`, loaded from
///    `.secrets.yaml`. Catches anything the structural pass missed (e.g. tokens
///    in Bash command strings or assistant text).
///
/// Fail-closed: if `.secrets.yaml` is missing or unparseable, no log is written.
fn save_claude_stream_log(iteration: u32, content: &str) -> Result<String> {
    let masker = load_secret_masker()?;
    let redacted = redact_tool_payloads(content);
    let (sanitized, _modified) = masker.mask(&redacted);

    let base = std::env::var("RUNNER_TEMP")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    let dir = base.join("review-agent-logs");
    std::fs::create_dir_all(&dir)?;
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let path = dir.join(format!("claude-stream-iter{iteration}-{ts}.jsonl"));
    std::fs::write(&path, sanitized)?;
    Ok(path.to_string_lossy().to_string())
}

/// Load the shared `SecretMasker` from `.secrets.yaml` (same config the
/// gh-validator wrapper uses for `gh pr comment` masking). Fail-closed: if the
/// config is missing or invalid, return an error and let the caller skip the
/// artifact rather than write an unmasked file.
fn load_secret_masker() -> Result<SecretMasker> {
    let config = load_secrets_config().map_err(|e| {
        anyhow::anyhow!(
            "fail-closed: cannot load .secrets.yaml for artifact masking ({e}); \
             skipping artifact write to avoid leaking unmasked content"
        )
    })?;
    Ok(SecretMasker::new(&config))
}

/// Walk a stream-json string line-by-line and strip content payloads from
/// `tool_use` and `tool_result` blocks while preserving structure and
/// identifying metadata. The result is still valid JSONL — every line either
/// stays as-is (non-JSON, system events, etc.) or is re-serialized after
/// in-place mutation.
///
/// Fields redacted:
/// - `tool_use.input.old_string` / `new_string` / `content` → `<redacted: N chars>`
/// - `tool_use.input.edits[].old_string` / `new_string` (MultiEdit) → same
/// - `tool_result.content` (string form OR array of `{type:"text",text:"..."}`)
///
/// Fields kept:
/// - `tool_use.name`, `id`, `input.file_path`, `input.command`, `input.pattern`,
///   `input.url`, etc. — anything that describes *what* Claude was doing.
/// - `text` blocks (assistant reasoning / summary marker)
/// - `system` / `result` events
fn redact_tool_payloads(stream: &str) -> String {
    let mut out = String::with_capacity(stream.len());
    for line in stream.lines() {
        if line.trim().is_empty() {
            out.push('\n');
            continue;
        }
        match serde_json::from_str::<serde_json::Value>(line) {
            Ok(mut event) => {
                redact_event_in_place(&mut event);
                match serde_json::to_string(&event) {
                    Ok(s) => out.push_str(&s),
                    Err(_) => out.push_str(line),
                }
            },
            Err(_) => out.push_str(line),
        }
        out.push('\n');
    }
    out
}

/// Mutate a single parsed JSON event to strip content payloads from any
/// `tool_use` / `tool_result` blocks it contains.
fn redact_event_in_place(event: &mut serde_json::Value) {
    let Some(content) = event
        .get_mut("message")
        .and_then(|m| m.get_mut("content"))
        .and_then(|c| c.as_array_mut())
    else {
        return;
    };
    for block in content.iter_mut() {
        let Some(block_type) = block.get("type").and_then(|t| t.as_str()) else {
            continue;
        };
        match block_type {
            "tool_use" => redact_tool_use_input(block),
            "tool_result" => redact_tool_result(block),
            _ => {},
        }
    }
}

fn redact_tool_use_input(block: &mut serde_json::Value) {
    let Some(input) = block.get_mut("input").and_then(|i| i.as_object_mut()) else {
        return;
    };
    for key in ["old_string", "new_string", "content"] {
        if let Some(v) = input.get_mut(key) {
            *v = serde_json::Value::String(redacted_marker(v));
        }
    }
    // MultiEdit nests an array of {old_string, new_string} edit specs.
    if let Some(edits) = input.get_mut("edits").and_then(|e| e.as_array_mut()) {
        for edit in edits.iter_mut() {
            if let Some(obj) = edit.as_object_mut() {
                for key in ["old_string", "new_string"] {
                    if let Some(v) = obj.get_mut(key) {
                        *v = serde_json::Value::String(redacted_marker(v));
                    }
                }
            }
        }
    }
}

fn redact_tool_result(block: &mut serde_json::Value) {
    let Some(content) = block.get_mut("content") else {
        return;
    };
    match content {
        // String form: replace whole string with marker.
        serde_json::Value::String(_) => {
            *content = serde_json::Value::String(redacted_marker(content));
        },
        // Array of content blocks (each may carry a `text` field). Replace
        // each block's `text` with a marker so the structure is preserved.
        serde_json::Value::Array(blocks) => {
            for b in blocks.iter_mut() {
                if let Some(obj) = b.as_object_mut()
                    && let Some(text) = obj.get_mut("text")
                {
                    *text = serde_json::Value::String(redacted_marker(text));
                }
            }
        },
        _ => {},
    }
}

/// Build a `<redacted: N chars>` marker that records the size of what was
/// stripped, so debugging can still tell whether the field was empty or large.
fn redacted_marker(value: &serde_json::Value) -> String {
    let len = match value {
        serde_json::Value::String(s) => s.len(),
        other => other.to_string().len(),
    };
    format!("<redacted: {len} chars>")
}

fn extract_agent_summary(output: &str) -> String {
    let start_marker = "---AGENT-SUMMARY-START---";
    let end_marker = "---AGENT-SUMMARY-END---";

    if let Some(start) = output.find(start_marker)
        && let Some(end) = output[start..].find(end_marker)
    {
        let summary = &output[start + start_marker.len()..start + end];
        return summary.trim().to_string();
    }

    // Fallback: last 20 meaningful lines
    output
        .lines()
        .rev()
        .filter(|l| !l.trim().is_empty())
        .take(20)
        .collect::<Vec<_>>()
        .into_iter()
        .rev()
        .collect::<Vec<_>>()
        .join("\n")
}

/// Check if the agent summary claims to have fixed issues (non-empty
/// "Fixed Issues" section).
///
/// Handles `##` and `###` headings, case-insensitive matching, and
/// various "none" markers.
fn summary_claims_fixes(summary: &str) -> bool {
    let lower = summary.to_lowercase();
    // Match both "## Fixed Issues" and "### Fixed Issues".
    let marker = "fixed issues";
    let pos = lower
        .find(&format!("### {marker}"))
        .or_else(|| lower.find(&format!("## {marker}")));
    let Some(pos) = pos else { return false };
    // Skip past the heading line.
    let after = &lower[pos..];
    let after = after.find('\n').map(|i| &after[i + 1..]).unwrap_or("");
    // Find the next section header or end of string.
    let section_end = after.find("\n#").unwrap_or(after.len());
    let section = after[..section_end].trim();
    if section.is_empty() {
        return false;
    }
    // Strip leading list markers then check "none" variants.
    let stripped = section
        .strip_prefix("- ")
        .or_else(|| section.strip_prefix("* "))
        .unwrap_or(section)
        .trim();
    // Already lowercased so direct comparison is fine.
    ![
        "(none)",
        "none",
        "n/a",
        "(none — no review feedback was generated)",
        "(none -- no review feedback was generated)",
    ]
    .contains(&stripped)
}

fn post_comment(pr_number: u64, body: &str) -> Result<()> {
    if !process::command_exists("gh") {
        if project::is_ci() {
            bail!("gh CLI not found in CI -- cannot post PR comment");
        }
        output::warn("gh CLI not found, skipping PR comment");
        return Ok(());
    }
    let temp = write_temp_file(body)?;
    let pr = pr_number.to_string();
    let result =
        process::run_with_retries("gh", &["pr", "comment", &pr, "--body-file", &temp], 3, 2);
    let _ = std::fs::remove_file(&temp);
    result
}

fn post_decision_comment(
    pr_number: u64,
    iteration: u32,
    made_changes: bool,
    commit_sha: &str,
    summary: &str,
) -> Result<()> {
    let display_iter = iteration + 1;
    let body = if made_changes {
        format!(
            "## Review Response Agent (Iteration {display_iter})\n\
             <!-- agent-metadata:type=review-fix:iteration={display_iter} -->\n\n\
             **Status:** Changes committed, pushing...\n\n\
             **Commit:** `{commit_sha}`\n\n\
             {summary}\n\n---\n\
             *Automated summary of agent fixes.*"
        )
    } else if summary_claims_fixes(summary) {
        // The agent claimed to fix things but no files were actually modified.
        format!(
            "## Review Response Agent (Iteration {display_iter})\n\
             <!-- agent-metadata:type=review-fix:iteration={display_iter} -->\n\n\
             **Status:** No changes needed\n\n\
             > **Warning:** The agent's summary below claims fixes were applied, \
             but no files were actually modified. These claimed fixes were NOT committed.\n\n\
             {summary}\n\n---\n\
             *The agent reviewed feedback but no file modifications were detected.*"
        )
    } else {
        format!(
            "## Review Response Agent (Iteration {display_iter})\n\
             <!-- agent-metadata:type=review-fix:iteration={display_iter} -->\n\n\
             **Status:** No changes needed\n\n\
             {summary}\n\n---\n\
             *The agent reviewed feedback but determined no code changes were required.*"
        )
    };
    post_comment(pr_number, &body)
}

/// Post the explicit hallucination warning comment with a pointer to the
/// stream-json log artifact for post-mortem.
fn post_hallucination_comment(
    pr_number: u64,
    iteration: u32,
    summary: &str,
    stream_log_path: Option<&str>,
) -> Result<()> {
    let display_iter = iteration + 1;
    let log_note = stream_log_path
        .map(|p| {
            format!(
                "\n\n**Stream log:** `{p}`  \n\
                 _Uploaded as the `review-agent-claude-logs` workflow artifact._"
            )
        })
        .unwrap_or_default();

    let body = format!(
        "## Review Response Agent (Iteration {display_iter})\n\
         <!-- agent-metadata:type=review-fix-hallucination:iteration={display_iter} -->\n\n\
         **Status:** Hallucination detected — no commit\n\n\
         > **Detection:** The agent's summary below claims to have applied fixes, \
         > but Claude made **zero** file-mutating tool calls (`Edit` / `Write` / `MultiEdit` / `NotebookEdit`) \
         > during the run. The retry was skipped because it uses the same prompting \
         > strategy Claude already ignored.{log_note}\n\n\
         {summary}\n\n---\n\
         *No file modifications were performed; this iteration produced no commit.*"
    );
    post_comment(pr_number, &body)
}

fn configure_git() -> Result<()> {
    let token = std::env::var("GITHUB_TOKEN").unwrap_or_default();
    let repo = std::env::var("GITHUB_REPOSITORY").unwrap_or_default();
    if !token.is_empty() && !repo.is_empty() {
        output::step("Configuring git authentication...");
        let url = format!("https://x-access-token:{token}@github.com/{repo}.git");
        process::run("git", &["remote", "set-url", "origin", &url])?;
        process::run("git", &["config", "user.name", "AI Review Agent"])?;
        process::run(
            "git",
            &["config", "user.email", "ai-review-agent@localhost"],
        )?;
    }
    Ok(())
}

fn temporarily_disable_pre_push_hook<T, F: FnOnce() -> Result<T>>(f: F) -> Result<T> {
    let hook = Path::new(".git/hooks/pre-push");
    let disabled = Path::new(".git/hooks/pre-push.disabled");
    let had_hook = hook.exists();

    if had_hook {
        std::fs::rename(hook, disabled)?;
        output::info("Disabled pre-push hook temporarily");
    }

    let result = f();

    if had_hook && disabled.exists() {
        let _ = std::fs::rename(disabled, hook);
    }

    result
}

fn truncate_in_place(s: &mut String, max: usize) {
    if s.len() <= max {
        return;
    }
    let original_len = s.len();
    // Find a safe truncation point on a char boundary
    let safe_max = if s.is_char_boundary(max) {
        max
    } else {
        s.floor_char_boundary(max)
    };
    // Find last newline before safe_max
    if let Some(pos) = s[..safe_max].rfind('\n') {
        s.truncate(pos);
    } else {
        s.truncate(safe_max);
    }
    s.push_str(&format!(
        "\n\n[... truncated from {original_len} to {} chars ...]",
        s.len()
    ));
}

fn write_temp_file(content: &str) -> Result<String> {
    let n = TEMP_COUNTER.fetch_add(1, Ordering::Relaxed);
    let path = std::env::temp_dir().join(format!("automation-cli-{}-{n}", std::process::id()));
    std::fs::write(&path, content)?;
    Ok(path.to_string_lossy().to_string())
}

/// Run autoformat via the precommit module and restage changed files.
/// Errors are logged but not fatal -- formatting is best-effort.
fn run_precommit_autoformat() {
    if let Err(e) = super::precommit::run_autoformat_and_restage() {
        output::warn(&format!("Autoformat/restage failed (non-fatal): {e}"));
    }
}

/// Run lint checks and capture error output for agent feedback.
/// Returns the error output string (empty if all checks pass).
fn run_precommit_lint_capture() -> String {
    let stages = ["lint-basic"];
    let mut errors = String::new();

    for stage in &stages {
        match super::precommit::run_ci_stage_captured(stage) {
            Ok(check) if !check.passed => {
                if !errors.is_empty() {
                    errors.push('\n');
                }
                errors.push_str(&format!("### {stage} failures:\n"));
                errors.push_str(&check.error_output);
                errors.push('\n');
            },
            Err(e) => {
                output::warn(&format!("Failed to run {stage}: {e}"));
            },
            _ => {},
        }
    }

    errors
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn summary_claims_fixes_detects_real_fixes() {
        let summary = "### Fixed Issues\n\
                        - **Per-frame allocations**: Added `set_text_if_changed()` helper\n\n\
                        ### Ignored Issues\n- (none)";
        assert!(summary_claims_fixes(summary));
    }

    #[test]
    fn summary_claims_fixes_ignores_none() {
        let summary = "### Fixed Issues\n- (none)\n\n### Ignored Issues\n- style nits";
        assert!(!summary_claims_fixes(summary));
    }

    #[test]
    fn summary_claims_fixes_ignores_empty() {
        let summary = "### Ignored Issues\n- Everything was fine";
        assert!(!summary_claims_fixes(summary));
    }

    #[test]
    fn summary_claims_fixes_case_insensitive_header() {
        let summary = "### fixed issues\n- Fixed a bug\n\n### Ignored Issues\n- (none)";
        assert!(summary_claims_fixes(summary));
    }

    #[test]
    fn summary_claims_fixes_none_variants() {
        for none_val in &[
            "(none)",
            "- (none)",
            "None",
            "- None",
            "N/A",
            "- N/A",
            "(none -- no review feedback was generated)",
            "- (none -- no review feedback was generated)",
        ] {
            let summary = format!("### Fixed Issues\n{none_val}\n\n### Ignored Issues\n- x");
            assert!(
                !summary_claims_fixes(&summary),
                "should be false for: {none_val}"
            );
        }
    }

    #[test]
    fn extract_agent_summary_parses_markers() {
        let output = "Some preamble\n\
                       ---AGENT-SUMMARY-START---\n\
                       ### Fixed Issues\n- a bug\n\
                       ---AGENT-SUMMARY-END---\n\
                       trailing text";
        let summary = extract_agent_summary(output);
        assert!(summary.contains("### Fixed Issues"));
        assert!(summary.contains("- a bug"));
        assert!(!summary.contains("preamble"));
    }

    #[test]
    fn parse_claude_stream_extracts_text_and_edits() {
        let stream = r#"{"type":"system","subtype":"init","session_id":"abc"}
{"type":"assistant","message":{"content":[{"type":"text","text":"Reading the file."}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1","name":"Edit","input":{"file_path":"src/foo.rs","old_string":"a","new_string":"b"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t2","name":"Write","input":{"file_path":"src/bar.rs","content":"hi"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t3","name":"MultiEdit","input":{"file_path":"src/baz.rs","edits":[]}}]}}
{"type":"result","result":"---AGENT-SUMMARY-START---\n### Fixed Issues\n- foo\n---AGENT-SUMMARY-END---"}
"#;
        let (text, edited) = parse_claude_stream(stream);
        assert!(text.contains("Reading the file."));
        assert!(text.contains("---AGENT-SUMMARY-START---"));
        assert_eq!(edited.len(), 3);
        assert!(edited.contains("src/foo.rs"));
        assert!(edited.contains("src/bar.rs"));
        assert!(edited.contains("src/baz.rs"));
    }

    #[test]
    fn parse_claude_stream_ignores_non_mutating_tools() {
        let stream = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","id":"r1","name":"Read","input":{"file_path":"src/foo.rs"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"b1","name":"Bash","input":{"command":"ls"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"g1","name":"Grep","input":{"pattern":"x"}}]}}
"#;
        let (_, edited) = parse_claude_stream(stream);
        assert!(
            edited.is_empty(),
            "Read/Bash/Grep should not count as mutations: {edited:?}"
        );
    }

    #[test]
    fn parse_claude_stream_skips_malformed_lines() {
        let stream = "{not json\n\n{\"type\":\"assistant\",\"message\":{\"content\":[{\"type\":\"text\",\"text\":\"ok\"}]}}\ngarbage trailer\n";
        let (text, edited) = parse_claude_stream(stream);
        assert!(text.contains("ok"));
        assert!(edited.is_empty());
    }

    #[test]
    fn parse_claude_stream_handles_empty_input() {
        let (text, edited) = parse_claude_stream("");
        assert!(text.is_empty());
        assert!(edited.is_empty());
    }

    #[test]
    fn redact_tool_payloads_strips_edit_strings_keeps_metadata() {
        let stream = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1","name":"Edit","input":{"file_path":"src/foo.rs","old_string":"SECRET=ghp_abcdefghijklmnopqrstuvwxyz0123456789","new_string":"SECRET=redacted"}}]}}"#;
        let out = redact_tool_payloads(stream);
        assert!(out.contains("\"file_path\":\"src/foo.rs\""));
        assert!(out.contains("\"name\":\"Edit\""));
        assert!(out.contains("<redacted:"));
        assert!(!out.contains("ghp_abcdefghijklmnopqrstuvwxyz0123456789"));
        assert!(!out.contains("SECRET=redacted"));
    }

    #[test]
    fn redact_tool_payloads_strips_write_content() {
        let stream = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Write","input":{"file_path":"out.txt","content":"line1\nline2\nsecret-here"}}]}}"#;
        let out = redact_tool_payloads(stream);
        assert!(out.contains("\"file_path\":\"out.txt\""));
        assert!(!out.contains("secret-here"));
        assert!(!out.contains("line1"));
        assert!(out.contains("<redacted:"));
    }

    #[test]
    fn redact_tool_payloads_strips_multiedit_array() {
        let stream = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","name":"MultiEdit","input":{"file_path":"a.rs","edits":[{"old_string":"FOO","new_string":"BAR"},{"old_string":"BAZ","new_string":"QUX"}]}}]}}"#;
        let out = redact_tool_payloads(stream);
        assert!(out.contains("\"file_path\":\"a.rs\""));
        // Both edit specs should be present (structure preserved) but content stripped
        assert!(!out.contains("\"FOO\""));
        assert!(!out.contains("\"BAR\""));
        assert!(!out.contains("\"BAZ\""));
        assert!(!out.contains("\"QUX\""));
        // Two redacted markers per edit, two edits = 4 markers minimum
        assert_eq!(out.matches("<redacted:").count(), 4);
    }

    #[test]
    fn redact_tool_payloads_strips_tool_result_string() {
        let stream = r#"{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"file contents with token=ghp_secrettoken1234567890"}]}}"#;
        let out = redact_tool_payloads(stream);
        assert!(out.contains("\"tool_use_id\":\"t1\""));
        assert!(!out.contains("ghp_secrettoken1234567890"));
        assert!(!out.contains("file contents"));
        assert!(out.contains("<redacted:"));
    }

    #[test]
    fn redact_tool_payloads_strips_tool_result_array_text() {
        let stream = r#"{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":[{"type":"text","text":"sensitive output"}]}]}}"#;
        let out = redact_tool_payloads(stream);
        assert!(out.contains("\"tool_use_id\":\"t1\""));
        assert!(!out.contains("sensitive output"));
        assert!(out.contains("<redacted:"));
    }

    #[test]
    fn redact_tool_payloads_keeps_text_blocks_and_bash_command() {
        let stream = r#"{"type":"assistant","message":{"content":[{"type":"text","text":"I will run a command"},{"type":"tool_use","name":"Bash","input":{"command":"ls -la","description":"list"}}]}}"#;
        let out = redact_tool_payloads(stream);
        assert!(out.contains("I will run a command"));
        assert!(out.contains("\"command\":\"ls -la\""));
        // Bash inputs are NOT structurally redacted; SecretMasker handles
        // pattern-based secret redaction afterward.
        assert!(!out.contains("<redacted:"));
    }

    #[test]
    fn redact_tool_payloads_passes_through_non_json_lines() {
        let stream =
            "not json line\n{\"type\":\"system\",\"subtype\":\"init\"}\nanother garbage line";
        let out = redact_tool_payloads(stream);
        assert!(out.contains("not json line"));
        assert!(out.contains("\"system\""));
        assert!(out.contains("another garbage line"));
    }

    #[test]
    fn redact_tool_payloads_preserves_assistant_text_for_summary_extraction() {
        // The summary marker lives in assistant text blocks; it MUST survive
        // redaction so extract_agent_summary still works on the saved log.
        let stream = r#"{"type":"assistant","message":{"content":[{"type":"text","text":"---AGENT-SUMMARY-START---\n### Fixed Issues\n- foo\n---AGENT-SUMMARY-END---"}]}}"#;
        let out = redact_tool_payloads(stream);
        assert!(out.contains("---AGENT-SUMMARY-START---"));
        assert!(out.contains("---AGENT-SUMMARY-END---"));
    }

    #[test]
    fn redacted_marker_records_size() {
        let v = serde_json::Value::String("12345".to_string());
        assert_eq!(redacted_marker(&v), "<redacted: 5 chars>");
    }

    #[test]
    fn parse_claude_stream_dedupes_repeated_edits() {
        let stream = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"a.rs"}}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","input":{"file_path":"a.rs"}}]}}
"#;
        let (_, edited) = parse_claude_stream(stream);
        assert_eq!(edited.len(), 1);
        assert!(edited.contains("a.rs"));
    }

    #[test]
    fn parse_ls_remote_sha_basic() {
        let out = "abc123def456abc123def456abc123def456abcd\trefs/heads/main\n";
        assert_eq!(
            parse_ls_remote_sha(out).as_deref(),
            Some("abc123def456abc123def456abc123def456abcd")
        );
    }

    #[test]
    fn parse_ls_remote_sha_empty() {
        assert_eq!(parse_ls_remote_sha(""), None);
    }

    #[test]
    fn parse_ls_remote_sha_whitespace_only() {
        assert_eq!(parse_ls_remote_sha("   \n"), None);
    }

    #[test]
    fn parse_ls_remote_sha_first_line_only() {
        // Multiple refs: take the first refs/heads/ line's SHA.
        let out = "aaa\trefs/heads/feature\nbbb\trefs/heads/main\n";
        assert_eq!(parse_ls_remote_sha(out).as_deref(), Some("aaa"));
    }

    #[test]
    fn parse_ls_remote_sha_no_branch_ref() {
        let out = "abc123\trefs/tags/v1.0\n";
        assert_eq!(parse_ls_remote_sha(out), None);
    }

    #[test]
    fn looks_like_non_fast_forward_matches() {
        assert!(looks_like_non_fast_forward(
            "! [rejected]        main -> main (non-fast-forward)"
        ));
        assert!(looks_like_non_fast_forward(
            "error: failed to push some refs; updates were rejected"
        ));
        assert!(looks_like_non_fast_forward(
            "hint: Updates were rejected because the tip of your current branch is behind -- fetch first"
        ));
        assert!(!looks_like_non_fast_forward(
            "fatal: unable to access: could not resolve host"
        ));
    }

    #[test]
    fn extract_agent_summary_fallback() {
        let output = "line 1\nline 2\nline 3\n";
        let summary = extract_agent_summary(output);
        assert!(summary.contains("line 1"));
    }
}
