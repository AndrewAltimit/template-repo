//! `automation-cli proxy` -- build and smoke-test the corporate proxy
//! containers (`automation/corporate-proxy`).

use std::process::{Child, Command, Stdio};
use std::time::Duration;

use anyhow::{Context, Result, bail};
use clap::{Subcommand, ValueEnum};
use owo_colors::OwoColorize;

use crate::shared::{http, output, process, project};

/// Compose profile shared by all proxy services.
const PROFILE: &str = "proxy";
const UNIFIED_API: &str = "automation/corporate-proxy/shared/services/unified_tool_api.py";

#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
pub enum TestMode {
    /// Start the unified tool API locally and check /health
    Quick,
    /// Build the crush-proxy image
    Crush,
    /// Build the opencode-proxy image
    Opencode,
    /// Build the gemini-proxy image
    Gemini,
    /// Start the unified tool API locally and exercise /tools and /execute
    Api,
    /// Start crush-proxy + opencode-proxy containers and check their /health
    Integration,
    /// Every mode above
    All,
}

#[derive(Subcommand)]
pub enum ProxyAction {
    /// Build corporate proxy containers
    Build {
        /// Target architecture, e.g. amd64 or arm64 (auto-detected if not specified)
        #[arg(long)]
        arch: Option<String>,
    },
    /// Run corporate proxy test suite
    Test {
        /// Test mode
        #[arg(value_enum, default_value = "quick")]
        mode: TestMode,
    },
}

pub fn run(action: ProxyAction) -> Result<()> {
    project::enter_project_root()?;
    match action {
        ProxyAction::Build { arch } => build(arch),
        ProxyAction::Test { mode } => run_tests(mode),
    }
}

fn build(arch: Option<String>) -> Result<()> {
    output::header("Building corporate proxy containers");
    let arch = arch.unwrap_or_else(|| detect_arch().to_string());
    output::info(&format!("Target architecture: {arch}"));

    for service in ["crush-proxy", "opencode-proxy", "gemini-proxy"] {
        output::step(&format!("Building {service}..."));
        process::run_with_env(
            "docker",
            &["compose", "--profile", PROFILE, "build", service],
            &[("TARGETARCH", &arch)],
        )?;
    }
    output::success("All proxy containers built");
    Ok(())
}

fn detect_arch() -> &'static str {
    match std::env::consts::ARCH {
        "aarch64" => "arm64",
        _ => "amd64",
    }
}

/// Pass/fail tally for the test suite.
#[derive(Default)]
struct Tally {
    passed: u32,
    failed: u32,
}

impl Tally {
    fn record(&mut self, name: &str, ok: bool) {
        if ok {
            eprintln!("  {name}... {}", "PASSED".green());
            self.passed += 1;
        } else {
            eprintln!("  {name}... {}", "FAILED".red());
            self.failed += 1;
        }
    }
}

fn run_tests(mode: TestMode) -> Result<()> {
    output::header("Corporate Proxy Test Suite");
    output::info(&format!("Test mode: {mode:?}"));

    let modes: Vec<TestMode> = if mode == TestMode::All {
        vec![
            TestMode::Quick,
            TestMode::Crush,
            TestMode::Opencode,
            TestMode::Gemini,
            TestMode::Api,
            TestMode::Integration,
        ]
    } else {
        vec![mode]
    };

    let mut tally = Tally::default();
    for m in modes {
        run_mode(m, &mut tally);
    }

    println!();
    output::header("Test Results Summary");
    println!("Tests Run:    {}", tally.passed + tally.failed);
    println!("Tests Passed: {}", tally.passed.green());
    println!("Tests Failed: {}", tally.failed.red());
    println!();

    if tally.failed == 0 {
        output::success("All tests passed!");
        Ok(())
    } else {
        output::fail("Some tests failed");
        bail!("{} test(s) failed", tally.failed);
    }
}

fn run_mode(mode: TestMode, tally: &mut Tally) {
    match mode {
        TestMode::Quick => {
            output::step("Quick smoke tests");
            with_local_api(8080, tally, |_, _| {});
        },
        TestMode::Api => {
            output::step("API endpoint tests");
            with_local_api(8090, tally, |base, tally| {
                let Ok(client) = http::client(Duration::from_secs(10)) else {
                    tally.record("HTTP client", false);
                    return;
                };
                tally.record(
                    "GET /tools",
                    http::get_ok(&client, &format!("{base}/tools")),
                );
                let execute = client
                    .post(format!("{base}/execute"))
                    .json(&serde_json::json!({
                        "tool": "view",
                        "parameters": {"filePath": "test.py"}
                    }))
                    .send()
                    .is_ok_and(|r| r.status().is_success());
                tally.record("POST /execute", execute);
            });
        },
        TestMode::Crush | TestMode::Opencode | TestMode::Gemini => {
            let service = match mode {
                TestMode::Crush => "crush-proxy",
                TestMode::Opencode => "opencode-proxy",
                _ => "gemini-proxy",
            };
            output::step(&format!("{service} image build"));
            let ok = process::run(
                "docker",
                &["compose", "--profile", PROFILE, "build", service],
            )
            .is_ok();
            tally.record(&format!("{service} docker build"), ok);
        },
        TestMode::Integration => integration(tally),
        TestMode::All => unreachable!("expanded by run_tests"),
    }
}

/// Kills the wrapped child process when dropped.
struct ChildGuard(Child);

impl Drop for ChildGuard {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

/// Start the unified tool API on `port`, record its startup/health, run
/// `checks` against its base URL, then stop it.
fn with_local_api(port: u16, tally: &mut Tally, checks: impl FnOnce(&str, &mut Tally)) {
    let python = ["python3", "python"]
        .into_iter()
        .find(|p| process::command_exists(p));
    let Some(python) = python else {
        output::warn("python3 not found on PATH");
        tally.record("Unified API startup", false);
        return;
    };
    let spawned = Command::new(python)
        .arg(UNIFIED_API)
        .env("API_MODE", "crush")
        .env("PORT", port.to_string())
        .env("HOST", "127.0.0.1")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .with_context(|| format!("failed to start {UNIFIED_API}"));
    let _guard = match spawned {
        Ok(child) => ChildGuard(child),
        Err(e) => {
            output::warn(&format!("{e:#}"));
            tally.record("Unified API startup", false);
            return;
        },
    };
    tally.record("Unified API startup", true);

    let base = format!("http://127.0.0.1:{port}");
    let healthy = http::client(Duration::from_secs(2)).is_ok_and(|c| {
        http::poll_until(
            Duration::from_secs(15),
            Duration::from_millis(500),
            || http::get_ok(&c, &format!("{base}/health")),
            || {},
        )
    });
    tally.record("API health check", healthy);
    if healthy {
        checks(&base, tally);
    }
}

/// Bring up the proxy containers, check their health endpoints, and stop
/// only those containers afterwards (never the whole compose project).
fn integration(tally: &mut Tally) {
    output::step("Integration tests");
    let services = [("crush-proxy", 8051u16), ("opencode-proxy", 8052u16)];
    let names: Vec<&str> = services.iter().map(|(s, _)| *s).collect();

    let mut up = vec!["compose", "--profile", PROFILE, "up", "-d"];
    up.extend_from_slice(&names);
    let started = process::run("docker", &up).is_ok();
    tally.record("Docker Compose services start", started);

    if started && let Ok(client) = http::client(Duration::from_secs(2)) {
        for (service, port) in services {
            let url = format!("http://localhost:{port}/health");
            let ok = http::poll_until(
                Duration::from_secs(30),
                Duration::from_secs(1),
                || http::get_ok(&client, &url),
                || {},
            );
            tally.record(&format!("{service} /health"), ok);
        }
    }

    let mut stop = vec!["compose", "--profile", PROFILE, "stop"];
    stop.extend_from_slice(&names);
    if let Err(e) = process::run("docker", &stop) {
        output::warn(&format!("failed to stop proxy containers: {e}"));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;

    #[derive(Parser)]
    struct Probe {
        #[command(subcommand)]
        action: ProxyAction,
    }

    #[test]
    fn test_mode_defaults_to_quick() {
        let p = Probe::try_parse_from(["x", "test"]).unwrap();
        assert!(matches!(
            p.action,
            ProxyAction::Test {
                mode: TestMode::Quick
            }
        ));
    }

    #[test]
    fn all_mode_names_parse() {
        for m in [
            "quick",
            "crush",
            "opencode",
            "gemini",
            "api",
            "integration",
            "all",
        ] {
            assert!(Probe::try_parse_from(["x", "test", m]).is_ok(), "{m}");
        }
        assert!(Probe::try_parse_from(["x", "test", "bogus"]).is_err());
    }

    #[test]
    fn tally_counts() {
        let mut t = Tally::default();
        t.record("a", true);
        t.record("b", false);
        assert_eq!((t.passed, t.failed), (1, 1));
    }

    #[test]
    fn arch_is_docker_style() {
        assert!(matches!(detect_arch(), "amd64" | "arm64"));
    }
}
