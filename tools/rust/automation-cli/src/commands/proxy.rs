use std::time::Duration;

use anyhow::{Result, bail};
use clap::Subcommand;
use owo_colors::OwoColorize;

use crate::shared::{output, process, project};

#[derive(Subcommand)]
pub enum ProxyAction {
    /// Build corporate proxy containers
    Build {
        /// Target architecture (auto-detected if not specified)
        #[arg(long)]
        arch: Option<String>,
    },
    /// Run corporate proxy test suite
    Test {
        /// Test mode (quick, crush, opencode, gemini, api, integration, all)
        #[arg(default_value = "quick")]
        mode: String,
    },
}

pub fn run(action: ProxyAction) -> Result<()> {
    let root = project::find_project_root()?;
    std::env::set_current_dir(&root)?;

    match action {
        ProxyAction::Build { arch } => build(arch),
        ProxyAction::Test { mode } => run_tests(&mode),
    }
}

fn build(arch: Option<String>) -> Result<()> {
    output::header("Building corporate proxy containers");

    let arch = arch.unwrap_or_else(detect_arch);
    output::info(&format!("Target architecture: {arch}"));

    // SAFETY: single-threaded at this point
    unsafe { std::env::set_var("TARGETARCH", &arch) };

    for service in &["crush-proxy", "opencode-proxy", "gemini-proxy"] {
        output::step(&format!("Building {service}..."));
        process::run("docker", &["compose", "build", service])?;
    }

    output::success("All proxy containers built");
    Ok(())
}

fn detect_arch() -> String {
    #[cfg(target_arch = "x86_64")]
    {
        "amd64".to_string()
    }
    #[cfg(target_arch = "aarch64")]
    {
        "arm64".to_string()
    }
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    {
        "amd64".to_string()
    }
}

fn run_tests(mode: &str) -> Result<()> {
    output::header("Corporate Proxy Test Suite");
    output::info(&format!("Test Type: {mode}"));

    let mut tests_run: u32 = 0;
    let mut tests_passed: u32 = 0;
    let mut tests_failed: u32 = 0;

    match mode {
        "quick" | "--quick" => {
            run_test_set(
                "Quick smoke tests",
                &[
                    (
                        "Unified API startup",
                        "python automation/corporate-proxy/shared/services/unified_tool_api.py &",
                    ),
                    ("API health check", "curl -fsS http://localhost:8080/health"),
                ],
                &mut tests_run,
                &mut tests_passed,
                &mut tests_failed,
            )?;
        },
        "crush" | "--crush" => {
            run_test_set(
                "Crush tests",
                &[("Crush Docker build", "docker compose build crush-proxy")],
                &mut tests_run,
                &mut tests_passed,
                &mut tests_failed,
            )?;
        },
        "opencode" | "--opencode" => {
            run_test_set(
                "OpenCode tests",
                &[(
                    "OpenCode Docker build",
                    "docker compose build opencode-proxy",
                )],
                &mut tests_run,
                &mut tests_passed,
                &mut tests_failed,
            )?;
        },
        "gemini" | "--gemini" => {
            run_test_set(
                "Gemini tests",
                &[("Gemini Docker build", "docker compose build gemini-proxy")],
                &mut tests_run,
                &mut tests_passed,
                &mut tests_failed,
            )?;
        },
        "api" | "--api" => {
            output::step("Running API endpoint tests...");
            // Start test server
            let _ = std::process::Command::new("bash")
                .args(["-c", "API_MODE=crush PORT=8090 python automation/corporate-proxy/shared/services/unified_tool_api.py &"])
                .spawn();

            // Wait for server
            std::thread::sleep(Duration::from_secs(3));

            run_test_set(
                "API endpoint tests",
                &[
                    ("GET /tools", "curl -fsS http://localhost:8090/tools"),
                    (
                        "POST /execute",
                        "curl -fsS -X POST http://localhost:8090/execute -H 'Content-Type: application/json' -d '{\"tool\":\"view\",\"parameters\":{\"filePath\":\"test.py\"}}'",
                    ),
                ],
                &mut tests_run,
                &mut tests_passed,
                &mut tests_failed,
            )?;

            // Cleanup
            let _ = std::process::Command::new("pkill")
                .args(["-f", "unified_tool_api"])
                .status();
        },
        "integration" | "--integration" => {
            run_test_set(
                "Integration tests",
                &[(
                    "Docker Compose services",
                    "docker compose up -d crush-proxy opencode-proxy && sleep 5 && docker compose ps | grep -E 'crush-proxy|opencode-proxy'",
                )],
                &mut tests_run,
                &mut tests_passed,
                &mut tests_failed,
            )?;
            let _ = process::run("docker", &["compose", "down"]);
        },
        "all" | "--all" => {
            // Run all test modes sequentially
            for sub_mode in &["quick", "crush", "opencode", "gemini", "api", "integration"] {
                run_tests(sub_mode)?;
            }
            return Ok(());
        },
        _ => bail!(
            "invalid test mode: {mode}\nAvailable: quick, crush, opencode, gemini, api, integration, all"
        ),
    }

    // Summary
    println!();
    output::header("Test Results Summary");
    println!("Tests Run:    {tests_run}");
    println!("Tests Passed: {}", tests_passed.green());
    println!("Tests Failed: {}", tests_failed.red());
    println!();

    if tests_failed == 0 {
        output::success("All tests passed!");
        Ok(())
    } else {
        output::fail("Some tests failed");
        bail!("{tests_failed} test(s) failed");
    }
}

fn run_test_set(
    name: &str,
    tests: &[(&str, &str)],
    total: &mut u32,
    passed: &mut u32,
    failed: &mut u32,
) -> Result<()> {
    output::step(&format!("Running {name}..."));
    println!();

    for (test_name, command) in tests {
        *total += 1;
        eprint!("Running {test_name}... ");

        let status = std::process::Command::new("bash")
            .args(["-c", command])
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status();

        if status.is_ok_and(|s| s.success()) {
            eprintln!("{}", "PASSED".green());
            *passed += 1;
        } else {
            eprintln!("{}", "FAILED".red());
            *failed += 1;
        }
    }
    Ok(())
}
