pub mod lint;
mod stages;

use anyhow::{Result, bail};
use clap::Subcommand;

use crate::shared::{docker, output, project};
use stages::Stage;

#[derive(Subcommand)]
pub enum CiAction {
    /// Run a named CI stage
    #[command(trailing_var_arg = true)]
    Run {
        /// Stage name (e.g., format, lint-full, rust-fmt, econ-full, full, rust-all)
        stage: String,
        /// Extra arguments passed through to underlying tools
        #[arg(allow_hyphen_values = true)]
        extra: Vec<String>,
    },
    /// List all available CI stages
    List,
}

pub fn run(action: CiAction) -> Result<()> {
    match action {
        CiAction::Run { stage, extra } => run_stage(&stage, &extra),
        CiAction::List => {
            list_stages();
            Ok(())
        },
    }
}

fn run_stage(name: &str, extra: &[String]) -> Result<()> {
    let root = project::find_project_root()?;
    let compose = project::compose_file(&root);
    std::env::set_current_dir(&root)?;

    // Export user IDs for docker compose
    // SAFETY: single-threaded at this point (called before any thread spawning)
    unsafe {
        std::env::set_var("USER_ID", format!("{}", libc::getuid()));
        std::env::set_var("GROUP_ID", format!("{}", libc::getgid()));
        std::env::set_var("PYTHONDONTWRITEBYTECODE", "1");
        std::env::set_var("PYTHONPYCACHEPREFIX", "/tmp/pycache");
    }

    // Ensure cache dirs exist
    let home = std::env::var("HOME").unwrap_or_default();
    let _ = std::fs::create_dir_all(format!("{home}/.cache/uv"));
    let _ = std::fs::create_dir_all(format!("{home}/.cache/pre-commit"));

    let ruff_fmt = if project::is_ci() {
        "github"
    } else {
        "concise"
    };

    let stage = Stage::parse(name)?;
    let extra_str: Vec<&str> = extra.iter().map(|s| s.as_str()).collect();

    run_parsed_stage(&stage, &compose, ruff_fmt, &extra_str, &root)
}

fn run_parsed_stage(
    stage: &Stage,
    compose: &std::path::Path,
    ruff_fmt: &str,
    extra: &[&str],
    root: &std::path::Path,
) -> Result<()> {
    match stage {
        // ===================== Python stages =====================
        Stage::Format => {
            output::header("Running format checks");
            docker::run_python_ci(compose, &["ruff", "format", "--check", "--diff", "."], &[])?;
            docker::run_python_ci(
                compose,
                &["ruff", "check", "--select=I", "--diff", "."],
                &[],
            )
        },
        Stage::LintBasic => {
            output::header("Running basic linting");
            docker::run_python_ci(compose, &["ruff", "format", "--check", "."], &[])?;
            docker::run_python_ci(compose, &["ruff", "check", "--select=I", "."], &[])?;
            docker::run_python_ci(
                compose,
                &[
                    "ruff",
                    "check",
                    "--select=E9,F63,F7,F82",
                    &format!("--output-format={ruff_fmt}"),
                    ".",
                ],
                &[],
            )?;
            docker::run_python_ci(
                compose,
                &[
                    "ruff",
                    "check",
                    "--select=E,W,C90",
                    "--output-format=grouped",
                    ".",
                ],
                &[],
            )
        },
        Stage::LintFull => {
            output::header("Running full linting suite");
            docker::run_python_ci(compose, &["ruff", "format", "--check", "."], &[])?;
            docker::run_python_ci(compose, &["ruff", "check", "--select=I", "."], &[])?;
            docker::run_python_ci(
                compose,
                &["ruff", "check", &format!("--output-format={ruff_fmt}"), "."],
                &[],
            )?;
            docker::run_python_ci(compose, &["ty", "check", "."], &[])
        },
        Stage::Ruff => {
            output::header("Running Ruff (fast linter)");
            docker::run_python_ci(
                compose,
                &["ruff", "check", ".", "--output-format=github"],
                &[],
            )
        },
        Stage::RuffFix => {
            output::header("Running Ruff with auto-fix");
            docker::run_python_ci(compose, &["ruff", "check", ".", "--fix"], &[])
        },
        Stage::Bandit => {
            output::header("Running Bandit security scan");
            docker::run_python_ci(
                compose,
                &["bandit", "-r", ".", "-c", "pyproject.toml", "-f", "txt"],
                &[],
            )
        },
        Stage::Security => {
            // ChatGPT issue #1 fix: security checks now FAIL the pipeline
            // ChatGPT issue #7: widen static analysis -- run bandit at medium severity
            output::header("Running security scans");
            docker::run_python_ci(
                compose,
                &[
                    "bandit",
                    "-r",
                    ".",
                    "-c",
                    "pyproject.toml",
                    "-f",
                    "txt",
                    "--severity-level",
                    "medium",
                ],
                &[],
            )?;
            // Dependency check
            if let Ok(key) = std::env::var("SAFETY_API_KEY") {
                output::step("Using Safety with API key...");
                docker::run_python_ci(
                    compose,
                    &["safety", "scan", "--disable-optional-telemetry"],
                    &[("SAFETY_API_KEY", &key)],
                )?;
            } else {
                output::step("No SAFETY_API_KEY found, using pip-audit...");
                let audit_ok =
                    docker::run_python_ci_check(compose, &["python", "-m", "pip_audit"], &[])?;
                if !audit_ok {
                    output::warn("pip-audit reported vulnerabilities");
                    output::warn("Dependency audit is advisory; update packages when feasible");
                }
            }
            Ok(())
        },
        Stage::Test => {
            output::header("Running tests");
            let mut args = vec![
                "pytest",
                "tests/",
                "automation/corporate-proxy/tests/",
                "-v",
                "-n",
                "auto",
                "--cov=.",
                "--cov-report=xml",
                "--cov-report=html",
                "--cov-report=term",
            ];
            args.extend_from_slice(extra);
            let envs = [
                ("PYTHONDONTWRITEBYTECODE", "1"),
                ("PYTHONPYCACHEPREFIX", "/tmp/pycache"),
            ];
            docker::run_python_ci(compose, &args, &envs)?;

            output::header("Testing corporate proxy components");
            docker::run_python_ci(
                compose,
                &[
                    "python",
                    "automation/corporate-proxy/shared/scripts/test-auto-detection.py",
                ],
                &[],
            )?;
            docker::run_python_ci(
                compose,
                &[
                    "python",
                    "automation/corporate-proxy/shared/scripts/test-content-stripping.py",
                ],
                &[],
            )
        },
        Stage::YamlLint => {
            // ChatGPT issue #2 fix: accumulate errors and fail properly
            output::header("Validating YAML files");
            docker::run_python_ci(
                compose,
                &[
                    "bash",
                    "-c",
                    concat!(
                        "ERRORS=0; ",
                        "for file in $(find . -name '*.yml' -o -name '*.yaml'); do ",
                        "  echo \"Checking $file...\"; ",
                        "  if ! yamllint \"$file\"; then ERRORS=$((ERRORS+1)); fi; ",
                        "  if ! python3 -c \"import yaml; yaml.safe_load(open('$file'))\"; then ",
                        "    echo \"Invalid YAML: $file\"; ERRORS=$((ERRORS+1)); ",
                        "  fi; ",
                        "done; ",
                        "if [ $ERRORS -gt 0 ]; then ",
                        "  echo \"FAIL: $ERRORS YAML validation errors\"; exit 1; ",
                        "fi; ",
                        "echo \"OK: All YAML files valid\""
                    ),
                ],
                &[],
            )
        },
        Stage::JsonLint => {
            // ChatGPT issue #2 fix: accumulate errors and fail properly
            output::header("Validating JSON files");
            docker::run_python_ci(
                compose,
                &[
                    "bash",
                    "-c",
                    concat!(
                        "ERRORS=0; ",
                        "for file in $(find . -name '*.json'); do ",
                        "  echo \"Checking $file...\"; ",
                        "  if ! python3 -m json.tool \"$file\" > /dev/null; then ",
                        "    echo \"Invalid JSON: $file\"; ERRORS=$((ERRORS+1)); ",
                        "  fi; ",
                        "done; ",
                        "if [ $ERRORS -gt 0 ]; then ",
                        "  echo \"FAIL: $ERRORS JSON validation errors\"; exit 1; ",
                        "fi; ",
                        "echo \"OK: All JSON files valid\""
                    ),
                ],
                &[],
            )
        },
        Stage::LintShell => {
            output::header("Linting shell scripts with shellcheck");
            docker::run_python_ci(
                compose,
                &[
                    "bash",
                    "-c",
                    concat!(
                        "ISSUES=0; ",
                        "for script in $(find . -name '*.sh' -type f); do ",
                        "  echo \"Checking $script...\"; ",
                        "  if shellcheck -S warning \"$script\"; then ",
                        "    echo \"OK $script\"; ",
                        "  else ",
                        "    echo \"FAIL $script has issues\"; ISSUES=1; ",
                        "  fi; ",
                        "done; ",
                        "if [ $ISSUES -ne 0 ]; then ",
                        "  echo \"FAIL: Shell linting failed\"; exit 1; ",
                        "fi; ",
                        "echo \"OK: All shell scripts passed linting\""
                    ),
                ],
                &[],
            )
        },
        Stage::Autoformat => {
            output::header("Running autoformatters");
            docker::run_python_ci(compose, &["ruff", "format", "."], &[])?;
            docker::run_python_ci(compose, &["ruff", "check", "--select=I", "--fix", "."], &[])?;

            output::subheader("Running Rust autoformat");
            // Format tools/rust/* crates
            for entry in std::fs::read_dir(root.join("tools/rust"))? {
                let entry = entry?;
                let path = entry.path();
                if path.join("Cargo.toml").exists() {
                    let name = path.file_name().unwrap().to_string_lossy();
                    output::info(&format!("Formatting {name}..."));
                    let ws = format!("tools/rust/{name}");
                    let _ = docker::run_cargo(compose, &ws, &["fmt", "--all"]);
                }
            }
            // Format workspace roots
            for ws in &[
                "packages/economic_agents",
                "packages/injection_toolkit",
                "packages/tamper_briefcase",
                "packages/bioforge",
                "tools/mcp/mcp_core_rust",
            ] {
                if root.join(ws).exists() {
                    output::info(&format!("Formatting {ws}..."));
                    let _ = docker::run_cargo(compose, ws, &["fmt", "--all"]);
                }
            }
            Ok(())
        },
        Stage::TestGaea2 => {
            output::header("Running Gaea2 tests");
            let gaea2_url = std::env::var("GAEA2_MCP_URL")
                .unwrap_or_else(|_| "http://192.168.0.152:8007".to_string());
            let health_url = format!("{gaea2_url}/health");
            let reachable = reqwest::blocking::Client::builder()
                .timeout(std::time::Duration::from_secs(5))
                .build()
                .ok()
                .and_then(|c| c.get(&health_url).send().ok())
                .is_some_and(|r| r.status().is_success());
            if !reachable {
                output::warn(&format!(
                    "Gaea2 MCP server not reachable at {gaea2_url}, skipping"
                ));
                return Ok(());
            }
            output::success(&format!("Gaea2 MCP server available at {gaea2_url}"));
            let mut args = vec!["pytest", "tools/mcp/mcp_gaea2/tests/", "-v", "--tb=short"];
            args.extend_from_slice(extra);
            docker::run_python_ci(
                compose,
                &args,
                &[
                    ("PYTHONDONTWRITEBYTECODE", "1"),
                    ("PYTHONPYCACHEPREFIX", "/tmp/pycache"),
                    ("GAEA2_MCP_URL", &gaea2_url),
                ],
            )
        },
        Stage::TestAll => {
            output::header("Running all tests");
            let mut args = vec![
                "pytest",
                "tests/",
                "-v",
                "-n",
                "auto",
                "--cov=.",
                "--cov-report=xml",
                "--cov-report=term",
            ];
            args.extend_from_slice(extra);
            docker::run_python_ci(
                compose,
                &args,
                &[
                    ("PYTHONDONTWRITEBYTECODE", "1"),
                    ("PYTHONPYCACHEPREFIX", "/tmp/pycache"),
                ],
            )
        },
        Stage::TestCorporateProxy => {
            output::header("Running corporate proxy tests");
            let uid = std::env::var("USER_ID").unwrap_or_default();
            let gid = std::env::var("GROUP_ID").unwrap_or_default();
            let user_flag = format!("{uid}:{gid}");
            let cf = compose.to_string_lossy();
            let mut args: Vec<&str> = vec![
                "compose",
                "-f",
                &cf,
                "run",
                "--rm",
                "-e",
                "PYTHONDONTWRITEBYTECODE=1",
                "-e",
                "PYTHONPYCACHEPREFIX=/tmp/pycache",
                "--user",
                &user_flag,
                "python-ci",
                "python",
                "-m",
                "pytest",
                "automation/corporate-proxy/tests/",
                "-v",
                "-n",
                "auto",
                "--tb=short",
                "--no-header",
            ];
            args.extend(extra.iter().copied());
            crate::shared::process::run("docker", &args)
        },

        // ===================== Rust injection_toolkit stages =====================
        Stage::RustFmt => {
            output::header("Running Rust format checks");
            docker::run_cargo(compose, ".", &["fmt", "--all", "--", "--check"])
        },
        Stage::RustClippy => {
            output::header("Running Rust clippy lints");
            docker::run_cargo(
                compose,
                ".",
                &[
                    "clippy",
                    "--workspace",
                    "--all-targets",
                    "--exclude",
                    "itk-native-dll",
                    "--exclude",
                    "nms-cockpit-injector",
                    "--exclude",
                    "nms-video-launcher",
                    "--exclude",
                    "nms-video-overlay",
                    "--",
                    "-D",
                    "warnings",
                ],
            )
        },
        Stage::RustTest => {
            output::header("Running Rust tests");
            let mut args = vec![
                "test",
                "--workspace",
                "--exclude",
                "itk-native-dll",
                "--exclude",
                "nms-cockpit-injector",
                "--exclude",
                "nms-video-launcher",
                "--exclude",
                "nms-video-overlay",
            ];
            args.extend(extra.iter().copied());
            docker::run_cargo(compose, ".", &args)
        },
        Stage::RustBuild => {
            output::header("Building Rust workspace");
            docker::run_cargo(
                compose,
                ".",
                &[
                    "build",
                    "--workspace",
                    "--all-targets",
                    "--exclude",
                    "itk-native-dll",
                    "--exclude",
                    "nms-cockpit-injector",
                    "--exclude",
                    "nms-video-launcher",
                    "--exclude",
                    "nms-video-overlay",
                ],
            )
        },
        Stage::RustDeny => {
            output::header("Running cargo-deny license/security checks");
            docker::run_cargo(compose, ".", &["deny", "check"])
        },
        Stage::RustFull => {
            output::header("Running full Rust CI checks");
            run_parsed_stage(&Stage::RustFmt, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::RustClippy, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::RustTest, compose, ruff_fmt, extra, root)
        },

        // ===================== Rust nightly stages =====================
        Stage::RustLoom => {
            output::header("Running Loom concurrency tests");
            docker::build_rust_ci_nightly(compose)?;
            let cf = compose.to_string_lossy();
            crate::shared::process::run(
                "docker",
                &[
                    "compose",
                    "-f",
                    &cf,
                    "--profile",
                    "ci",
                    "run",
                    "--rm",
                    "-e",
                    "RUSTFLAGS=--cfg loom",
                    "rust-ci-nightly",
                    "cargo",
                    "test",
                    "-p",
                    "itk-shmem",
                    "loom_tests",
                    "--",
                    "--nocapture",
                ],
            )
        },
        Stage::RustMiri => {
            output::header("Running Miri UB detection");
            docker::build_rust_ci_nightly(compose)?;
            let cf = compose.to_string_lossy();
            crate::shared::process::run(
                "docker",
                &[
                    "compose",
                    "-f",
                    &cf,
                    "--profile",
                    "ci",
                    "run",
                    "--rm",
                    "rust-ci-nightly",
                    "cargo",
                    "+nightly",
                    "miri",
                    "test",
                    "-p",
                    "itk-shmem",
                    "--",
                    "seqlock",
                ],
            )?;
            crate::shared::process::run(
                "docker",
                &[
                    "compose",
                    "-f",
                    &cf,
                    "--profile",
                    "ci",
                    "run",
                    "--rm",
                    "rust-ci-nightly",
                    "cargo",
                    "+nightly",
                    "miri",
                    "test",
                    "-p",
                    "itk-protocol",
                ],
            )
        },
        Stage::RustCrossLinux => {
            output::header("Cross-compile check (x86_64 Linux)");
            docker::build_rust_ci_nightly(compose)?;
            let cf = compose.to_string_lossy();
            crate::shared::process::run(
                "docker",
                &[
                    "compose",
                    "-f",
                    &cf,
                    "--profile",
                    "ci",
                    "run",
                    "--rm",
                    "rust-ci-nightly",
                    "cargo",
                    "check",
                    "--target",
                    "x86_64-unknown-linux-gnu",
                    "-p",
                    "itk-protocol",
                    "-p",
                    "itk-shmem",
                    "-p",
                    "itk-ipc",
                ],
            )
        },
        Stage::RustCrossWindows => {
            output::header("Cross-compile check (Windows)");
            docker::build_rust_ci_nightly(compose)?;
            let cf = compose.to_string_lossy();
            crate::shared::process::run(
                "docker",
                &[
                    "compose",
                    "-f",
                    &cf,
                    "--profile",
                    "ci",
                    "run",
                    "--rm",
                    "rust-ci-nightly",
                    "cargo",
                    "check",
                    "--target",
                    "x86_64-pc-windows-gnu",
                    "-p",
                    "itk-protocol",
                    "-p",
                    "itk-shmem",
                    "-p",
                    "itk-ipc",
                ],
            )
        },
        Stage::RustAdvanced => {
            output::header("Running advanced Rust CI checks (nightly)");
            run_parsed_stage(&Stage::RustLoom, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::RustMiri, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::RustCrossLinux, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::RustCrossWindows, compose, ruff_fmt, extra, root)
        },

        // ===================== Workspace stages (generic) =====================
        Stage::WorkspaceFmt(ws) => {
            output::header(&format!("Running {ws} format checks"));
            run_ws_stages(compose, ws, &["fmt"], extra)
        },
        Stage::WorkspaceClippy(ws) => {
            output::header(&format!("Running {ws} clippy lints"));
            run_ws_stages(compose, ws, &["clippy"], extra)
        },
        Stage::WorkspaceTest(ws) => {
            output::header(&format!("Running {ws} tests"));
            run_ws_stages(compose, ws, &["test"], extra)
        },
        Stage::WorkspaceBuild(ws) => {
            output::header(&format!("Building {ws} workspace"));
            run_ws_stages(compose, ws, &["build"], extra)
        },
        Stage::WorkspaceDeny(ws) => {
            output::header(&format!("Running {ws} cargo-deny checks"));
            docker::run_cargo(compose, ws.path(), &["deny", "check"])
        },
        Stage::WorkspaceDoc(ws) => {
            output::header(&format!("Generating {ws} documentation"));
            docker::run_cargo(
                compose,
                ws.path(),
                &[
                    "doc",
                    "--workspace",
                    "--no-deps",
                    "--document-private-items",
                ],
            )
        },
        Stage::WorkspaceCoverage(ws) => {
            output::header(&format!("Running {ws} test coverage"));
            let mut args = vec![
                "llvm-cov",
                "--workspace",
                "--lcov",
                "--output-path",
                "lcov.info",
            ];
            args.extend(extra.iter().copied());
            docker::run_cargo(compose, ws.path(), &args)
        },
        Stage::WorkspaceFull(ws) => {
            output::header(&format!("Running full {ws} CI checks"));
            run_parsed_stage(
                &Stage::WorkspaceFmt(ws.clone()),
                compose,
                ruff_fmt,
                extra,
                root,
            )?;
            run_parsed_stage(
                &Stage::WorkspaceClippy(ws.clone()),
                compose,
                ruff_fmt,
                extra,
                root,
            )?;
            run_parsed_stage(
                &Stage::WorkspaceTest(ws.clone()),
                compose,
                ruff_fmt,
                extra,
                root,
            )
        },

        // ===================== BioForge (special: includes MCP server) =====================
        Stage::BioFmt => {
            output::header("Running BioForge format checks");
            docker::run_cargo(
                compose,
                "packages/bioforge",
                &["fmt", "--all", "--", "--check"],
            )?;
            output::header("Running MCP BioForge format checks");
            docker::run_cargo(
                compose,
                "tools/mcp/mcp_bioforge",
                &["fmt", "--all", "--", "--check"],
            )
        },
        Stage::BioClippy => {
            output::header("Running BioForge clippy lints");
            docker::run_cargo(
                compose,
                "packages/bioforge",
                &[
                    "clippy",
                    "--workspace",
                    "--all-targets",
                    "--",
                    "-D",
                    "warnings",
                ],
            )?;
            output::header("Running MCP BioForge clippy lints");
            docker::run_cargo(
                compose,
                "tools/mcp/mcp_bioforge",
                &["clippy", "--all-targets", "--", "-D", "warnings"],
            )
        },
        Stage::BioBuild => {
            output::header("Building BioForge workspace");
            docker::run_cargo(
                compose,
                "packages/bioforge",
                &["build", "--workspace", "--all-targets"],
            )?;
            output::header("Building MCP BioForge server");
            docker::run_cargo(
                compose,
                "tools/mcp/mcp_bioforge",
                &["build", "--all-targets"],
            )
        },
        Stage::BioFull => {
            output::header("Running full BioForge CI checks");
            run_parsed_stage(&Stage::BioFmt, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::BioClippy, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(
                &Stage::WorkspaceTest(stages::Workspace::Bioforge),
                compose,
                ruff_fmt,
                extra,
                root,
            )
        },

        // ===================== Tamper Briefcase (special: aarch64 exclusions) =====================
        Stage::TamperClippy => {
            output::header("Running Tamper Briefcase clippy lints");
            for krate in &[
                "tamper-common",
                "tamper-gate",
                "tamper-challenge",
                "tamper-recovery",
            ] {
                output::subheader(&format!("Linting: {krate}"));
                docker::run_cargo(
                    compose,
                    "packages/tamper_briefcase",
                    &[
                        "clippy",
                        "-p",
                        krate,
                        "--all-targets",
                        "--",
                        "-D",
                        "warnings",
                    ],
                )?;
            }
            Ok(())
        },
        Stage::TamperTest => {
            output::header("Running Tamper Briefcase tests");
            for krate in &[
                "tamper-common",
                "tamper-gate",
                "tamper-challenge",
                "tamper-recovery",
            ] {
                output::subheader(&format!("Testing: {krate}"));
                let mut args = vec!["test", "-p", krate];
                args.extend(extra.iter().copied());
                docker::run_cargo(compose, "packages/tamper_briefcase", &args)?;
            }
            Ok(())
        },
        Stage::TamperBuild => {
            output::header("Building Tamper Briefcase workspace");
            for krate in &[
                "tamper-common",
                "tamper-gate",
                "tamper-challenge",
                "tamper-recovery",
            ] {
                output::subheader(&format!("Building: {krate}"));
                docker::run_cargo(
                    compose,
                    "packages/tamper_briefcase",
                    &["build", "-p", krate, "--all-targets"],
                )?;
            }
            Ok(())
        },
        Stage::TamperFull => {
            output::header("Running full Tamper Briefcase CI checks");
            run_parsed_stage(
                &Stage::WorkspaceFmt(stages::Workspace::TamperBriefcase),
                compose,
                ruff_fmt,
                extra,
                root,
            )?;
            run_parsed_stage(&Stage::TamperClippy, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::TamperTest, compose, ruff_fmt, extra, root)
        },

        // ===================== Iterator stages (wrapper, mcp-servers, tools) =====================
        Stage::IterFmt(iter) => run_iter_stage(compose, iter, "fmt", extra, root),
        Stage::IterClippy(iter) => run_iter_stage(compose, iter, "clippy", extra, root),
        Stage::IterTest(iter) => run_iter_stage(compose, iter, "test", extra, root),
        Stage::IterFull(iter) => {
            run_iter_stage(compose, iter, "fmt", extra, root)?;
            run_iter_stage(compose, iter, "clippy", extra, root)?;
            run_iter_stage(compose, iter, "test", extra, root)
        },

        // ===================== Composite stages =====================
        Stage::Full => {
            // ChatGPT issue #3 fix: "full" now includes security, yaml, json, and Rust
            output::header("Running full CI checks");
            run_parsed_stage(&Stage::Format, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::LintBasic, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::LintFull, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::LintShell, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::Security, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::YamlLint, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::JsonLint, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::Test, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::TestCorporateProxy, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::RustFull, compose, ruff_fmt, extra, root)
        },
        Stage::RustAll => {
            output::header("Running ALL Rust CI checks");
            run_parsed_stage(&Stage::RustFull, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(
                &Stage::WorkspaceFull(stages::Workspace::EconomicAgents),
                compose,
                ruff_fmt,
                extra,
                root,
            )?;
            run_parsed_stage(
                &Stage::WorkspaceFull(stages::Workspace::McpCore),
                compose,
                ruff_fmt,
                extra,
                root,
            )?;
            run_parsed_stage(&Stage::BioFull, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(&Stage::TamperFull, compose, ruff_fmt, extra, root)?;
            run_parsed_stage(
                &Stage::IterFull(stages::IterGroup::Wrapper),
                compose,
                ruff_fmt,
                extra,
                root,
            )?;
            run_parsed_stage(
                &Stage::IterFull(stages::IterGroup::McpServers),
                compose,
                ruff_fmt,
                extra,
                root,
            )?;
            run_parsed_stage(
                &Stage::IterFull(stages::IterGroup::Tools),
                compose,
                ruff_fmt,
                extra,
                root,
            )
        },
    }
}

/// Run workspace-level cargo stages (fmt/clippy/test/build)
fn run_ws_stages(
    compose: &std::path::Path,
    ws: &stages::Workspace,
    ops: &[&str],
    extra: &[&str],
) -> Result<()> {
    let path = ws.path();
    for op in ops {
        match *op {
            "fmt" => docker::run_cargo(compose, path, &["fmt", "--all", "--", "--check"])?,
            "clippy" => docker::run_cargo(
                compose,
                path,
                &[
                    "clippy",
                    "--workspace",
                    "--all-targets",
                    "--",
                    "-D",
                    "warnings",
                ],
            )?,
            "test" => {
                let mut args = vec!["test", "--workspace"];
                args.extend(extra.iter().copied());
                docker::run_cargo(compose, path, &args)?;
            },
            "build" => {
                docker::run_cargo(compose, path, &["build", "--workspace", "--all-targets"])?
            },
            _ => bail!("unknown workspace op: {op}"),
        }
    }
    Ok(())
}

/// Run iterator-based stages (wrapper, mcp-servers, tools) that loop over directories
fn run_iter_stage(
    compose: &std::path::Path,
    group: &stages::IterGroup,
    op: &str,
    extra: &[&str],
    root: &std::path::Path,
) -> Result<()> {
    let (base_dir, skip_list) = group.config();
    let search_dir = root.join(base_dir);

    if !search_dir.exists() {
        output::warn(&format!(
            "{} does not exist, skipping",
            search_dir.display()
        ));
        return Ok(());
    }

    let op_name = match op {
        "fmt" => "format checks",
        "clippy" => "clippy lints",
        "test" => "tests",
        _ => op,
    };
    output::header(&format!("Running {group} {op_name}"));

    let mut failed = false;
    for entry in std::fs::read_dir(&search_dir)? {
        let entry = entry?;
        let path = entry.path();
        let name = path.file_name().unwrap().to_string_lossy().to_string();

        if skip_list.contains(&name.as_str()) {
            continue;
        }
        if !path.join("Cargo.toml").exists() {
            continue;
        }

        let ws_path = format!("{base_dir}/{name}");
        output::subheader(&format!(
            "{}: {name}",
            match op {
                "fmt" => "Checking format",
                "clippy" => "Linting",
                "test" => "Testing",
                _ => op,
            }
        ));

        let result = match op {
            "fmt" => docker::run_cargo(compose, &ws_path, &["fmt", "--all", "--", "--check"]),
            "clippy" => docker::run_cargo(
                compose,
                &ws_path,
                &["clippy", "--all-targets", "--", "-D", "warnings"],
            ),
            "test" => {
                let mut args = vec!["test"];
                args.extend(extra.iter().copied());
                docker::run_cargo(compose, &ws_path, &args)
            },
            _ => bail!("unknown iter op: {op}"),
        };

        if result.is_err() {
            failed = true;
        }
    }

    if failed {
        bail!("one or more {group} {op_name} failed");
    }
    Ok(())
}

fn list_stages() {
    println!("Available CI stages:");
    println!();
    println!("  Python:");
    println!("    format, lint-basic, lint-full, lint-shell, ruff, ruff-fix");
    println!("    bandit, security, test, test-gaea2, test-all, test-corporate-proxy");
    println!("    yaml-lint, json-lint, autoformat, full");
    println!();
    println!("  Rust (injection_toolkit):");
    println!("    rust-fmt, rust-clippy, rust-test, rust-build, rust-deny, rust-full");
    println!();
    println!("  Rust (nightly):");
    println!("    rust-loom, rust-miri, rust-cross-linux, rust-cross-windows, rust-advanced");
    println!();
    println!("  Rust (economic_agents):");
    println!(
        "    econ-fmt, econ-clippy, econ-test, econ-build, econ-deny, econ-doc, econ-coverage, econ-full"
    );
    println!();
    println!("  Rust (mcp_core_rust):");
    println!("    mcp-fmt, mcp-clippy, mcp-test, mcp-build, mcp-deny, mcp-doc, mcp-full");
    println!();
    println!("  Rust (bioforge+mcp):");
    println!("    bio-fmt, bio-clippy, bio-test, bio-build, bio-deny, bio-full");
    println!();
    println!("  Rust (tamper_briefcase):");
    println!("    tamper-fmt, tamper-clippy, tamper-test, tamper-build, tamper-deny, tamper-full");
    println!();
    println!("  Rust (wrapper_guard):");
    println!("    wrapper-fmt, wrapper-clippy, wrapper-test, wrapper-full");
    println!();
    println!("  Rust (mcp_servers):");
    println!("    mcp-servers-fmt, mcp-servers-clippy, mcp-servers-test, mcp-servers-full");
    println!();
    println!("  Rust (standalone tools):");
    println!("    tools-fmt, tools-clippy, tools-test, tools-full");
    println!();
    println!("  Composite:");
    println!("    rust-all, full");
}
