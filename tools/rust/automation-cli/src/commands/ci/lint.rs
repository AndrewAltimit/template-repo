//! `automation-cli lint <mode>` -- lint stages that count errors/warnings and
//! export them as `errors` / `warnings` to `$GITHUB_ENV` (consumed by
//! `.github/workflows/lint-stages.yml`). Exits 1 when any error was counted.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use clap::Subcommand;

use crate::shared::{docker, output, process, project};

#[derive(Subcommand)]
pub enum LintAction {
    /// Run format checks with error counting
    Format,
    /// Run Ruff linting with error counting
    Ruff,
    /// Run basic linting suite with error counting
    Basic,
    /// Run full linting suite (format + ruff + ty + security) with error counting
    Full,
    /// Run markdown link checking (writes link_check_summary.md)
    Links,
}

/// Error / warning tally for one lint run.
#[derive(Default)]
struct Tally {
    errors: u32,
    warnings: u32,
}

impl Tally {
    /// Count a failed check as an error.
    fn error_unless(&mut self, passed: bool) {
        if !passed {
            self.errors += 1;
        }
    }
}

pub fn run(action: LintAction) -> Result<()> {
    let root = project::enter_project_root()?;
    let compose = project::compose_file(&root);
    project::export_compose_env();

    let mut tally = Tally::default();
    let check = |args: &[&str]| docker::run_python_ci_check(&compose, args, &[]);

    match action {
        LintAction::Format => {
            output::header("Running format check");
            tally.error_unless(check(&["ruff", "format", "--check", "--diff", "."])?);
            tally.error_unless(check(&["ruff", "check", "--select=I", "--diff", "."])?);
        },
        LintAction::Ruff => {
            output::header("Running Ruff (fast linter)");
            tally.error_unless(check(&["ruff", "check", ".", "--output-format=grouped"])?);
        },
        LintAction::Basic => {
            output::header("Running basic linting");
            // Format/import-order results are shown for context only; the
            // `format` stage is what gates on them.
            check(&["ruff", "format", "--check", "."])?;
            check(&["ruff", "check", "--select=I", "."])?;

            // Critical errors (syntax errors, undefined names, ...)
            tally.error_unless(check(&[
                "ruff",
                "check",
                "--select=E9,F63,F7,F82",
                "--output-format=grouped",
                ".",
            ])?);

            // Style check (informational)
            check(&[
                "ruff",
                "check",
                "--select=E,W,C90",
                "--ignore=E501,E402",
                "--exit-zero",
                "--output-format=grouped",
                ".",
            ])?;
        },
        LintAction::Full => {
            output::header("Running full linting suite");
            tally.error_unless(check(&["ruff", "format", "--check", "."])?);
            // Import order is gated by the `format` stage.
            check(&["ruff", "check", "--select=I", "."])?;
            tally.error_unless(check(&["ruff", "check", "--output-format=grouped", "."])?);
            // Critical errors are checked explicitly in case the project's
            // ruff `select` list ever drops them.
            tally.error_unless(check(&[
                "ruff",
                "check",
                "--select=E9,F63,F7,F82",
                "--output-format=grouped",
                ".",
            ])?);

            if !check(&["ty", "check", "."])? {
                output::info("ty found type errors (informational)");
            }

            output::step("Running Bandit security scanner...");
            let bandit_ok = check(&["bandit", "-r", ".", "-c", "pyproject.toml", "-f", "txt"])?;
            if !bandit_ok {
                output::warn("Bandit found security issues");
            }
            tally.error_unless(bandit_ok);

            output::step("Checking dependency security...");
            if !super::dependency_audit(&compose)? {
                tally.warnings += 1;
                output::warn("Dependency audit found vulnerabilities");
            }
        },
        LintAction::Links => {
            output::header("Running markdown link check");
            tally.error_unless(run_link_check(&root, &compose)?);
        },
    }

    // Export results for GitHub Actions
    project::set_github_env("errors", &tally.errors.to_string());
    project::set_github_env("warnings", &tally.warnings.to_string());

    println!();
    output::header("Linting Summary");
    output::info(&format!("Errors: {}", tally.errors));
    output::info(&format!("Warnings: {}", tally.warnings));

    if tally.errors > 0 {
        output::fail(&format!("Linting failed with {} errors", tally.errors));
        std::process::exit(1);
    }
    output::success("Linting completed");
    Ok(())
}

const LINK_CHECKER_DIR: &str = "tools/rust/markdown-link-checker";
const LINK_CHECKER_BIN: &str = "md-link-checker";

/// Find the md-link-checker binary: repo build output first (where CI
/// installs it), then `PATH`, else build it inside the rust-ci container.
fn link_checker_binary(root: &Path, compose: &Path) -> Result<PathBuf> {
    let local = root
        .join(LINK_CHECKER_DIR)
        .join("target/release")
        .join(LINK_CHECKER_BIN);
    if local.is_file() {
        return Ok(local);
    }
    if let Some(p) = process::find_on_path(LINK_CHECKER_BIN) {
        return Ok(p);
    }
    output::warn("md-link-checker not found, building it in the rust-ci container...");
    docker::run_cargo(compose, LINK_CHECKER_DIR, &["build", "--release"])?;
    if local.is_file() {
        Ok(local)
    } else {
        anyhow::bail!(
            "md-link-checker build finished but {} is missing",
            local.display()
        )
    }
}

/// Run the link checker, echo its output, and write `link_check_summary.md`
/// for the PR comment step. Returns whether all links were valid.
fn run_link_check(root: &Path, compose: &Path) -> Result<bool> {
    let binary = link_checker_binary(root, compose)?;
    let cmd_output = std::process::Command::new(&binary)
        .arg(root)
        .arg("--internal-only")
        .stdin(std::process::Stdio::null())
        .output()
        .with_context(|| format!("failed to execute {}", binary.display()))?;

    let stdout = String::from_utf8_lossy(&cmd_output.stdout);
    let stderr = String::from_utf8_lossy(&cmd_output.stderr);
    if !stdout.is_empty() {
        print!("{stdout}");
    }
    if !stderr.is_empty() {
        eprint!("{stderr}");
    }

    let success = cmd_output.status.success();
    let summary = link_summary(success, &format!("{stdout}{stderr}"));
    std::fs::write(root.join("link_check_summary.md"), summary)
        .context("failed to write link_check_summary.md")?;
    output::info("Wrote link_check_summary.md");
    Ok(success)
}

/// Markdown summary for the PR comment. On failure, only the lines that look
/// like broken-link reports are included (or the full output if none match).
fn link_summary(success: bool, combined: &str) -> String {
    if success {
        return "## Link Check Results\n\nAll internal links are valid.".to_string();
    }
    let relevant: Vec<&str> = combined
        .lines()
        .filter(|line| {
            line.contains("ERROR")
                || line.contains("broken")
                || line.contains("not found")
                || line.contains("-> ")
        })
        .collect();
    let body = if relevant.is_empty() {
        combined.trim_end().to_string()
    } else {
        relevant.join("\n")
    };
    format!("## Link Check Results\n\nBroken links found:\n\n```\n{body}\n```\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn link_summary_success() {
        assert!(link_summary(true, "whatever").contains("All internal links are valid"));
    }

    #[test]
    fn link_summary_filters_relevant_lines() {
        let out = "Scanning 10 files\nERROR docs/a.md: broken link -> b.md\nDone\n";
        let s = link_summary(false, out);
        assert!(s.contains("ERROR docs/a.md"));
        assert!(!s.contains("Scanning"));
        assert!(s.ends_with("```\n"));
    }

    #[test]
    fn link_summary_falls_back_to_full_output() {
        let s = link_summary(false, "something odd happened\n");
        assert!(s.contains("something odd happened"));
    }

    #[test]
    fn tally_counts_failures() {
        let mut t = Tally::default();
        t.error_unless(true);
        t.error_unless(false);
        t.error_unless(false);
        assert_eq!(t.errors, 2);
        assert_eq!(t.warnings, 0);
    }
}
