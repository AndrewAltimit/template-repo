use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use anyhow::{Result, bail};
use clap::Args;

use crate::shared::{output, process, project};

static TEMP_COUNTER: AtomicU64 = AtomicU64::new(0);

/// Error extraction limits
const MAX_LINT_ERROR_LINES: usize = 150;
const MAX_TEST_ERROR_LINES: usize = 100;

#[derive(Args)]
pub struct FailureArgs {
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
    /// Comma-separated failure types to handle (format,lint,test)
    #[arg(default_value = "format,lint")]
    pub failure_types: String,
}

pub fn run(args: FailureArgs) -> Result<()> {
    let root = project::find_project_root()?;
    std::env::set_current_dir(&root)?;

    output::header("Agent Failure Handler");
    output::info(&format!("PR Number: {}", args.pr_number));
    output::info(&format!("Branch: {}", args.branch));
    output::info(&format!(
        "Iteration: {} / {}",
        args.iteration, args.max_iterations
    ));
    output::info(&format!("Handling failure types: {}", args.failure_types));

    // Max iterations check
    if args.iteration >= args.max_iterations {
        output::fail(&format!(
            "Maximum iterations ({}) reached! Manual intervention required.",
            args.max_iterations
        ));
        project::set_github_output("exceeded_max", "true");
        project::set_github_output("made_changes", "false");
        bail!("max iterations exceeded");
    }

    if !Path::new(".git").exists() {
        bail!("not in a git repository");
    }

    // Configure git
    configure_git()?;

    // Checkout branch
    output::step(&format!("Checking out branch: {}", args.branch));
    let _ = process::run("git", &["fetch", "origin", &args.branch]);
    let _ = process::run("git", &["checkout", &args.branch]);

    // Detect failures from env vars or failure_types
    let format_failed = std::env::var("FORMAT_CHECK_RESULT")
        .map(|v| v == "failure")
        .unwrap_or(false);
    let basic_lint_failed = std::env::var("BASIC_LINT_RESULT")
        .map(|v| v == "failure")
        .unwrap_or(false);
    let full_lint_failed = std::env::var("FULL_LINT_RESULT")
        .map(|v| v == "failure")
        .unwrap_or(false);
    let test_failed = std::env::var("TEST_SUITE_RESULT")
        .map(|v| v == "failure")
        .unwrap_or(false);

    let mut lint_failures = Vec::new();
    let mut has_test_failure = false;

    if format_failed {
        lint_failures.push("format");
    }
    if basic_lint_failed {
        lint_failures.push("basic-lint");
    }
    if full_lint_failed {
        lint_failures.push("full-lint");
    }
    if test_failed {
        has_test_failure = true;
    }

    // Fallback: infer from failure_types
    if lint_failures.is_empty() && !has_test_failure {
        if args.failure_types.contains("format") || args.failure_types.contains("lint") {
            lint_failures.extend(["format", "lint"]);
        }
        if args.failure_types.contains("test") {
            has_test_failure = true;
        }
    }

    if lint_failures.is_empty() && !has_test_failure {
        output::info("No handleable failures detected");
        project::set_github_output("made_changes", "false");
        return Ok(());
    }

    output::info(&format!(
        "Failures to address: {} {}",
        lint_failures.join(", "),
        if has_test_failure { "test-suite" } else { "" }
    ));

    // Step 1: Autoformat
    output::header("Step 1: Running autoformat");
    let _ = process::run("./automation/ci-cd/run-ci.sh", &["autoformat"]);
    process::run("git", &["add", "-A"])?;

    // Step 2: Capture remaining lint errors
    output::header("Step 2: Checking for remaining lint issues");
    let lint_output = capture_lint_errors(&lint_failures)?;
    let test_output = if has_test_failure {
        output::header("Step 2b: Capturing test failure output");
        capture_test_errors()?
    } else {
        String::new()
    };

    // Step 3: Invoke Claude
    output::header("Step 3: Invoking Claude for remaining issues");
    let prompt = build_failure_prompt(&lint_failures, &lint_output, has_test_failure, &test_output);

    let prompt_file = write_temp_file(&prompt)?;
    output::info(&format!("Prompt size: {} chars", prompt.len()));

    let claude_cmd = if process::command_exists("claude") {
        Some("claude")
    } else if process::command_exists("claude-code") {
        Some("claude-code")
    } else {
        output::warn("Claude CLI not found, proceeding with autoformat changes only");
        None
    };

    if let Some(cmd) = claude_cmd {
        output::step("Running Claude with 20 min timeout...");
        let prompt_path = Path::new(&prompt_file);
        let result = process::run_capture_with_timeout(
            cmd,
            &["--print", "--dangerously-skip-permissions", "-p"],
            prompt_path,
            Duration::from_secs(20 * 60),
        );
        let _ = std::fs::remove_file(&prompt_file);
        match result {
            Ok(stdout) => {
                if !stdout.is_empty() {
                    eprintln!("{stdout}");
                }
            },
            Err(e) => {
                output::warn(&format!("Claude invocation failed: {e}"));
            },
        }
    } else {
        let _ = std::fs::remove_file(&prompt_file);
    }

    // Step 4: Commit
    output::header("Step 4: Checking for changes");
    process::run("git", &["add", "-A"])?;

    if process::run_check("git", &["diff", "--cached", "--quiet"])? {
        output::info("No changes to commit");
        post_comment(
            args.pr_number,
            &format_handler_comment(args.iteration, false, "", ""),
        )?;
        project::set_github_output("made_changes", "false");
        return Ok(());
    }

    output::step("Changes detected, creating commit...");
    let failures_list: String = lint_failures
        .iter()
        .chain(if has_test_failure {
            vec![&"test-suite"]
        } else {
            vec![]
        })
        .map(|f| format!("- {f}"))
        .collect::<Vec<_>>()
        .join("\n");

    let display_iter = args.iteration + 1;
    let commit_msg = format!(
        "fix: resolve CI pipeline failures\n\n\
         Automated fix by Claude in response to pipeline failures.\n\n\
         Failures addressed:\n{failures_list}\n\n\
         Actions taken:\n\
         - Ran autoformat (ruff format, cargo fmt)\n\
         - Fixed remaining lint issues\n\n\
         Iteration: {display_iter}/{}\n\n\
         Co-Authored-By: AI Pipeline Agent <noreply@anthropic.com>",
        args.max_iterations
    );
    let msg_file = write_temp_file(&commit_msg)?;
    process::run("git", &["commit", "-F", &msg_file])?;
    let _ = std::fs::remove_file(&msg_file);

    // Step 5: Push
    output::header("Step 5: Pushing changes");
    let sha = process::run_capture("git", &["rev-parse", "--short", "HEAD"])?;
    let sha = sha.trim();

    // Post comment BEFORE pushing
    post_comment(
        args.pr_number,
        &format_handler_comment(args.iteration, true, sha, &failures_list),
    )?;

    let branch = args.branch.clone();
    let push_result = temporarily_disable_pre_push_hook(|| {
        process::run_with_retries("git", &["push", "origin", &branch], 3, 2)
    });

    if let Err(e) = push_result {
        let _ = post_comment(
            args.pr_number,
            &format!(
                "**Push failed** after retries: `{e}`\n\n\
                 The commit exists locally but was not pushed. Manual intervention required."
            ),
        );
        return Err(e);
    }

    output::success(&format!("Changes pushed to branch: {}", args.branch));
    project::set_github_output("made_changes", "true");
    Ok(())
}

fn capture_lint_errors(failures: &[&str]) -> Result<String> {
    let mut output = String::new();

    let has_basic = failures
        .iter()
        .any(|f| *f == "basic-lint" || *f == "lint" || *f == "format");
    let has_full = failures
        .iter()
        .any(|f| *f == "full-lint" || *f == "lint-full");

    let stages: Vec<(&str, &str)> = if has_full && has_basic {
        vec![("lint-basic", "lint-basic"), ("lint-full", "lint-full")]
    } else if has_full {
        vec![("lint-full", "lint-full")]
    } else if has_basic {
        vec![("lint-basic", "lint-basic")]
    } else {
        vec![]
    };

    for (label, arg) in stages {
        output::step(&format!("Capturing {label} errors..."));
        if let Ok(raw) = std::process::Command::new("./automation/ci-cd/run-ci.sh")
            .arg(arg)
            .output()
        {
            let stdout = String::from_utf8_lossy(&raw.stdout);
            let stderr = String::from_utf8_lossy(&raw.stderr);
            let combined = format!("{stdout}{stderr}");
            let errors: Vec<&str> = combined
                .lines()
                .filter(|l| {
                    l.contains(": error")
                        || l.contains(": warning")
                        || l.contains("Error:")
                        || l.contains("FAILED")
                        || l.contains("Found ")
                })
                .take(MAX_LINT_ERROR_LINES)
                .collect();
            if !errors.is_empty() {
                if !output.is_empty() {
                    output.push('\n');
                }
                output.push_str(&errors.join("\n"));
            }
        }
    }
    Ok(output)
}

fn capture_test_errors() -> Result<String> {
    output::step("Running tests to capture failure details...");
    if let Ok(raw) = std::process::Command::new("./automation/ci-cd/run-ci.sh")
        .arg("test")
        .output()
    {
        let stdout = String::from_utf8_lossy(&raw.stdout);
        let stderr = String::from_utf8_lossy(&raw.stderr);
        let combined = format!("{stdout}{stderr}");
        let errors: Vec<&str> = combined
            .lines()
            .filter(|l| {
                l.contains("FAILED")
                    || l.contains("AssertionError")
                    || l.contains("Error:")
                    || l.contains("Traceback")
            })
            .take(MAX_TEST_ERROR_LINES)
            .collect();
        return Ok(errors.join("\n"));
    }
    Ok(String::new())
}

fn build_failure_prompt(
    lint_failures: &[&str],
    lint_output: &str,
    has_test: bool,
    test_output: &str,
) -> String {
    let mut prompt = "You are fixing CI/CD pipeline failures for a pull request.\n\n".to_string();

    if !lint_failures.is_empty() {
        prompt.push_str("## Lint/Format Failures Detected\n\n");
        prompt.push_str("INSTRUCTIONS:\n");
        prompt.push_str("1. Fix unused imports, formatting issues, type hints\n");
        prompt.push_str("2. Make minimal changes - only what's needed to pass CI\n");
        prompt.push_str("3. The autoformat tools have already been run\n\n");
        if !lint_output.is_empty() {
            prompt.push_str(&format!("### Lint Output:\n{lint_output}\n\n"));
        }
    }

    if has_test {
        prompt.push_str("## Test Failures Detected\n\n");
        prompt.push_str("INSTRUCTIONS:\n");
        prompt.push_str("1. Analyze the test output to understand what's failing\n");
        prompt.push_str("2. Fix bugs in the CODE being tested, not the tests\n");
        prompt.push_str("3. Do NOT disable, skip, or delete failing tests\n");
        prompt.push_str("4. Make minimal, targeted fixes\n\n");
        if !test_output.is_empty() {
            prompt.push_str(&format!("### Test Output:\n{test_output}\n\n"));
        }
    }

    prompt.push_str("Please analyze and fix the issues above.\n");
    prompt.push_str("After making changes, provide a brief summary of what was fixed.\n");
    prompt
}

fn format_handler_comment(iteration: u32, made_changes: bool, sha: &str, failures: &str) -> String {
    let next = iteration + 1;
    if made_changes {
        format!(
            "## Failure Handler Agent (Iteration {next})\n\
             <!-- agent-metadata:type=failure-fix:iteration={next} -->\n\n\
             **Status:** Changes committed, pushing...\n\n\
             **Commit:** `{sha}`\n\n\
             **Failures addressed:**\n{failures}\n\n---\n\
             *Automated fix in response to CI pipeline failures.*"
        )
    } else {
        format!(
            "## Failure Handler Agent (Iteration {next})\n\
             <!-- agent-metadata:type=failure-fix:iteration={next} -->\n\n\
             **Status:** No changes needed\n\n\
             The agent analyzed the failures but no automated fixes could be applied.\n\n---\n\
             *Manual intervention may be required.*"
        )
    }
}

fn post_comment(pr_number: u64, body: &str) -> Result<()> {
    if !process::command_exists("gh") {
        if project::is_ci() {
            bail!("gh CLI not found in CI -- cannot post PR comment");
        }
        return Ok(());
    }
    let temp = write_temp_file(body)?;
    let pr = pr_number.to_string();
    let result =
        process::run_with_retries("gh", &["pr", "comment", &pr, "--body-file", &temp], 3, 2);
    let _ = std::fs::remove_file(&temp);
    result
}

fn configure_git() -> Result<()> {
    let token = std::env::var("GITHUB_TOKEN").unwrap_or_default();
    let repo = std::env::var("GITHUB_REPOSITORY").unwrap_or_default();
    if !token.is_empty() && !repo.is_empty() {
        let url = format!("https://x-access-token:{token}@github.com/{repo}.git");
        process::run("git", &["remote", "set-url", "origin", &url])?;
        process::run("git", &["config", "user.name", "AI Pipeline Agent"])?;
        process::run(
            "git",
            &["config", "user.email", "ai-pipeline-agent@localhost"],
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
    }

    let result = f();

    if had_hook && disabled.exists() {
        let _ = std::fs::rename(disabled, hook);
    }

    result
}

fn write_temp_file(content: &str) -> Result<String> {
    let n = TEMP_COUNTER.fetch_add(1, Ordering::Relaxed);
    let path =
        std::env::temp_dir().join(format!("automation-cli-failure-{}-{n}", std::process::id()));
    std::fs::write(&path, content)?;
    Ok(path.to_string_lossy().to_string())
}
