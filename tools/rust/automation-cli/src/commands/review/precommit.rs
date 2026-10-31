//! `automation-cli review precommit`: autoformat + lint/test gates run
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

/// Env override for the agent autoformat gate (see [`Gate::from_env`]).
pub(super) const AUTOFORMAT_CMD_ENV: &str = "AGENT_AUTOFORMAT_CMD";
/// Env override for the agent lint gate (see [`Gate::from_env`]).
pub(super) const LINT_CMD_ENV: &str = "AGENT_LINT_CMD";
/// Env override for the agent test gate (see [`Gate::from_env`]).
pub(super) const TEST_CMD_ENV: &str = "AGENT_TEST_CMD";

/// How an agent gate (autoformat, lint, test) runs in this repository.
///
/// The built-in stages assume template-repo's CI layout (`python-ci` /
/// `rust-ci` compose services). Other repositories using these tools set the
/// `AGENT_*_CMD` variables to their own command, or to an empty string to
/// turn the gate off.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) enum Gate {
    /// Built-in `automation-cli ci run <stage>` stages.
    Stages(Vec<String>),
    /// Repository-specific shell command, run with `bash -c` at the repo root.
    Command(String),
    /// Disabled by an empty override.
    Skip,
}

impl Gate {
    /// Resolve a gate: `var` unset means the default stages, set but blank
    /// means skip, anything else is a shell command.
    pub(super) fn from_env(
        lookup: impl Fn(&str) -> Option<String>,
        var: &str,
        default_stages: &[&str],
    ) -> Self {
        match lookup(var) {
            None => Self::Stages(default_stages.iter().map(|s| (*s).to_string()).collect()),
            Some(cmd) if cmd.trim().is_empty() => Self::Skip,
            Some(cmd) => Self::Command(cmd.trim().to_string()),
        }
    }

    /// Run every step of the gate with captured output.
    pub(super) fn run_captured(&self) -> Vec<CheckResult> {
        match self {
            Self::Stages(stages) => stages.iter().map(|s| run_ci_stage_captured(s)).collect(),
            Self::Command(cmd) => vec![run_command_captured(cmd)],
            Self::Skip => Vec::new(),
        }
    }
}

/// Result of a single precommit check.
pub struct CheckResult {
    pub name: String,
    pub passed: bool,
    /// The check could not run at all (missing compose service, unknown
    /// stage, no compose file), as opposed to running and finding problems.
    pub unavailable: bool,
    pub error_output: String,
    /// Combined stdout + stderr, for callers that apply their own filter.
    pub raw_output: String,
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
            let status = match (check.passed, check.unavailable) {
                (true, _) => "PASS",
                (false, true) => "UNAVAILABLE",
                (false, false) => "FAIL",
            };
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
            // An unavailable stage still counts as a failure here: a caller
            // that asked for this gate explicitly should not pass silently.
            match (check.passed, check.unavailable) {
                (true, _) => output::success(&format!("{stage_name}: passed")),
                (false, true) => output::fail(&format!(
                    "{stage_name}: unavailable in this repository (counted as failed)"
                )),
                (false, false) => output::fail(&format!("{stage_name}: failed")),
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

/// Run the autoformat gate (`AGENT_AUTOFORMAT_CMD`, default the `autoformat`
/// CI stage), then restage any files that were modified. Returns the number
/// of files restaged.
pub(super) fn run_autoformat_and_restage() -> Result<u32> {
    let gate = Gate::from_env(
        |k| std::env::var(k).ok(),
        AUTOFORMAT_CMD_ENV,
        &["autoformat"],
    );
    if gate == Gate::Skip {
        output::info(&format!(
            "Autoformat skipped ({AUTOFORMAT_CMD_ENV} is empty)"
        ));
        return Ok(0);
    }

    let staged_before = git_name_list(&["diff", "--cached", "--name-only"])?;
    // Snapshot unstaged tracked files before formatting so we can isolate
    // formatter-modified files from pre-existing edits afterwards.
    let unstaged_before: HashSet<String> = git_name_list(&["diff", "--name-only"])?
        .into_iter()
        .collect();

    // Formatting is best effort: a failure is reported but restaging still
    // happens for whatever the formatters did manage to change.
    for check in gate.run_captured() {
        if check.unavailable {
            output::warn(&format!(
                "autoformat stage '{}' is not available in this repository; set \
                 {AUTOFORMAT_CMD_ENV} to this repo's formatter (or to an empty string to skip)",
                check.name
            ));
        } else if !check.passed {
            output::warn(&format!(
                "autoformat '{}' failed:\n{}",
                check.name, check.error_output
            ));
        }
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

/// Run a CI stage (via this binary) and capture its output for error
/// reporting. Never fails: a stage that cannot even be started is reported
/// as an unavailable check with the spawn error as its output.
pub(super) fn run_ci_stage_captured(stage: &str) -> CheckResult {
    let raw = process::self_command().and_then(|mut cmd| {
        Ok(cmd
            .args(["ci", "run", stage])
            .stdin(Stdio::null())
            .output()?)
    });
    check_from_output(stage, raw, true)
}

/// Run a repository-provided shell command at the repo root, capturing output.
/// The root is set explicitly rather than relying on the caller's cwd.
fn run_command_captured(cmd: &str) -> CheckResult {
    let raw = project::find_project_root().and_then(|root| {
        Ok(std::process::Command::new("bash")
            .args(["-c", cmd])
            .current_dir(root)
            .stdin(Stdio::null())
            .output()?)
    });
    check_from_output(cmd, raw, false)
}

/// Build a [`CheckResult`]. `builtin_stage` enables detection of stages that
/// cannot run in this repository (their failure is not a code problem).
fn check_from_output(
    name: &str,
    raw: Result<std::process::Output>,
    builtin_stage: bool,
) -> CheckResult {
    match raw {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout);
            let stderr = String::from_utf8_lossy(&out.stderr);
            let passed = out.status.success();
            let raw_output = format!("{stdout}\n{stderr}");
            let unavailable = !passed && builtin_stage && stage_unavailable(&stderr);
            let error_output = if passed {
                String::new()
            } else {
                extract_error_lines(&stdout, &stderr)
            };
            CheckResult {
                name: name.to_string(),
                passed,
                unavailable,
                error_output,
                raw_output,
            }
        },
        Err(e) => CheckResult {
            name: name.to_string(),
            passed: false,
            unavailable: true,
            error_output: format!("Failed to execute: {e}"),
            raw_output: String::new(),
        },
    }
}

/// True when a built-in stage failed because this repository lacks the CI
/// infrastructure it needs, rather than because the code has problems.
///
/// Only the last few stderr lines are checked: that is where compose and
/// `ci run` report these errors before exiting, and it keeps a real lint or
/// test log that merely mentions the same text from being hidden.
fn stage_unavailable(stderr: &str) -> bool {
    const MARKERS: &[&str] = &[
        "no such service:",
        "unknown stage:",
        "no configuration file provided",
    ];
    const TAIL_LINES: usize = 10;
    stderr
        .lines()
        .filter(|l| !l.trim().is_empty())
        .rev()
        .take(TAIL_LINES)
        .any(|l| {
            let lower = l.to_lowercase();
            MARKERS.iter().any(|m| lower.contains(m))
        })
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
                // rustc/clippy location line under each diagnostic
                || l.trim_start().starts_with("--> ")
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
                    unavailable: false,
                    raw_output: String::new(),
                },
                CheckResult {
                    name: "test".to_string(),
                    passed: false,
                    error_output: "src/foo.rs:10: error[E0308]: mismatched types".to_string(),
                    unavailable: false,
                    raw_output: String::new(),
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
                unavailable: false,
                raw_output: String::new(),
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
                    unavailable: false,
                    raw_output: String::new(),
                },
                CheckResult {
                    name: "lint-full".to_string(),
                    passed: false,
                    error_output: "error: unused import".to_string(),
                    unavailable: false,
                    raw_output: String::new(),
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

        // clippy's location line is kept so the agent knows where to look.
        let result = extract_error_lines("warning: unused import\n  --> src/lib.rs:3:5\n", "");
        assert!(result.contains("--> src/lib.rs:3:5"), "{result}");
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

    #[test]
    fn gate_from_env_default_skip_and_command() {
        let unset = |_: &str| None;
        assert_eq!(
            Gate::from_env(unset, LINT_CMD_ENV, &["lint-basic"]),
            Gate::Stages(vec!["lint-basic".to_string()])
        );

        let empty = |_: &str| Some("  ".to_string());
        assert_eq!(
            Gate::from_env(empty, LINT_CMD_ENV, &["lint-basic"]),
            Gate::Skip
        );
        assert!(Gate::Skip.run_captured().is_empty());

        let cmd =
            |k: &str| (k == LINT_CMD_ENV).then(|| " cargo clippy -- -D warnings ".to_string());
        assert_eq!(
            Gate::from_env(cmd, LINT_CMD_ENV, &["lint-basic"]),
            Gate::Command("cargo clippy -- -D warnings".to_string())
        );
        // Only the named variable is consulted.
        assert_eq!(
            Gate::from_env(cmd, AUTOFORMAT_CMD_ENV, &["autoformat"]),
            Gate::Stages(vec!["autoformat".to_string()])
        );
    }

    #[test]
    fn stage_unavailable_detects_missing_infra() {
        // Observed in a repo without template-repo's compose services.
        assert!(stage_unavailable(
            "no such service: python-ci\nError: docker compose ... exited with exit status: 1"
        ));
        assert!(stage_unavailable("Error: unknown stage: lint-basic"));
        assert!(stage_unavailable(
            "no configuration file provided: not found"
        ));
        assert!(!stage_unavailable("src/foo.py:1:1: F401 unused import"));

        // A real log that merely mentions the text early on is not hidden:
        // only the stderr tail, where compose / ci run report it, counts.
        let mut log = String::from("test asserts 'no such service: x' message\n");
        for i in 0..20 {
            log.push_str(&format!("FAILED tests/test_{i}.py::test_x\n"));
        }
        assert!(!stage_unavailable(&log));
    }

    #[cfg(unix)]
    #[test]
    fn check_from_output_ignores_markers_on_stdout() {
        use std::os::unix::process::ExitStatusExt;
        let raw = Ok(std::process::Output {
            status: std::process::ExitStatus::from_raw(1 << 8),
            stdout: b"assert msg == 'no such service: python-ci'\n".to_vec(),
            stderr: b"1 failed\n".to_vec(),
        });
        let c = check_from_output("test", raw, true);
        assert!(!c.passed && !c.unavailable);
    }

    #[cfg(unix)]
    #[test]
    fn check_from_output_flags_unavailable_only_for_builtin_failures() {
        use std::os::unix::process::ExitStatusExt;
        let out = |code: i32, stderr: &str| {
            Ok(std::process::Output {
                status: std::process::ExitStatus::from_raw(code << 8),
                stdout: Vec::new(),
                stderr: stderr.as_bytes().to_vec(),
            })
        };
        let c = check_from_output("lint-basic", out(1, "no such service: python-ci"), true);
        assert!(!c.passed && c.unavailable);
        // A user command printing the same text is a real failure.
        let c = check_from_output("make lint", out(1, "no such service: python-ci"), false);
        assert!(!c.passed && !c.unavailable);
        let c = check_from_output("lint-basic", out(0, ""), true);
        assert!(c.passed && !c.unavailable);
    }

    #[test]
    fn summary_marks_unavailable_checks() {
        let result = PrecommitResult {
            checks: vec![CheckResult {
                name: "lint-basic".to_string(),
                passed: false,
                unavailable: true,
                error_output: "no such service: python-ci".to_string(),
                raw_output: String::new(),
            }],
            autoformat_changed_files: 0,
        };
        assert!(result.summary().contains("[UNAVAILABLE] lint-basic"));
    }
}
