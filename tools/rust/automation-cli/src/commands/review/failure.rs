//! `automation-cli review failure`: autoformat, then ask Claude to fix the
//! remaining lint/test failures of a PR pipeline, commit, and push.
//!
//! GitHub outputs: `exceeded_max`, `made_changes`, `pushed`, `commit_sha`.

use anyhow::{Result, bail};
use clap::Args;

use super::common::{self, CLAUDE_TIMEOUT};
use super::precommit::{Gate, LINT_CMD_ENV, TEST_CMD_ENV};
use crate::shared::{output, process, project};

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

/// Which failures this run should address.
#[derive(Debug, Default, PartialEq, Eq)]
struct Failures {
    /// Lint-ish failure labels (`format`, `basic-lint`, `full-lint`, `lint`).
    lint: Vec<&'static str>,
    test: bool,
}

impl Failures {
    fn is_empty(&self) -> bool {
        self.lint.is_empty() && !self.test
    }

    /// Detect failures from the workflow's job-result env vars, falling back
    /// to the comma-separated `failure_types` argument.
    fn detect(env: impl Fn(&str) -> Option<String>, failure_types: &str) -> Self {
        let failed = |var: &str| env(var).is_some_and(|v| v == "failure");
        let mut f = Failures::default();
        if failed("FORMAT_CHECK_RESULT") {
            f.lint.push("format");
        }
        if failed("BASIC_LINT_RESULT") {
            f.lint.push("basic-lint");
        }
        if failed("FULL_LINT_RESULT") {
            f.lint.push("full-lint");
        }
        f.test = failed("TEST_SUITE_RESULT");

        if f.is_empty() {
            let types: Vec<&str> = failure_types.split(',').map(str::trim).collect();
            if types.iter().any(|t| matches!(*t, "format" | "lint")) {
                f.lint.extend(["format", "lint"]);
            }
            f.test = types.contains(&"test");
        }
        f
    }

    /// Bullet list for the commit message and PR comment.
    fn bullet_list(&self) -> String {
        self.lint
            .iter()
            .copied()
            .chain(self.test.then_some("test-suite"))
            .map(|f| format!("- {f}"))
            .collect::<Vec<_>>()
            .join("\n")
    }

    /// CI stages whose output is captured to show Claude the remaining errors.
    fn lint_stages(&self) -> Vec<&'static str> {
        let basic = self
            .lint
            .iter()
            .any(|f| matches!(*f, "basic-lint" | "lint" | "format"));
        let full = self.lint.contains(&"full-lint");
        let mut stages = Vec::new();
        if basic {
            stages.push("lint-basic");
        }
        if full {
            stages.push("lint-full");
        }
        stages
    }
}

pub fn run(args: FailureArgs) -> Result<()> {
    project::enter_project_root()?;

    output::header("Agent Failure Handler");
    output::info(&format!("PR Number: {}", args.pr_number));
    output::info(&format!("Branch: {}", args.branch));
    output::info(&format!(
        "Iteration: {} / {}",
        args.iteration, args.max_iterations
    ));
    output::info(&format!("Handling failure types: {}", args.failure_types));

    if args.iteration >= args.max_iterations {
        output::fail(&format!(
            "Maximum iterations ({}) reached! Manual intervention required.",
            args.max_iterations
        ));
        project::set_github_output("exceeded_max", "true");
        report_no_commit();
        bail!("max iterations exceeded");
    }

    if !std::path::Path::new(".git").exists() {
        bail!("not in a git repository");
    }

    common::configure_git("AI Pipeline Agent", "ai-pipeline-agent@localhost")?;
    common::checkout_branch(&args.branch)?;

    let failures = Failures::detect(|k| std::env::var(k).ok(), &args.failure_types);
    if failures.is_empty() {
        output::info("No handleable failures detected");
        report_no_commit();
        return Ok(());
    }
    let failures_list = failures.bullet_list();
    output::info(&format!("Failures to address:\n{failures_list}"));

    output::header("Step 1: Running autoformat");
    if let Err(e) = super::precommit::run_autoformat_and_restage() {
        output::warn(&format!("Autoformat/restage failed (non-fatal): {e}"));
    }

    output::header("Step 2: Checking for remaining lint issues");
    let lint_gate = if failures.lint.is_empty() {
        Gate::Skip
    } else {
        Gate::from_process_env(LINT_CMD_ENV, &failures.lint_stages())
    };
    let lint_output =
        capture_gate_errors(&lint_gate, LINT_CMD_ENV, MAX_LINT_ERROR_LINES, is_lint_line);
    let test_output = if failures.test {
        output::header("Step 2b: Capturing test failure output");
        let test_gate = Gate::from_process_env(TEST_CMD_ENV, &["test"]);
        capture_gate_errors(&test_gate, TEST_CMD_ENV, MAX_TEST_ERROR_LINES, is_test_line)
    } else {
        String::new()
    };

    output::header("Step 3: Invoking Claude for remaining issues");
    let prompt = build_failure_prompt(&failures, &lint_output, &test_output);
    output::info(&format!("Prompt size: {} chars", prompt.len()));
    invoke_claude(&prompt)?;

    output::header("Step 4: Checking for changes");
    if !common::stage_tracked_changes()? {
        output::info("No changes to commit");
        common::post_comment(
            args.pr_number,
            &format_handler_comment(args.iteration, false, "", ""),
        )?;
        report_no_commit();
        return Ok(());
    }

    output::step("Changes detected, creating commit...");
    common::commit(&commit_message(&failures_list, &args))?;
    let (full_sha, short_sha) = common::head_sha()?;

    // Post the comment BEFORE pushing: the push triggers a new pipeline run
    // which cancels this one.
    output::header("Step 5: Pushing changes");
    common::post_comment(
        args.pr_number,
        &format_handler_comment(args.iteration, true, &short_sha, &failures_list),
    )?;

    project::set_github_output("made_changes", "true");
    match common::push_and_verify(&args.branch, &full_sha) {
        Ok(landed) => {
            output::success(&format!("Changes pushed to branch: {}", args.branch));
            project::set_github_output("pushed", "true");
            project::set_github_output("commit_sha", &landed);
            Ok(())
        },
        Err(e) => {
            let _ = common::post_comment(
                args.pr_number,
                &format!(
                    "**Push failed** after retries: `{e}`\n\n\
                     The commit exists locally but was not pushed. Manual intervention required."
                ),
            );
            project::set_github_output("pushed", "false");
            project::set_github_output("commit_sha", &full_sha);
            Err(e)
        },
    }
}

fn report_no_commit() {
    project::set_github_output("made_changes", "false");
    project::set_github_output("pushed", "false");
    project::set_github_output("commit_sha", "");
}

/// Run Claude on the prompt (if the CLI is installed), echoing its output.
/// A failed or timed-out invocation is a warning: autoformat changes may
/// still be worth committing.
fn invoke_claude(prompt: &str) -> Result<()> {
    let Some(cmd) = common::find_claude_cli() else {
        output::warn("Claude CLI not found, proceeding with autoformat changes only");
        return Ok(());
    };
    output::step("Running Claude with 20 min timeout...");
    let prompt_file = common::write_temp(prompt)?;
    match process::run_capture_with_timeout(
        cmd,
        &["-p", "--dangerously-skip-permissions"],
        prompt_file.path(),
        CLAUDE_TIMEOUT,
    ) {
        Ok(stdout) if !stdout.is_empty() => eprintln!("{stdout}"),
        Ok(_) => {},
        Err(e) => output::warn(&format!("Claude invocation failed: {e}")),
    }
    Ok(())
}

/// Run a gate and collect the error lines `keep` selects. Checks that cannot
/// run in this repository are logged and skipped rather than sent to Claude.
/// `env_var` names the override for this gate, for the "not available" hint.
fn capture_gate_errors(
    gate: &Gate,
    env_var: &str,
    max_lines: usize,
    keep: fn(&str) -> bool,
) -> String {
    let mut out = String::new();
    for check in gate.run_captured() {
        output::step(&format!("Capturing {} errors...", check.name));
        if check.unavailable {
            output::warn(&format!(
                "'{}' is not available in this repository; skipping. Set {env_var} to \
                 this repo's command (or to an empty string to skip)",
                check.name
            ));
            continue;
        }
        let mut lines = filter_lines(&check.raw_output, max_lines, keep);
        if lines.is_empty() && !check.passed {
            // The filter knows ruff/pytest/rustc shapes; for any other tool
            // fall back to the generic extract (error lines, else the tail)
            // so Claude never gets a failed gate with no output.
            lines = filter_lines(&check.error_output, max_lines, |_| true);
        }
        if !lines.is_empty() {
            if !out.is_empty() {
                out.push('\n');
            }
            out.push_str(&lines);
        }
    }
    out
}

/// rustc error lines: `error: ...` and `error[E0308]: ...`.
fn is_rust_error(l: &str) -> bool {
    let t = l.trim_start();
    t.starts_with("error:") || t.starts_with("error[")
}

/// rustc/clippy diagnostic lines: errors, `warning: ...`, and the
/// ` --> file:line:col` location that follows them.
fn is_rust_diagnostic(l: &str) -> bool {
    let t = l.trim_start();
    is_rust_error(l) || t.starts_with("warning:") || t.starts_with("--> ")
}

/// Lint lines worth showing Claude: ruff/flake8 (`file:1:1: F401`, `Found N
/// errors`) and rustc/clippy diagnostics.
fn is_lint_line(l: &str) -> bool {
    l.contains(": error")
        || l.contains(": warning")
        || l.contains("Error:")
        || l.contains("FAILED")
        || l.contains("Found ")
        || is_rust_diagnostic(l)
}

/// Test failure lines: pytest and `cargo test` (`... FAILED`, panics, and
/// compile errors). Compiler warnings and their `-->` locations are left out:
/// they precede the test results and would fill the line cap, pushing out
/// the failures Claude actually needs.
fn is_test_line(l: &str) -> bool {
    l.contains("FAILED")
        // pytest collection errors: the "ERROR collecting <file>" header and
        // the "ERROR <file> - ..." short-summary line name the broken file.
        || l.contains("ERROR collecting")
        || is_pytest_error_summary(l)
        || l.contains("AssertionError")
        || l.contains("Error:")
        || l.contains("Traceback")
        || l.contains("panicked at")
        || is_rust_error(l)
}

/// pytest's short-summary `ERROR <path>.py[::test] - ...` line. The path must
/// follow a single space: captured-log lines pad the level name
/// (`ERROR    pkg.mod:file.py:12 msg`), so a noisy suite's logs can't fill the
/// line cap ahead of the `FAILED` lines.
fn is_pytest_error_summary(l: &str) -> bool {
    l.strip_prefix("ERROR ")
        .and_then(|rest| rest.split(' ').next())
        .is_some_and(|path| path.contains(".py"))
}

/// Keep the lines `keep` selects, plus the ` --> file:line:col` location
/// directly under a kept rustc error, so a compile error is never sent to
/// Claude without its location even when `keep` drops `-->` lines.
fn filter_lines(text: &str, max_lines: usize, keep: fn(&str) -> bool) -> String {
    let mut prev_kept_error = false;
    text.lines()
        .filter(|l| {
            let kept = keep(l) || (prev_kept_error && l.trim_start().starts_with("--> "));
            prev_kept_error = kept && is_rust_error(l);
            kept
        })
        .take(max_lines)
        .collect::<Vec<_>>()
        .join("\n")
}

fn commit_message(failures_list: &str, args: &FailureArgs) -> String {
    format!(
        "fix: resolve CI pipeline failures\n\n\
         Automated fix by Claude in response to pipeline failures.\n\n\
         Failures addressed:\n{failures_list}\n\n\
         Actions taken:\n\
         - Ran autoformat (ruff format, cargo fmt)\n\
         - Fixed remaining lint issues\n\n\
         Iteration: {}/{}\n\n\
         Co-Authored-By: AI Pipeline Agent <noreply@anthropic.com>",
        args.iteration + 1,
        args.max_iterations
    )
}

fn build_failure_prompt(failures: &Failures, lint_output: &str, test_output: &str) -> String {
    let mut prompt = "You are fixing CI/CD pipeline failures for a pull request.\n\n".to_string();

    if !failures.lint.is_empty() {
        prompt.push_str(
            "## Lint/Format Failures Detected\n\n\
             INSTRUCTIONS:\n\
             1. Fix unused imports, formatting issues, type hints\n\
             2. Make minimal changes - only what's needed to pass CI\n\
             3. The autoformat tools have already been run\n\n",
        );
        if !lint_output.is_empty() {
            prompt.push_str(&format!("### Lint Output:\n{lint_output}\n\n"));
        }
    }

    if failures.test {
        prompt.push_str(
            "## Test Failures Detected\n\n\
             INSTRUCTIONS:\n\
             1. Analyze the test output to understand what's failing\n\
             2. Fix bugs in the CODE being tested, not the tests\n\
             3. Do NOT disable, skip, or delete failing tests\n\
             4. Make minimal, targeted fixes\n\n",
        );
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

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(unix)]
    #[test]
    fn capture_falls_back_when_filter_keeps_nothing() {
        // Output in a shape none of the filters know still reaches Claude.
        let gate = Gate::Command("echo 'mytool: style problem in a.c' >&2; exit 1".into());
        let out = capture_gate_errors(&gate, LINT_CMD_ENV, 50, is_lint_line);
        assert!(out.contains("style problem in a.c"), "{out}");

        // The fallback respects the caller's line cap.
        let gate = Gate::Command(
            "for i in $(seq 1 300); do echo \"mytool: issue $i\"; done; exit 1".into(),
        );
        let out = capture_gate_errors(&gate, LINT_CMD_ENV, 20, is_lint_line);
        assert_eq!(out.lines().count(), 20, "{out}");

        // A passing gate contributes nothing.
        let gate = Gate::Command("echo all good".into());
        assert!(capture_gate_errors(&gate, LINT_CMD_ENV, 50, is_lint_line).is_empty());
    }

    /// Real clippy / cargo test output shapes (e.g. AGENT_LINT_CMD set to
    /// `cargo clippy ... -D warnings` in a Rust-only repository).
    #[test]
    fn filters_keep_rust_diagnostics() {
        let clippy = "    Checking oasis-css v0.1.0 (/app/crates/oasis-css)\n\
                      warning: unused import: `std::fmt`\n \
                      --> crates/oasis-css/src/lib.rs:3:5\n\
                      error[E0308]: mismatched types\n\
                      error: could not compile `oasis-css` (lib) due to 1 previous error\n\
                      Container rust-ci-run-1 Creating";
        let kept = filter_lines(clippy, 50, is_lint_line);
        assert!(kept.contains("unused import"), "{kept}");
        assert!(
            kept.contains("--> crates/oasis-css/src/lib.rs:3:5"),
            "{kept}"
        );
        assert!(kept.contains("error[E0308]"), "{kept}");
        assert!(kept.contains("could not compile"), "{kept}");
        assert!(!kept.contains("Checking"), "{kept}");
        assert!(!kept.contains("Container"), "{kept}");

        // ruff output still matches.
        assert!(is_lint_line("src/a.py:1:1: F401 unused; Found 1 error"));

        let test = "test cascade::tests::nth ... FAILED\n\
                    thread 'cascade::tests::nth' panicked at crates/oasis-css/src/x.rs:9:5:\n\
                    running 12 tests";
        let kept = filter_lines(test, 50, is_test_line);
        assert!(kept.contains("... FAILED"), "{kept}");
        assert!(kept.contains("panicked at"), "{kept}");
        assert!(!kept.contains("running 12 tests"), "{kept}");

        // pytest collection errors keep the line naming the broken file.
        let collect = "______ ERROR collecting tests/test_x.py ______\n\
                       ERROR tests/test_y.py\n\
                       ERROR tests/test_z.py::test_db - RuntimeError\n\
                       ERROR    pkg.mod:file.py:12 connection reset\n\
                       collected 0 items / 2 errors";
        let kept = filter_lines(collect, 50, is_test_line);
        assert!(kept.contains("ERROR collecting tests/test_x.py"), "{kept}");
        assert!(kept.contains("ERROR tests/test_y.py"), "{kept}");
        assert!(kept.contains("ERROR tests/test_z.py::test_db"), "{kept}");
        // pytest captured-log lines at ERROR level are not failure lines.
        assert!(!kept.contains("connection reset"), "{kept}");
        assert!(!kept.contains("collected 0 items"), "{kept}");

        // Compile warnings before the results must not crowd the failures
        // out of the capped test capture.
        let mut noisy = String::new();
        for i in 0..200 {
            noisy.push_str(&format!(
                "warning: unused variable `v{i}`\n  --> src/a.rs:{i}:1\n"
            ));
        }
        noisy.push_str("test a::b ... FAILED\nthread 'a::b' panicked at src/a.rs:1:1:\n");
        let kept = filter_lines(&noisy, MAX_TEST_ERROR_LINES, is_test_line);
        assert!(kept.contains("... FAILED"), "{kept}");
        assert!(kept.contains("panicked at"), "{kept}");
        assert!(!kept.contains("unused variable"), "{kept}");
        assert!(is_test_line("error[E0425]: cannot find value `x`"));

        // A compile error keeps its location line; a warning's does not.
        let compile = "warning: unused\n  --> src/w.rs:1:1\n\
                       error[E0425]: cannot find value `x`\n  --> src/a.rs:3:9\n   |";
        let kept = filter_lines(compile, 50, is_test_line);
        assert!(kept.contains("--> src/a.rs:3:9"), "{kept}");
        assert!(!kept.contains("src/w.rs"), "{kept}");
    }

    fn env_from(pairs: &'static [(&'static str, &'static str)]) -> impl Fn(&str) -> Option<String> {
        move |k| {
            pairs
                .iter()
                .find(|(key, _)| *key == k)
                .map(|(_, v)| v.to_string())
        }
    }

    #[test]
    fn detect_prefers_job_results() {
        let f = Failures::detect(
            env_from(&[
                ("FORMAT_CHECK_RESULT", "failure"),
                ("FULL_LINT_RESULT", "failure"),
                ("TEST_SUITE_RESULT", "success"),
            ]),
            "test",
        );
        assert_eq!(f.lint, ["format", "full-lint"]);
        assert!(
            !f.test,
            "failure_types must be ignored when job results exist"
        );
        assert_eq!(f.lint_stages(), ["lint-basic", "lint-full"]);
    }

    #[test]
    fn detect_falls_back_to_failure_types() {
        let f = Failures::detect(env_from(&[]), "lint, test");
        assert_eq!(f.lint, ["format", "lint"]);
        assert!(f.test);
        assert_eq!(f.lint_stages(), ["lint-basic"]);
    }

    #[test]
    fn detect_does_not_substring_match() {
        // "linting" or "contest" must not be mistaken for lint/test.
        let f = Failures::detect(env_from(&[]), "linting,contest");
        assert!(f.is_empty());
    }

    #[test]
    fn bullet_list_includes_tests() {
        let f = Failures {
            lint: vec!["format"],
            test: true,
        };
        assert_eq!(f.bullet_list(), "- format\n- test-suite");
    }

    #[test]
    fn prompt_sections_follow_failures() {
        let f = Failures {
            lint: vec![],
            test: true,
        };
        let p = build_failure_prompt(&f, "ignored", "FAILED test_x");
        assert!(!p.contains("Lint/Format Failures"));
        assert!(p.contains("Test Failures Detected"));
        assert!(p.contains("FAILED test_x"));
    }

    #[test]
    fn filter_lines_caps() {
        let text = "Error: a\nok\nError: b\nError: c\n";
        assert_eq!(
            filter_lines(text, 2, |l| l.contains("Error:")),
            "Error: a\nError: b"
        );
    }

    #[test]
    fn handler_comment_has_metadata_marker() {
        let c = format_handler_comment(2, true, "abc1234", "- format");
        assert!(c.contains("<!-- agent-metadata:type=failure-fix:iteration=3 -->"));
        assert!(c.contains("`abc1234`"));
    }
}
