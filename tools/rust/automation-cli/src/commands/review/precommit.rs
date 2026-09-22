//! `automation-cli review precommit` -- autoformat + lint/test gates run
//! before an agent commits, with a machine-readable summary on stdout and
//! `precommit_*` GitHub outputs.

use std::collections::HashSet;
use std::process::Stdio;

use anyhow::{Result, bail};
use clap::Args;

use crate::shared::{output, process, project};

/// Maximum lines of error output to capture per check.
const MAX_ERROR_LINES: usize = 200;

#[derive(Args)]
pub struct PrecommitArgs {
    /// Run autoformat and restage changed files
    #[arg(long)]
    pub autoformat: bool,

    /// Run lint checks and report failures.
    /// Accepts an optional comma-separated list of CI stages to run
    /// (e.g., "lint-basic,lint-full"). Defaults to "lint-basic" if no value given.
    #[arg(long, num_args = 0..=1, default_missing_value = "lint-basic")]
    pub lint: Option<String>,

    /// Run test suite and report failures.
    /// Accepts an optional comma-separated list of CI stages to run
    /// (e.g., "test,econ-test"). Defaults to "test" if no value given.
    #[arg(long, num_args = 0..=1, default_missing_value = "test")]
    pub test: Option<String>,

    /// Run arbitrary CI stages (comma-separated).
    /// Output is captured and printed; non-zero exit from any stage is reported.
    #[arg(long)]
    pub stage: Option<String>,

    /// Exit non-zero if any check fails (default: report only).
    /// When false, failures are printed but the command exits 0
    /// so callers can decide how to handle them.
    #[arg(long)]
    pub fail_on_error: bool,
}

/// Result of a single precommit check.
pub struct CheckResult {
    pub name: String,
    pub passed: bool,
    pub error_output: String,
}

/// Aggregated result of all precommit checks.
pub struct PrecommitResult {
    pub checks: Vec<CheckResult>,
    pub autoformat_changed_files: u32,
}

impl PrecommitResult {
    pub fn all_passed(&self) -> bool {
        self.checks.iter().all(|c| c.passed)
    }

    /// Build a machine-readable summary suitable for feeding back to an agent.
    pub fn summary(&self) -> String {
        let mut out = String::new();

        if self.autoformat_changed_files > 0 {
            out.push_str(&format!(
                "Autoformat: restaged {} file(s)\n",
                self.autoformat_changed_files
            ));
        }

        for check in &self.checks {
            let status = if check.passed { "PASS" } else { "FAIL" };
            out.push_str(&format!("[{status}] {}\n", check.name));
            if !check.passed && !check.error_output.is_empty() {
                out.push_str(&check.error_output);
                if !check.error_output.ends_with('\n') {
                    out.push('\n');
                }
            }
        }

        out
    }
}

/// Split a comma-separated stage list, trimming blanks.
fn split_stages(list: Option<&str>) -> impl Iterator<Item = &str> {
    list.unwrap_or_default()
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
}

pub fn run(args: PrecommitArgs) -> Result<()> {
    project::enter_project_root()?;

    output::header("Review Precommit Checks");

    // Validate that at least one check was requested
    if !args.autoformat && args.lint.is_none() && args.test.is_none() && args.stage.is_none() {
        output::warn("No checks requested (use --autoformat, --lint, --test, or --stage)");
        project::set_github_output("precommit_passed", "true");
        project::set_github_output("precommit_autoformat_changed", "0");
        project::set_github_output("precommit_failed_checks", "");
        return Ok(());
    }

    let mut result = PrecommitResult {
        checks: Vec::new(),
        autoformat_changed_files: 0,
    };

    // --- Autoformat + restage ---
    if args.autoformat {
        output::step("Running autoformat...");
        let changed = run_autoformat_and_restage()?;
        result.autoformat_changed_files = changed;
        if changed > 0 {
            output::success(&format!("Autoformat: restaged {changed} file(s)"));
        } else {
            output::info("Autoformat: no changes");
        }
    }

    // --- Lint, test, and arbitrary stage checks (in that order) ---
    for (label, stages) in [
        ("lint check", &args.lint),
        ("test check", &args.test),
        ("stage", &args.stage),
    ] {
        for stage_name in split_stages(stages.as_deref()) {
            output::step(&format!("Running {label}: {stage_name}..."));
            let check = run_ci_stage_captured(stage_name);
            if check.passed {
                output::success(&format!("{stage_name}: passed"));
            } else {
                output::fail(&format!("{stage_name}: failed"));
            }
            result.checks.push(check);
        }
    }

    // --- Summary ---
    output::header("Precommit Summary");
    let summary = result.summary();
    // Print summary to stdout so callers/agents can parse it
    print!("{summary}");

    // Set GitHub outputs for workflow integration
    let has_failures = !result.all_passed();
    project::set_github_output("precommit_passed", &(!has_failures).to_string());
    project::set_github_output(
        "precommit_autoformat_changed",
        &result.autoformat_changed_files.to_string(),
    );

    if has_failures {
        let failed_names: Vec<&str> = result
            .checks
            .iter()
            .filter(|c| !c.passed)
            .map(|c| c.name.as_str())
            .collect();
        project::set_github_output("precommit_failed_checks", &failed_names.join(","));

        if args.fail_on_error {
            bail!("precommit checks failed: {}", failed_names.join(", "));
        }
    } else {
        project::set_github_output("precommit_failed_checks", "");
    }

    Ok(())
}

/// Run autoformat via the CI stage, then restage any files that were modified.
/// Returns the number of files restaged.
pub(super) fn run_autoformat_and_restage() -> Result<u32> {
    let staged_before = git_name_list(&["diff", "--cached", "--name-only"])?;
    // Snapshot unstaged tracked files before formatting so we can isolate
    // formatter-modified files from pre-existing edits afterwards.
    let unstaged_before: HashSet<String> = git_name_list(&["diff", "--name-only"])?
        .into_iter()
        .collect();

    // Formatting is best effort: a failure is reported but restaging still
    // happens for whatever the formatters did manage to change.
    if let Err(e) = run_ci_stage("autoformat") {
        output::warn(&format!("autoformat stage failed: {e}"));
    }

    // Restage previously-staged files so format changes are included.
    let mut restaged = git_add(&staged_before)?;

    // Stage tracked files the formatter modified (newly unstaged), without
    // sweeping in edits that were already present before formatting.
    let unstaged_after = git_name_list(&["diff", "--name-only"])?;
    let formatter_modified = newly_modified(&unstaged_before, unstaged_after);
    restaged += git_add(&formatter_modified)?;
    Ok(restaged)
}

/// Files in `after` that were not in `before`, sorted for stable output.
fn newly_modified(before: &HashSet<String>, after: Vec<String>) -> Vec<String> {
    let mut v: Vec<String> = after.into_iter().filter(|f| !before.contains(f)).collect();
    v.sort();
    v.dedup();
    v
}

/// `git add -- <files>` in batches (avoids argument-list-too-long).
fn git_add(files: &[String]) -> Result<u32> {
    for chunk in files.chunks(100) {
        let mut args = vec!["add", "--"];
        args.extend(chunk.iter().map(String::as_str));
        process::run("git", &args)?;
    }
    Ok(u32::try_from(files.len()).unwrap_or(u32::MAX))
}

/// Run a git command that prints one path per line.
fn git_name_list(args: &[&str]) -> Result<Vec<String>> {
    Ok(process::run_capture("git", args)?
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .map(String::from)
        .collect())
}

/// Run `automation-cli ci run <stage>` (this binary) with live output.
fn run_ci_stage(stage: &str) -> Result<()> {
    let status = process::self_command()?
        .args(["ci", "run", stage])
        .stdin(Stdio::null())
        .status()?;
    if !status.success() {
        bail!("ci run {stage} exited with {status}");
    }
    Ok(())
}

/// Run a CI stage (via this binary) and capture its output for error
/// reporting. Never fails: a stage that cannot even be started is reported
/// as a failed check with the spawn error as its output.
pub(super) fn run_ci_stage_captured(stage: &str) -> CheckResult {
    let raw = process::self_command().and_then(|mut cmd| {
        Ok(cmd
            .args(["ci", "run", stage])
            .stdin(Stdio::null())
            .output()?)
    });

    match raw {
        Ok(output) => {
            let passed = output.status.success();
            let error_output = if passed {
                String::new()
            } else {
                extract_error_lines(
                    &String::from_utf8_lossy(&output.stdout),
                    &String::from_utf8_lossy(&output.stderr),
                )
            };
            CheckResult {
                name: stage.to_string(),
                passed,
                error_output,
            }
        },
        Err(e) => CheckResult {
            name: stage.to_string(),
            passed: false,
            error_output: format!("Failed to execute stage: {e}"),
        },
    }
}

/// Extract the most relevant error lines from combined stdout/stderr output.
/// Filters for error indicators and truncates to MAX_ERROR_LINES.
fn extract_error_lines(stdout: &str, stderr: &str) -> String {
    let combined = format!("{stdout}\n{stderr}");
    let error_lines: Vec<&str> = combined
        .lines()
        .filter(|l| {
            let lower = l.to_lowercase();
            lower.contains("error")
                || lower.contains("warning")
                || lower.contains("failed")
                || lower.contains("found ")
                || lower.contains("traceback")
                || lower.contains("assertionerror")
                || lower.contains("panicked")
                || lower.contains("cannot find")
                || lower.contains("undefined")
                || lower.contains("unused")
                || lower.contains("mismatched")
        })
        .take(MAX_ERROR_LINES)
        .collect();

    if error_lines.is_empty() {
        // If no error-specific lines found, return the last N lines as context
        let all_lines: Vec<&str> = combined.lines().filter(|l| !l.trim().is_empty()).collect();
        let start = all_lines.len().saturating_sub(MAX_ERROR_LINES);
        return all_lines[start..].join("\n");
    }

    error_lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn precommit_result_summary_format() {
        let result = PrecommitResult {
            checks: vec![
                CheckResult {
                    name: "lint-basic".to_string(),
                    passed: true,
                    error_output: String::new(),
                },
                CheckResult {
                    name: "test".to_string(),
                    passed: false,
                    error_output: "src/foo.rs:10: error[E0308]: mismatched types".to_string(),
                },
            ],
            autoformat_changed_files: 3,
        };

        let summary = result.summary();
        assert!(summary.contains("Autoformat: restaged 3 file(s)"));
        assert!(summary.contains("[PASS] lint-basic"));
        assert!(summary.contains("[FAIL] test"));
        assert!(summary.contains("mismatched types"));
    }

    #[test]
    fn precommit_result_all_passed() {
        let result = PrecommitResult {
            checks: vec![CheckResult {
                name: "format".to_string(),
                passed: true,
                error_output: String::new(),
            }],
            autoformat_changed_files: 0,
        };
        assert!(result.all_passed());
    }

    #[test]
    fn precommit_result_has_failure() {
        let result = PrecommitResult {
            checks: vec![
                CheckResult {
                    name: "format".to_string(),
                    passed: true,
                    error_output: String::new(),
                },
                CheckResult {
                    name: "lint-full".to_string(),
                    passed: false,
                    error_output: "error: unused import".to_string(),
                },
            ],
            autoformat_changed_files: 0,
        };
        assert!(!result.all_passed());
    }

    #[test]
    fn extract_error_lines_filters_correctly() {
        let stdout = "Building...\nOK\nsrc/foo.rs:10: error[E0308]: mismatched types\nFinished\n";
        let stderr = "warning: unused variable `x`\n";
        let result = extract_error_lines(stdout, stderr);
        assert!(result.contains("error[E0308]"));
        assert!(result.contains("unused variable"));
        assert!(!result.contains("Building"));
        assert!(!result.contains("Finished"));
    }

    #[test]
    fn extract_error_lines_falls_back_to_tail() {
        let stdout = "line1\nline2\nline3\n";
        let stderr = "";
        let result = extract_error_lines(stdout, stderr);
        // No error-specific lines, so should return tail
        assert!(result.contains("line1"));
    }

    #[test]
    fn extract_error_lines_does_not_merge_stdout_and_stderr_lines() {
        // stdout without a trailing newline must not glue onto stderr's first line.
        let result = extract_error_lines("all good", "error: boom");
        assert_eq!(result, "error: boom");
    }

    #[test]
    fn extract_error_lines_caps_output() {
        let stdout = "error: x\n".repeat(MAX_ERROR_LINES + 50);
        let result = extract_error_lines(&stdout, "");
        assert_eq!(result.lines().count(), MAX_ERROR_LINES);
    }

    #[test]
    fn split_stages_trims_and_skips_blanks() {
        let v: Vec<_> = split_stages(Some(" lint-basic, ,lint-full ,")).collect();
        assert_eq!(v, ["lint-basic", "lint-full"]);
        assert_eq!(split_stages(None).count(), 0);
    }

    #[test]
    fn newly_modified_excludes_preexisting_edits() {
        let before: HashSet<String> = ["a.py".to_string()].into();
        let after = vec!["b.rs".to_string(), "a.py".to_string(), "b.rs".to_string()];
        assert_eq!(newly_modified(&before, after), ["b.rs"]);
    }

    #[test]
    fn summary_empty_checks() {
        let result = PrecommitResult {
            checks: Vec::new(),
            autoformat_changed_files: 0,
        };
        assert!(result.summary().is_empty());
        assert!(result.all_passed());
    }
}
