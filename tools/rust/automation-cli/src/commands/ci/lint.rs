use std::path::Path;

use anyhow::Result;
use clap::Subcommand;

use crate::shared::{docker, output, project};

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
    /// Run markdown link checking
    Links,
}

pub fn run(action: LintAction) -> Result<()> {
    let root = project::find_project_root()?;
    let compose = project::compose_file(&root);
    std::env::set_current_dir(&root)?;

    // Export user IDs for docker compose
    // SAFETY: single-threaded at this point
    unsafe {
        std::env::set_var("USER_ID", format!("{}", libc::getuid()));
        std::env::set_var("GROUP_ID", format!("{}", libc::getgid()));
    }

    let mut errors: u32 = 0;
    let mut warnings: u32 = 0;

    match action {
        LintAction::Format => {
            output::header("Running format check");
            if !docker::run_python_ci_check(
                &compose,
                &["ruff", "format", "--check", "--diff", "."],
            )? {
                errors += 1;
            }
            if !docker::run_python_ci_check(
                &compose,
                &["ruff", "check", "--select=I", "--diff", "."],
            )? {
                errors += 1;
            }
        },
        LintAction::Ruff => {
            output::header("Running Ruff (fast linter)");
            if !docker::run_python_ci_check(
                &compose,
                &["ruff", "check", ".", "--output-format=grouped"],
            )? {
                errors += 1;
            }
        },
        LintAction::Basic => {
            output::header("Running basic linting");
            // Format checks
            let _ = docker::run_python_ci_check(&compose, &["ruff", "format", "--check", "."]);
            let _ = docker::run_python_ci_check(&compose, &["ruff", "check", "--select=I", "."]);

            // Critical errors
            if !docker::run_python_ci_check(
                &compose,
                &[
                    "ruff",
                    "check",
                    "--select=E9,F63,F7,F82",
                    "--output-format=grouped",
                    ".",
                ],
            )? {
                errors += 1;
            }

            // Style check (informational)
            let _ = docker::run_python_ci_check(
                &compose,
                &[
                    "ruff",
                    "check",
                    "--select=E,W,C90",
                    "--exit-zero",
                    "--output-format=grouped",
                    ".",
                ],
            );
        },
        LintAction::Full => {
            output::header("Running full linting suite");

            // Format checks
            if !docker::run_python_ci_check(&compose, &["ruff", "format", "--check", "."])? {
                errors += 1;
            }
            let _ = docker::run_python_ci_check(&compose, &["ruff", "check", "--select=I", "."]);

            // Full ruff
            if !docker::run_python_ci_check(
                &compose,
                &["ruff", "check", "--output-format=grouped", "."],
            )? {
                errors += 1;
            }

            // Critical errors
            if !docker::run_python_ci_check(
                &compose,
                &[
                    "ruff",
                    "check",
                    "--select=E9,F63,F7,F82",
                    "--output-format=grouped",
                    ".",
                ],
            )? {
                errors += 1;
            }

            // Type checking with ty
            if !docker::run_python_ci_check(&compose, &["ty", "check"])? {
                // ty errors are informational for now
                output::info("ty found type errors (informational)");
            }

            // ChatGPT issue #1 fix: security scanning now counts as errors, not informational
            output::step("Running Bandit security scanner...");
            if !docker::run_python_ci_check(
                &compose,
                &["bandit", "-r", ".", "-c", "pyproject.toml", "-f", "txt"],
            )? {
                errors += 1;
                output::warn("Bandit found security issues");
            }

            // Dependency security check
            run_dependency_check(&compose, &mut warnings)?;
        },
        LintAction::Links => {
            output::header("Running markdown link check");
            run_link_check(&root, &mut errors)?;
        },
    }

    // Export results for GitHub Actions
    project::set_github_env("errors", &errors.to_string());
    project::set_github_env("warnings", &warnings.to_string());

    // Summary
    println!();
    output::header("Linting Summary");
    output::info(&format!("Errors: {errors}"));
    output::info(&format!("Warnings: {warnings}"));

    if errors > 0 {
        output::fail(&format!("Linting failed with {errors} errors"));
        std::process::exit(1);
    }
    output::success("Linting completed");
    Ok(())
}

fn run_dependency_check(compose: &Path, warnings: &mut u32) -> Result<()> {
    output::step("Checking dependency security...");
    if std::env::var("SAFETY_API_KEY").is_ok() {
        output::step("Using Safety with API key...");
        if !docker::run_python_ci_check(
            compose,
            &["safety", "scan", "--disable-optional-telemetry"],
        )? {
            *warnings += 1;
            output::warn("Safety found dependency vulnerabilities");
        }
    } else {
        output::step("No SAFETY_API_KEY found, using pip-audit...");
        if !docker::run_python_ci_check(compose, &["python", "-m", "pip_audit"])? {
            *warnings += 1;
            output::warn("pip-audit found dependency vulnerabilities");
        }
    }
    Ok(())
}

fn run_link_check(root: &Path, errors: &mut u32) -> Result<()> {
    let binary = root.join("tools/rust/markdown-link-checker/target/release/md-link-checker");

    if !binary.exists() {
        output::warn("Rust binary not found, building on demand...");
        crate::shared::process::run_in(
            &root.join("tools/rust/markdown-link-checker"),
            "cargo",
            &["build", "--release"],
        )?;
    }

    let binary_str = binary.to_string_lossy();
    let root_str = root.to_string_lossy();
    if crate::shared::process::run(&binary_str, &[&root_str, "--internal-only"]).is_err() {
        *errors += 1;
    }
    Ok(())
}
