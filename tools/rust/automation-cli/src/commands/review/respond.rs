use std::path::Path;

use anyhow::{Result, bail};
use clap::Args;

use super::trust::{TrustConfig, TrustLevel};
use crate::shared::{output, process, project};

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
        project::set_github_output("made_changes", "false");
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
        output::info("No changes to commit");
        post_decision_comment(args.pr_number, args.iteration, false, "", &summary)?;
        project::set_github_output("made_changes", "false");
        return Ok(());
    }

    // Commit
    output::step("Changes detected, creating commit...");
    let commit_msg = format!(
        "fix: address AI review feedback (iteration {})\n\n\
         Automated fix by Claude in response to Gemini/Codex review.\n\n\
         Iteration: {}/{}\n\n\
         Co-Authored-By: AI Review Agent <noreply@anthropic.com>",
        args.iteration, args.iteration, args.max_iterations
    );
    let msg_file = write_temp_file(&commit_msg)?;
    process::run("git", &["commit", "-F", &msg_file])?;
    let _ = std::fs::remove_file(&msg_file);

    // Get commit SHA and post comment BEFORE pushing
    let commit_sha = process::run_capture("git", &["rev-parse", "--short", "HEAD"])?;
    let commit_sha = commit_sha.trim();

    post_decision_comment(args.pr_number, args.iteration, true, commit_sha, &summary)?;

    // Push
    output::header("Step 4: Pushing changes");
    temporarily_disable_pre_push_hook(|| process::run("git", &["push", "origin", &args.branch]))?;

    output::success(&format!("Changes pushed to branch: {}", args.branch));
    project::set_github_output("made_changes", "true");
    Ok(())
}

fn collect_review_content(content: &mut String) -> Result<()> {
    let gemini_path =
        std::env::var("GEMINI_REVIEW_PATH").unwrap_or_else(|_| "gemini-review.md".to_string());
    let codex_path =
        std::env::var("CODEX_REVIEW_PATH").unwrap_or_else(|_| "codex-review.md".to_string());

    if let Ok(text) = std::fs::read_to_string(&gemini_path) {
        output::info(&format!("Found Gemini review at: {gemini_path}"));
        content.push_str("## Gemini Review Feedback\n\n");
        content.push_str(&text);
        content.push_str("\n\n");
    }
    if let Ok(text) = std::fs::read_to_string(&codex_path) {
        output::info(&format!("Found Codex review at: {codex_path}"));
        content.push_str("## Codex Review Feedback\n\n");
        content.push_str(&text);
        content.push_str("\n\n");
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

        // Skip AI review markers
        if body.contains("<!-- gemini-review-marker") || body.contains("<!-- codex-review-marker") {
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
         4. **Fix or skip** - Fix real issues; skip theoretical ones\n\n",
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

    output::step("Running Claude with tool access...");
    let prompt_file = write_temp_file(prompt)?;

    // Run Claude with stdin from file
    let output = std::process::Command::new(claude_cmd)
        .args(["--dangerously-skip-permissions"])
        .stdin(std::fs::File::open(&prompt_file)?)
        .output()?;

    let _ = std::fs::remove_file(&prompt_file);
    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

fn extract_agent_summary(output: &str) -> String {
    let start_marker = "---AGENT-SUMMARY-START---";
    let end_marker = "---AGENT-SUMMARY-END---";

    if let Some(start) = output.find(start_marker) {
        if let Some(end) = output[start..].find(end_marker) {
            let summary = &output[start + start_marker.len()..start + end];
            return summary.trim().to_string();
        }
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

fn post_comment(pr_number: u64, body: &str) -> Result<()> {
    if !process::command_exists("gh") {
        output::warn("gh CLI not found, skipping PR comment");
        return Ok(());
    }
    let temp = write_temp_file(body)?;
    let result = process::run(
        "gh",
        &[
            "pr",
            "comment",
            &pr_number.to_string(),
            "--body-file",
            &temp,
        ],
    );
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
    let next_iter = iteration + 1;
    let body = if made_changes {
        format!(
            "## Review Response Agent (Iteration {next_iter})\n\
             <!-- agent-metadata:type=review-fix:iteration={next_iter} -->\n\n\
             **Status:** Changes committed and pushed\n\n\
             **Commit:** `{commit_sha}`\n\n\
             {summary}\n\n---\n\
             *Automated summary of agent fixes.*"
        )
    } else {
        format!(
            "## Review Response Agent (Iteration {next_iter})\n\
             <!-- agent-metadata:type=review-fix:iteration={next_iter} -->\n\n\
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

fn temporarily_disable_pre_push_hook<F: FnOnce() -> Result<()>>(f: F) -> Result<()> {
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
    let path = std::env::temp_dir().join(format!("automation-cli-{}", std::process::id()));
    std::fs::write(&path, content)?;
    Ok(path.to_string_lossy().to_string())
}
