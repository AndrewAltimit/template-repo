//! `automation-cli ci` -- containerized CI stages.
//!
//! Python stages run in the `python-ci` compose service, Rust stages in
//! `rust-ci`. Stage names are defined in [`stages::CATALOG`].

mod doctor;
pub mod lint;
mod scripts;
mod stages;

use std::path::{Path, PathBuf};

use anyhow::{Result, bail};
use clap::Subcommand;

use crate::shared::{docker, output, project};
use stages::{CargoOp, IterGroup, Stage, Workspace};

#[derive(Subcommand)]
pub enum CiAction {
    /// Run a named CI stage
    #[command(trailing_var_arg = true)]
    Run {
        /// Stage name (e.g., format, lint-full, econ-full, full, rust-all); see `ci list`
        stage: String,
        /// Extra arguments passed through to underlying tools (pytest / cargo test)
        #[arg(allow_hyphen_values = true)]
        extra: Vec<String>,
    },
    /// List all available CI stages
    List {
        /// Print bare stage names, one per line (for scripts and completion)
        #[arg(long)]
        names: bool,
    },
    /// Check that stage names referenced by workflows/docs exist and that
    /// every workspace and crate group the stages expect is present
    Doctor,
}

pub fn run(action: CiAction) -> Result<()> {
    match action {
        CiAction::Run { stage, extra } => run_stage(&stage, &extra),
        CiAction::List { names } => {
            list_stages(names);
            Ok(())
        },
        CiAction::Doctor => doctor::run(),
    }
}

/// Shared state for executing stages.
struct Ctx<'a> {
    root: PathBuf,
    compose: PathBuf,
    /// `--output-format` for ruff: `github` annotations in CI, `concise` locally.
    ruff_fmt: &'static str,
    extra: &'a [&'a str],
}

fn run_stage(name: &str, extra: &[String]) -> Result<()> {
    // Parse first: a typo should fail fast, before any docker work.
    let stage = Stage::parse(name)?;

    let root = project::enter_project_root()?;
    project::export_compose_env();
    ensure_cache_dirs();

    let extra: Vec<&str> = extra.iter().map(String::as_str).collect();
    let ctx = Ctx {
        compose: project::compose_file(&root),
        root,
        ruff_fmt: if project::is_ci() {
            "github"
        } else {
            "concise"
        },
        extra: &extra,
    };
    ctx.run(stage)
}

/// Host directories bind-mounted by the python-ci service. If they do not
/// exist, docker creates them owned by root, which breaks later runs.
fn ensure_cache_dirs() {
    let Some(home) = std::env::var_os("HOME").filter(|h| !h.is_empty()) else {
        return;
    };
    for sub in [".cache/uv", ".cache/pre-commit"] {
        let dir = Path::new(&home).join(sub);
        if let Err(e) = std::fs::create_dir_all(&dir) {
            output::warn(&format!("could not create {}: {e}", dir.display()));
        }
    }
}

/// Run the pip dependency audit (Safety with an API key, pip-audit otherwise).
/// Returns Ok(false) if vulnerabilities were reported.
pub(crate) fn dependency_audit(compose: &Path) -> Result<bool> {
    if let Ok(key) = std::env::var("SAFETY_API_KEY") {
        output::step("Using Safety with API key...");
        docker::run_python_ci_check(
            compose,
            &["safety", "scan", "--disable-optional-telemetry"],
            &[("SAFETY_API_KEY", &key)],
        )
    } else {
        output::step("No SAFETY_API_KEY found, using pip-audit...");
        docker::run_python_ci_check(compose, &["python", "-m", "pip_audit"], &[])
    }
}

impl Ctx<'_> {
    fn py(&self, args: &[&str]) -> Result<()> {
        docker::run_python_ci(&self.compose, args, &[])
    }

    /// Run a test command in python-ci with the pass-through args appended
    /// and bytecode caching redirected away from the bind-mounted source tree.
    fn py_with_extra(&self, base: &[&str], env: &[(&str, &str)]) -> Result<()> {
        let mut args = base.to_vec();
        args.extend_from_slice(self.extra);
        let mut envs = PY_TEST_ENV.to_vec();
        envs.extend_from_slice(env);
        docker::run_python_ci(&self.compose, &args, &envs)
    }

    fn cargo(&self, dir: &str, args: &[&str]) -> Result<()> {
        docker::run_cargo(&self.compose, dir, args)
    }

    fn run_all(&self, stages: &[Stage]) -> Result<()> {
        stages.iter().try_for_each(|s| self.run(*s))
    }

    fn run(&self, stage: Stage) -> Result<()> {
        match stage {
            Stage::Format => {
                output::header("Running format checks");
                self.py(&["ruff", "format", "--check", "--diff", "."])?;
                self.py(&["ruff", "check", "--select=I", "--diff", "."])
            },
            Stage::LintBasic => {
                output::header("Running basic linting");
                self.py(&["ruff", "format", "--check", "."])?;
                self.py(&["ruff", "check", "--select=I", "."])?;
                let fmt = format!("--output-format={}", self.ruff_fmt);
                self.py(&["ruff", "check", "--select=E9,F63,F7,F82", &fmt, "."])?;
                self.py(&[
                    "ruff",
                    "check",
                    "--select=E,W,C90",
                    "--ignore=E501,E402",
                    "--output-format=grouped",
                    ".",
                ])
            },
            Stage::LintFull => {
                output::header("Running full linting suite");
                self.py(&["ruff", "format", "--check", "."])?;
                self.py(&["ruff", "check", "--select=I", "."])?;
                let fmt = format!("--output-format={}", self.ruff_fmt);
                self.py(&["ruff", "check", &fmt, "."])?;
                // ty errors are informational (matches `lint full` behavior)
                if !docker::run_python_ci_check(&self.compose, &["ty", "check", "."], &[])? {
                    output::info("ty found type errors (informational)");
                }
                Ok(())
            },
            Stage::Ruff => {
                output::header("Running Ruff (fast linter)");
                self.py(&["ruff", "check", ".", "--output-format=github"])
            },
            Stage::RuffFix => {
                output::header("Running Ruff with auto-fix");
                self.py(&["ruff", "check", ".", "--fix"])
            },
            Stage::Bandit => {
                output::header("Running Bandit security scan");
                self.py(&["bandit", "-r", ".", "-c", "pyproject.toml", "-f", "txt"])
            },
            Stage::Security => self.security(),
            Stage::Test => {
                output::header("Running tests");
                self.py_with_extra(
                    &[
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
                    ],
                    &[],
                )?;
                output::header("Testing corporate proxy components");
                self.py(&[
                    "python",
                    "automation/corporate-proxy/shared/scripts/test-auto-detection.py",
                ])?;
                self.py(&[
                    "python",
                    "automation/corporate-proxy/shared/scripts/test-content-stripping.py",
                ])
            },
            Stage::YamlLint => {
                output::header("Validating YAML files");
                self.py(&["bash", "-c", scripts::YAML_LINT])
            },
            Stage::JsonLint => {
                output::header("Validating JSON files");
                self.py(&["bash", "-c", scripts::JSON_LINT])
            },
            Stage::LintShell => {
                output::header("Linting shell scripts with shellcheck");
                self.py(&["bash", "-c", scripts::SHELL_LINT])
            },
            Stage::Autoformat => self.autoformat(),
            Stage::TestGaea2 => self.test_gaea2(),
            Stage::TestAll => {
                output::header("Running all tests");
                self.py_with_extra(
                    &[
                        "pytest",
                        "tests/",
                        "-v",
                        "-n",
                        "auto",
                        "--cov=.",
                        "--cov-report=xml",
                        "--cov-report=term",
                    ],
                    &[],
                )
            },
            Stage::TestCorporateProxy => {
                output::header("Running corporate proxy tests");
                self.py_with_extra(
                    &[
                        "python",
                        "-m",
                        "pytest",
                        "automation/corporate-proxy/tests/",
                        "-v",
                        "-n",
                        "auto",
                        "--tb=short",
                        "--no-header",
                    ],
                    &[],
                )
            },

            // ===================== Rust workspaces =====================
            Stage::Workspace(ws, op) => {
                output::header(&format!("Running {ws} {}", op.noun()));
                self.cargo(ws.path(), &op.cargo_args(true, self.extra))
            },
            Stage::WorkspaceDeny(ws) => {
                output::header(&format!("Running {ws} cargo-deny checks"));
                self.cargo(ws.path(), &["deny", "check"])
            },
            Stage::WorkspaceDoc(ws) => {
                output::header(&format!("Generating {ws} documentation"));
                self.cargo(
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
                args.extend_from_slice(self.extra);
                self.cargo(ws.path(), &args)
            },
            Stage::WorkspaceFull(ws) => {
                output::header(&format!("Running full {ws} CI checks"));
                self.run_all(&CargoOp::FULL.map(|op| Stage::Workspace(ws, op)))
            },

            // ============ BioForge (workspace + MCP BioForge server) ============
            Stage::Bio(op) => {
                output::header(&format!("Running BioForge {}", op.noun()));
                self.cargo(Workspace::Bioforge.path(), &op.cargo_args(true, self.extra))?;
                output::header(&format!("Running MCP BioForge {}", op.noun()));
                self.cargo("tools/mcp/mcp_bioforge", &op.cargo_args(false, self.extra))
            },
            Stage::BioFull => {
                output::header("Running full BioForge CI checks");
                self.run_all(&[
                    Stage::Bio(CargoOp::Fmt),
                    Stage::Bio(CargoOp::Clippy),
                    Stage::Workspace(Workspace::Bioforge, CargoOp::Test),
                ])
            },

            // ====== Tamper Briefcase (per crate: skips aarch64-only crates) ======
            Stage::Tamper(op) => {
                output::header(&format!("Running Tamper Briefcase {}", op.noun()));
                for krate in TAMPER_HOST_CRATES {
                    output::subheader(&format!("{}: {krate}", op.verb()));
                    let args = package_args(op, krate, self.extra);
                    self.cargo(Workspace::TamperBriefcase.path(), &args)?;
                }
                Ok(())
            },
            Stage::TamperFull => {
                output::header("Running full Tamper Briefcase CI checks");
                self.run_all(&[
                    Stage::Workspace(Workspace::TamperBriefcase, CargoOp::Fmt),
                    Stage::Tamper(CargoOp::Clippy),
                    Stage::Tamper(CargoOp::Test),
                ])
            },

            // ===================== Crate groups =====================
            Stage::Iter(group, op) => self.run_iter(group, op),
            Stage::IterFull(group) => CargoOp::FULL
                .iter()
                .try_for_each(|op| self.run_iter(group, *op)),

            // ===================== Composite =====================
            Stage::Full => {
                output::header("Running full CI checks");
                // `test` already runs automation/corporate-proxy/tests/, so the
                // separate test-corporate-proxy stage is not repeated here.
                self.run_all(&[
                    Stage::Format,
                    Stage::LintBasic,
                    Stage::LintFull,
                    Stage::LintShell,
                    Stage::Security,
                    Stage::YamlLint,
                    Stage::JsonLint,
                    Stage::Test,
                ])
            },
            Stage::RustAll => {
                output::header("Running ALL Rust CI checks");
                self.run_all(&[
                    Stage::WorkspaceFull(Workspace::EconomicAgents),
                    Stage::WorkspaceFull(Workspace::McpCore),
                    Stage::BioFull,
                    Stage::TamperFull,
                    Stage::WorkspaceFull(Workspace::SleeperAgents),
                    Stage::IterFull(IterGroup::Wrapper),
                    Stage::IterFull(IterGroup::McpServers),
                    Stage::IterFull(IterGroup::Tools),
                ])
            },
        }
    }

    fn security(&self) -> Result<()> {
        output::header("Running security scans");
        // Medium+ severity findings fail the stage.
        self.py(&[
            "bandit",
            "-r",
            ".",
            "-c",
            "pyproject.toml",
            "-f",
            "txt",
            "--severity-level",
            "medium",
        ])?;
        if !dependency_audit(&self.compose)? {
            output::warn("Dependency audit reported vulnerabilities");
            output::warn("Dependency audit is advisory; update packages when feasible");
        }
        Ok(())
    }

    /// Gaea2 MCP server: Rust unit tests (always), then a live health check
    /// against the remote Windows host, plus the legacy pytest suite if one
    /// still exists. The remote server being down is a warning, not a failure.
    fn test_gaea2(&self) -> Result<()> {
        output::header("Running Gaea2 tests");
        output::subheader("Unit tests (tools/mcp/mcp_gaea2)");
        self.cargo(GAEA2_DIR, &CargoOp::Test.cargo_args(false, self.extra))?;

        let gaea2_url = std::env::var("GAEA2_MCP_URL")
            .unwrap_or_else(|_| "http://192.168.0.152:8007".to_string());
        let health_url = format!("{}/health", gaea2_url.trim_end_matches('/'));
        let reachable = crate::shared::http::client(std::time::Duration::from_secs(5))
            .is_ok_and(|c| crate::shared::http::get_ok(&c, &health_url));
        if !reachable {
            output::warn(&format!(
                "Gaea2 MCP server not reachable at {gaea2_url}, skipping live checks"
            ));
            return Ok(());
        }
        output::success(&format!("Gaea2 MCP server healthy at {gaea2_url}"));

        let py_tests = format!("{GAEA2_DIR}/tests");
        if self.root.join(&py_tests).is_dir() {
            self.py_with_extra(
                &["pytest", &py_tests, "-v", "--tb=short"],
                &[("GAEA2_MCP_URL", &gaea2_url)],
            )?;
        }
        Ok(())
    }

    /// Format Python and every Rust crate/workspace in one pass.
    ///
    /// All `cargo fmt` runs share a single rust-ci container (one container
    /// start instead of one per crate). Failures are reported, not swallowed,
    /// but do not abort the remaining crates.
    fn autoformat(&self) -> Result<()> {
        output::header("Running autoformatters");
        self.py(&["ruff", "format", "."])?;
        self.py(&["ruff", "check", "--select=I", "--fix", "."])?;

        output::subheader("Running Rust autoformat");
        let dirs = rust_format_targets(&self.root);
        if dirs.is_empty() {
            output::warn("No Rust crates found to format");
            return Ok(());
        }
        let script = scripts::cargo_fmt_all(&dirs);
        if let Err(e) = docker::run_rust_ci_script(&self.compose, &script) {
            output::warn(&format!("Some Rust crates could not be formatted: {e}"));
        }
        Ok(())
    }

    /// Run a cargo op over every crate in an [`IterGroup`], continuing past
    /// failures and reporting all failing crates at the end.
    fn run_iter(&self, group: IterGroup, op: CargoOp) -> Result<()> {
        let search_dir = self.root.join(group.base_dir());
        if !search_dir.is_dir() {
            output::warn(&format!(
                "{} does not exist, skipping",
                search_dir.display()
            ));
            return Ok(());
        }
        output::header(&format!("Running {group} {}", op.noun()));

        let crates = discover_group(&self.root, group)?;
        if crates.is_empty() {
            output::warn(&format!("No crates found for {group}"));
            return Ok(());
        }
        let mut failed = Vec::new();
        for name in &crates {
            output::subheader(&format!("{}: {name}", op.verb()));
            let dir = format!("{}/{name}", group.base_dir());
            if let Err(e) = self.cargo(&dir, &op.cargo_args(false, self.extra)) {
                output::fail(&format!("{name}: {e}"));
                failed.push(name.as_str());
            }
        }
        if !failed.is_empty() {
            bail!("{group} {} failed for: {}", op.noun(), failed.join(", "));
        }
        Ok(())
    }
}

/// Gaea2 MCP server crate (tested by the `test-gaea2` stage).
const GAEA2_DIR: &str = "tools/mcp/mcp_gaea2";

/// Container env for pytest runs (compose does not forward host env by default).
const PY_TEST_ENV: [(&str, &str); 2] = [
    ("PYTHONDONTWRITEBYTECODE", "1"),
    ("PYTHONPYCACHEPREFIX", "/tmp/pycache"),
];

/// Tamper Briefcase crates that build on x86_64 hosts (the rest are aarch64-only).
const TAMPER_HOST_CRATES: [&str; 4] = [
    "tamper-common",
    "tamper-gate",
    "tamper-challenge",
    "tamper-recovery",
];

/// Cargo args for `op` restricted to one package: `-p <crate>` is inserted
/// right after the subcommand so it precedes any `--` separator.
fn package_args<'a>(op: CargoOp, krate: &'a str, extra: &[&'a str]) -> Vec<&'a str> {
    let mut args = op.cargo_args(false, extra);
    args.splice(1..1, ["-p", krate]);
    args
}

/// Sorted names of the crate directories (containing Cargo.toml) in a group.
fn discover_group(root: &Path, group: IterGroup) -> Result<Vec<String>> {
    let mut names = crate_dirs(&root.join(group.base_dir()))?;
    names.retain(|n| group.includes(n));
    Ok(names)
}

/// Sorted names of subdirectories of `dir` that contain a Cargo.toml.
fn crate_dirs(dir: &Path) -> Result<Vec<String>> {
    let mut names = Vec::new();
    let Ok(entries) = std::fs::read_dir(dir) else {
        return Ok(names);
    };
    for entry in entries {
        let path = entry?.path();
        if path.join("Cargo.toml").is_file()
            && let Some(name) = path.file_name().and_then(|n| n.to_str())
        {
            names.push(name.to_string());
        }
    }
    names.sort();
    Ok(names)
}

/// Every Rust crate / workspace root the `autoformat` stage should format,
/// relative to the project root.
fn rust_format_targets(root: &Path) -> Vec<String> {
    let mut dirs = Vec::new();
    for base in ["tools/rust", "tools/mcp"] {
        if let Ok(names) = crate_dirs(&root.join(base)) {
            dirs.extend(names.into_iter().map(|n| format!("{base}/{n}")));
        }
    }
    for ws in Workspace::ALL {
        let p = ws.path().to_string();
        if root.join(&p).join("Cargo.toml").is_file() && !dirs.contains(&p) {
            dirs.push(p);
        }
    }
    dirs
}

fn list_stages(names_only: bool) {
    if names_only {
        for name in stages::all_stage_names() {
            println!("{name}");
        }
        return;
    }
    println!("Available CI stages:");
    for group in stages::CATALOG {
        println!();
        println!("  {}:", group.title);
        for line in wrap_names(group.names, 76) {
            println!("    {line}");
        }
    }
    println!();
    println!("Extra arguments after the stage name are forwarded to pytest / cargo test.");
}

/// Join names with ", " into lines no wider than `width`.
fn wrap_names(names: &[&str], width: usize) -> Vec<String> {
    let mut lines = Vec::new();
    let mut cur = String::new();
    for name in names {
        if !cur.is_empty() && cur.len() + 2 + name.len() > width {
            cur.push(',');
            lines.push(std::mem::take(&mut cur));
        }
        if !cur.is_empty() {
            cur.push_str(", ");
        }
        cur.push_str(name);
    }
    if !cur.is_empty() {
        lines.push(cur);
    }
    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn package_args_insert_before_separator() {
        assert_eq!(
            package_args(CargoOp::Clippy, "tamper-gate", &[]),
            [
                "clippy",
                "-p",
                "tamper-gate",
                "--all-targets",
                "--",
                "-D",
                "warnings"
            ]
        );
        assert_eq!(
            package_args(CargoOp::Test, "tamper-gate", &["--", "--nocapture"]),
            ["test", "-p", "tamper-gate", "--", "--nocapture"]
        );
    }

    #[test]
    fn wrap_names_respects_width() {
        let lines = wrap_names(&["aaaa", "bbbb", "cccc"], 10);
        assert_eq!(lines, ["aaaa, bbbb,", "cccc"]);
        assert_eq!(wrap_names(&[], 10), Vec::<String>::new());
    }

    #[test]
    fn crate_discovery_is_sorted_and_filtered() {
        let dir = tempfile::tempdir().unwrap();
        let base = dir.path().join("tools/rust");
        for name in ["zeta", "git-guard", "alpha", "not-a-crate"] {
            std::fs::create_dir_all(base.join(name)).unwrap();
            if name != "not-a-crate" {
                std::fs::write(base.join(name).join("Cargo.toml"), "").unwrap();
            }
        }
        assert_eq!(
            discover_group(dir.path(), IterGroup::Tools).unwrap(),
            ["alpha", "zeta"]
        );
        assert_eq!(
            discover_group(dir.path(), IterGroup::Wrapper).unwrap(),
            ["git-guard"]
        );
        // Missing directory yields no crates rather than an error.
        assert!(
            discover_group(dir.path(), IterGroup::McpServers)
                .unwrap()
                .is_empty()
        );
    }

    #[test]
    fn format_targets_include_mcp_crates_and_workspaces() {
        let dir = tempfile::tempdir().unwrap();
        for p in [
            "tools/rust/a",
            "tools/mcp/mcp_x",
            "tools/mcp/mcp_core_rust",
            "packages/bioforge",
        ] {
            std::fs::create_dir_all(dir.path().join(p)).unwrap();
            std::fs::write(dir.path().join(p).join("Cargo.toml"), "").unwrap();
        }
        let targets = rust_format_targets(dir.path());
        assert_eq!(
            targets,
            [
                "tools/rust/a",
                "tools/mcp/mcp_core_rust",
                "tools/mcp/mcp_x",
                "packages/bioforge"
            ]
        );
    }
}
