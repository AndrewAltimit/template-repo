use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use anyhow::{Result, bail};
use clap::Args;

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

    // Step 1: Run autoformat
    output::header("Step 1: Running autoformat");
    let _ = process::run("./automation/ci-cd/run-ci.sh", &["autoformat"]);

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

    let claude_output = run_claude(&prompt)?;

    // Step 3: Check for changes
    output::header("Step 3: Checking for changes");
    process::run("git", &["add", "-A"])?;

    let has_changes = !process::run_check("git", &["diff", "--cached", "--quiet"])?;

    let summary = extract_agent_summary(&claude_output);

    if !has_changes {
        // Detect hallucinated fixes: Claude's summary claims "Fixed Issues" but no files
        // were actually modified. Retry once with a pointed correction prompt.
        if summary_claims_fixes(&summary) {
            output::warn("Agent summary claims fixed issues but no files were modified — retrying");

            let retry_prompt = format!(
                "Your previous response claimed to fix issues but did NOT actually modify any files.\n\n\
                 Your summary said:\n{summary}\n\n\
                 However, `git diff` shows zero changes. You MUST use the Edit tool to \
                 actually modify the source files, not just describe the changes.\n\n\
                 Please re-read the relevant files and apply the fixes now. If you determine \
                 the issues don't need fixing, move them to \"Ignored Issues\" instead of \
                 \"Fixed Issues\".\n\n\
                 ## Review Feedback\n\n{review_content}\n\n\
                 ## REQUIRED: Output Summary Format\n\n\
                 ---AGENT-SUMMARY-START---\n\
                 ### Fixed Issues\n- ...\n\
                 ### Ignored Issues\n- ...\n\
                 ### Deferred to Human\n- ...\n\
                 ### Notes\n- ...\n\
                 ---AGENT-SUMMARY-END---\n"
            );

            let retry_output = run_claude(&retry_prompt)?;
            process::run("git", &["add", "-A"])?;
            let retry_has_changes = !process::run_check("git", &["diff", "--cached", "--quiet"])?;
            let retry_summary = extract_agent_summary(&retry_output);

            if retry_has_changes {
                output::info("Retry produced actual file changes");
                // Fall through to the commit/push path below with the retry summary
                return commit_and_push(
                    &args,
                    &if retry_summary.is_empty() {
                        summary
                    } else {
                        retry_summary
                    },
                );
            }

            // Still no changes after retry — post with explicit warning
            let warning_summary = if retry_summary.is_empty() {
                summary.clone()
            } else {
                retry_summary
            };
            output::warn("Retry still produced no file changes");
            post_decision_comment(args.pr_number, args.iteration, false, "", &warning_summary)?;
            report_no_commit();
            return Ok(());
        }

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
         Automated fix by Claude in response to Gemini/Codex review.\n\n\
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
    output::header("Step 4: Pushing changes");
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
    msg.contains("non-fast-forward")
        || msg.contains("fetch first")
        || msg.contains("updates were rejected")
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
    let out = process::run_capture("git", &["ls-remote", "origin", branch])?;
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
        .or_else(|| output.lines().next().and_then(extract_sha))
}

/// Persist the unpushed commit as a `.patch` file in `$RUNNER_TEMP/review-agent-patches/`
/// so the workflow can upload it as an artifact for manual recovery.
fn save_commit_patch(sha: &str) -> Result<String> {
    let base = std::env::var("RUNNER_TEMP")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(std::env::temp_dir);
    let dir = base.join("review-agent-patches");
    std::fs::create_dir_all(&dir)?;
    let short_end = sha.len().min(12);
    let path = dir.join(format!("unpushed-{}.patch", &sha[..short_end]));
    let patch = process::run_capture("git", &["format-patch", "-1", "HEAD", "--stdout"])?;
    std::fs::write(&path, patch)?;
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

    if args.iteration >= 3 {
        prompt.push_str(
            "**IMPORTANT: This PR has already been through multiple review cycles.**\n\
             At this point, only fix issues that meet the HIGH SEVERITY threshold:\n\
             - Security vulnerabilities (injection, auth bypass, data exposure)\n\
             - Crashes or data corruption bugs\n\
             - Build/test failures\n\n\
             Do NOT fix: minor style issues, speculative edge cases, theoretical improvements.\n\n",
        );
    }

    prompt.push_str(
        "## Your Task\n\
         Review the feedback from Gemini and Codex below, and fix legitimate issues.\n\n\
         ## How to Work\n\
         1. **Read the files first** - Use the Read tool to examine any file mentioned\n\
         2. **Verify claims** - Check if the reported issue actually exists\n\
         3. **Assess severity** - Is this a real bug or speculative?\n\
         4. **Fix or skip** - Fix real issues; skip theoretical ones\n\n\
         ## CRITICAL: You MUST Actually Edit Files\n\
         If you decide to fix an issue, you MUST use the Edit or Write tool to modify \
         the source files. Do NOT just describe or plan changes — apply them. \
         If you list something under \"Fixed Issues\" in your summary, the corresponding \
         file MUST have been modified by an Edit or Write tool call. \
         If you cannot or choose not to modify a file, list that issue under \
         \"Ignored Issues\" or \"Deferred to Human\" instead.\n\n",
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

fn run_claude(prompt: &str) -> Result<String> {
    let claude_cmd = if process::command_exists("claude") {
        "claude"
    } else if process::command_exists("claude-code") {
        "claude-code"
    } else {
        output::warn("Claude CLI not found, skipping AI-assisted fixes");
        return Ok(String::new());
    };

    output::step("Running Claude with tool access (20 min timeout)...");
    let prompt_file = write_temp_file(prompt)?;
    let prompt_path = Path::new(&prompt_file);

    let result = process::run_capture_with_timeout(
        claude_cmd,
        &["--dangerously-skip-permissions"],
        prompt_path,
        Duration::from_secs(20 * 60),
    );

    let _ = std::fs::remove_file(&prompt_file);
    result
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
        // Multiple refs: take the first line's SHA.
        let out = "aaa\trefs/heads/feature\nbbb\trefs/heads/main\n";
        assert_eq!(parse_ls_remote_sha(out).as_deref(), Some("aaa"));
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
