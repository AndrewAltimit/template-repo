use std::process::{Command, Stdio};

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
    #[arg(long, default_value = "false")]
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

pub fn run(args: PrecommitArgs) -> Result<()> {
    let root = project::find_project_root()?;
    std::env::set_current_dir(&root)?;

    output::header("Review Precommit Checks");

    // Validate that at least one check was requested
    if !args.autoformat && args.lint.is_none() && args.test.is_none() && args.stage.is_none() {
        output::warn("No checks requested (use --autoformat, --lint, --test, or --stage)");
        project::set_github_output("precommit_passed", "true");
        project::set_github_output("precommit_autoformat_changed", "0");
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

    // --- Lint checks ---
    if let Some(ref stages) = args.lint {
        for stage_name in stages.split(',').map(str::trim).filter(|s| !s.is_empty()) {
            output::step(&format!("Running lint check: {stage_name}..."));
            let check = run_ci_stage_captured(stage_name)?;
            if check.passed {
                output::success(&format!("{stage_name}: passed"));
            } else {
                output::fail(&format!("{stage_name}: failed"));
            }
            result.checks.push(check);
        }
    }

    // --- Test checks ---
    if let Some(ref stages) = args.test {
        for stage_name in stages.split(',').map(str::trim).filter(|s| !s.is_empty()) {
            output::step(&format!("Running test check: {stage_name}..."));
            let check = run_ci_stage_captured(stage_name)?;
            if check.passed {
                output::success(&format!("{stage_name}: passed"));
            } else {
                output::fail(&format!("{stage_name}: failed"));
            }
            result.checks.push(check);
        }
    }

    // --- Arbitrary stages ---
    if let Some(ref stages) = args.stage {
        for stage_name in stages.split(',').map(str::trim).filter(|s| !s.is_empty()) {
            output::step(&format!("Running stage: {stage_name}..."));
            let check = run_ci_stage_captured(stage_name)?;
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
    }

    Ok(())
}

/// Run autoformat via the CI stage, then restage any files that were modified.
/// Returns the number of files restaged.
pub(super) fn run_autoformat_and_restage() -> Result<u32> {
    // Capture the set of currently-staged files before formatting
    let staged_before = get_staged_files()?;

    // Snapshot unstaged tracked files before formatting so we can isolate
    // formatter-modified files from pre-existing edits afterwards
    let before_output = process::run_capture("git", &["diff", "--name-only"])?;
    let unstaged_before: std::collections::HashSet<String> = before_output
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .map(String::from)
        .collect();

    // Run the autoformat CI stage (ruff format, cargo fmt, etc.)
    let _ = run_ci_stage("autoformat");

    // Restage files that were already staged (autoformat may have modified them)
    let mut restaged = 0u32;
    if !staged_before.is_empty() {
        // Add back all previously-staged files so format changes are included
        let files: Vec<&str> = staged_before.iter().map(|s| s.as_str()).collect();
        // Stage in batches to avoid argument-list-too-long
        for chunk in files.chunks(100) {
            let mut args = vec!["add", "--"];
            args.extend_from_slice(chunk);
            process::run("git", &args)?;
        }
        restaged = staged_before.len() as u32;
    }

    // Stage tracked files that were modified by the formatter (not previously
    // unstaged). We compare the unstaged set before/after to isolate changes
    // the formatter actually made, avoiding sweeping in pre-existing edits.
    let after_output = process::run_capture("git", &["diff", "--name-only"])?;
    let unstaged_after: std::collections::HashSet<String> = after_output
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .map(String::from)
        .collect();
    let formatter_modified: Vec<&str> = unstaged_after
        .difference(&unstaged_before)
        .map(|s| s.as_str())
        .collect();
    if !formatter_modified.is_empty() {
        for chunk in formatter_modified.chunks(100) {
            let mut args = vec!["add", "--"];
            args.extend_from_slice(chunk);
            process::run("git", &args)?;
        }
        restaged += formatter_modified.len() as u32;
    }

    Ok(restaged)
}

/// Get the list of currently staged file paths.
fn get_staged_files() -> Result<Vec<String>> {
    let output = process::run_capture("git", &["diff", "--cached", "--name-only"])?;
    Ok(output
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .map(String::from)
        .collect())
}

/// Run a CI stage via automation-cli (or the legacy shell wrapper) and return
/// success/failure status without aborting the process.
fn run_ci_stage(stage: &str) -> bool {
    process::run("./automation/ci-cd/run-ci.sh", &[stage]).is_ok()
}

/// Run a CI stage and capture its output for error reporting.
/// Returns a CheckResult with the stage name, pass/fail, and filtered error lines.
pub(super) fn run_ci_stage_captured(stage: &str) -> Result<CheckResult> {
    let raw = Command::new("./automation/ci-cd/run-ci.sh")
        .arg(stage)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output();

    match raw {
        Ok(output) => {
            let passed = output.status.success();
            let stdout = String::from_utf8_lossy(&output.stdout);
            let stderr = String::from_utf8_lossy(&output.stderr);

            // Extract error-relevant lines for agent consumption
            let error_output = if passed {
                String::new()
            } else {
                extract_error_lines(&stdout, &stderr)
            };

            Ok(CheckResult {
                name: stage.to_string(),
                passed,
                error_output,
            })
        },
        Err(e) => Ok(CheckResult {
            name: stage.to_string(),
            passed: false,
            error_output: format!("Failed to execute stage: {e}"),
        }),
    }
}

/// Extract the most relevant error lines from combined stdout/stderr output.
/// Filters for error indicators and truncates to MAX_ERROR_LINES.
fn extract_error_lines(stdout: &str, stderr: &str) -> String {
    let combined = format!("{stdout}{stderr}");
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
        let all_lines: Vec<&str> = combined.lines().collect();
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
    fn summary_empty_checks() {
        let result = PrecommitResult {
            checks: Vec::new(),
            autoformat_changed_files: 0,
        };
        assert!(result.summary().is_empty());
        assert!(result.all_passed());
    }
}
