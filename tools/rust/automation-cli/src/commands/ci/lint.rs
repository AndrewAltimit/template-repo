use std::path::Path;

use anyhow::{Context, Result};
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
                &[],
            )? {
                errors += 1;
            }
            if !docker::run_python_ci_check(
                &compose,
                &["ruff", "check", "--select=I", "--diff", "."],
                &[],
            )? {
                errors += 1;
            }
        },
        LintAction::Ruff => {
            output::header("Running Ruff (fast linter)");
            if !docker::run_python_ci_check(
                &compose,
                &["ruff", "check", ".", "--output-format=grouped"],
                &[],
            )? {
                errors += 1;
            }
        },
        LintAction::Basic => {
            output::header("Running basic linting");
            // Format checks
            let _ = docker::run_python_ci_check(&compose, &["ruff", "format", "--check", "."], &[]);
            let _ =
                docker::run_python_ci_check(&compose, &["ruff", "check", "--select=I", "."], &[]);

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
                &[],
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
                &[],
            );
        },
        LintAction::Full => {
            output::header("Running full linting suite");

            // Format checks
            if !docker::run_python_ci_check(&compose, &["ruff", "format", "--check", "."], &[])? {
                errors += 1;
            }
            let _ =
                docker::run_python_ci_check(&compose, &["ruff", "check", "--select=I", "."], &[]);

            // Full ruff
            if !docker::run_python_ci_check(
                &compose,
                &["ruff", "check", "--output-format=grouped", "."],
                &[],
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
                &[],
            )? {
                errors += 1;
            }

            // Type checking with ty
            if !docker::run_python_ci_check(&compose, &["ty", "check"], &[])? {
                // ty errors are informational for now
                output::info("ty found type errors (informational)");
            }

            // ChatGPT issue #1 fix: security scanning now counts as errors, not informational
            output::step("Running Bandit security scanner...");
            if !docker::run_python_ci_check(
                &compose,
                &["bandit", "-r", ".", "-c", "pyproject.toml", "-f", "txt"],
                &[],
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
    if let Ok(key) = std::env::var("SAFETY_API_KEY") {
        output::step("Using Safety with API key...");
        if !docker::run_python_ci_check(
            compose,
            &["safety", "scan", "--disable-optional-telemetry"],
            &[("SAFETY_API_KEY", &key)],
        )? {
            *warnings += 1;
            output::warn("Safety found dependency vulnerabilities");
        }
    } else {
        output::step("No SAFETY_API_KEY found, using pip-audit...");
        if !docker::run_python_ci_check(compose, &["python", "-m", "pip_audit"], &[])? {
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

    let root_str = root.to_string_lossy();
    let cmd_output = std::process::Command::new(binary.as_os_str())
        .args([root_str.as_ref(), "--internal-only"])
        .stdin(std::process::Stdio::null())
        .output()
        .context("failed to execute md-link-checker")?;

    let stdout = String::from_utf8_lossy(&cmd_output.stdout);
    let stderr = String::from_utf8_lossy(&cmd_output.stderr);

    // Print output so it's visible in CI logs
    if !stdout.is_empty() {
        print!("{stdout}");
    }
    if !stderr.is_empty() {
        eprint!("{stderr}");
    }

    let success = cmd_output.status.success();
    if !success {
        *errors += 1;
    }

    // Generate summary file for the GitHub Actions PR comment step
    let combined = format!("{stdout}{stderr}");
    let summary = if success {
        "## Link Check Results\n\nAll internal links are valid.".to_string()
    } else {
        let mut s = String::from("## Link Check Results\n\nBroken links found:\n\n```\n");
        for line in combined.lines() {
            if line.contains("ERROR")
                || line.contains("broken")
                || line.contains("not found")
                || line.contains("-> ")
            {
                s.push_str(line);
                s.push('\n');
            }
        }
        if s.ends_with("```\n") {
            // No matching lines, include full output
            s.push_str(&combined);
        }
        s.push_str("```\n");
        s
    };

    std::fs::write("link_check_summary.md", &summary)?;
    output::info("Wrote link_check_summary.md");

    Ok(())
}
