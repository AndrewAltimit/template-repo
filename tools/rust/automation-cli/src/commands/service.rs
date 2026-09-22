//! `automation-cli service <action>` -- manage the GPU AI services
//! (AI Toolkit + ComfyUI) on the remote AI machine.

use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use clap::{Subcommand, ValueEnum};

use crate::shared::{docker, http, output, process, project};

/// Compose services managed by this command.
const SERVICES: [&str; 2] = ["mcp-ai-toolkit", "mcp-comfyui"];
/// Compose profile the services belong to.
const PROFILE: &str = "ai-services";

#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
pub enum RunMode {
    /// Build and run the containers with docker compose
    Docker,
    /// Build and run the Rust MCP servers directly on the host
    Host,
}

#[derive(Subcommand)]
pub enum ServiceAction {
    /// Start AI services (AI Toolkit + ComfyUI)
    Start {
        /// Run mode
        #[arg(long, value_enum, default_value = "docker")]
        mode: RunMode,
        /// Docker compose profile to use
        #[arg(long, default_value = PROFILE)]
        profile: String,
        /// Seconds to wait for the containers to report healthy
        #[arg(long, default_value = "60")]
        timeout: u64,
    },
    /// Stop AI services (only these services; other containers are untouched)
    Stop,
    /// Restart AI services
    Restart,
    /// Follow service logs
    Logs,
    /// Show service status
    Status,
    /// Build service containers
    Build,
    /// Fast-forward the current branch from its upstream
    Pull,
    /// Pull code, rebuild, and restart services
    Update,
}

pub fn run(action: ServiceAction) -> Result<()> {
    let root = project::enter_project_root()?;

    match action {
        ServiceAction::Start {
            mode,
            profile,
            timeout,
        } => {
            output::header("AI Services MCP Server Launcher");
            match mode {
                RunMode::Docker => start_docker(&profile, Duration::from_secs(timeout)),
                RunMode::Host => start_host(&root),
            }
        },
        ServiceAction::Stop => {
            output::step("Stopping AI MCP services...");
            compose(&["stop"], &SERVICES)?;
            compose(&["rm", "-f"], &SERVICES)
        },
        ServiceAction::Restart => {
            output::step("Restarting AI MCP services...");
            compose(&["restart"], &SERVICES)
        },
        ServiceAction::Logs => compose(&["logs", "-f"], &SERVICES),
        ServiceAction::Status => compose(&["ps"], &SERVICES),
        ServiceAction::Build => {
            output::step("Building AI MCP service containers...");
            compose(&["build"], &SERVICES)
        },
        ServiceAction::Pull => git_pull(),
        ServiceAction::Update => {
            output::step("Updating and restarting services...");
            git_pull()?;
            compose(&["build"], &SERVICES)?;
            compose(&["up", "-d"], &SERVICES)
        },
    }
}

/// `docker compose --profile ai-services <args...> <services...>`
fn compose(args: &[&str], services: &[&str]) -> Result<()> {
    compose_with_profile(PROFILE, args, services)
}

fn compose_with_profile(profile: &str, args: &[&str], services: &[&str]) -> Result<()> {
    let mut full = vec!["compose", "--profile", profile];
    full.extend_from_slice(args);
    full.extend_from_slice(services);
    process::run_with_env("docker", &full, &compose_env())
}

/// ARM64 hosts need the ARM ComfyUI Dockerfile.
fn compose_env() -> Vec<(&'static str, &'static str)> {
    if std::env::consts::ARCH == "aarch64" {
        vec![("COMFYUI_DOCKERFILE", "docker/comfyui-arm64.Dockerfile")]
    } else {
        Vec::new()
    }
}

fn git_pull() -> Result<()> {
    output::step("Pulling latest code...");
    process::run("git", &["pull", "--ff-only"])
        .context("git pull --ff-only failed (does the branch track an upstream?)")
}

fn start_docker(profile: &str, timeout: Duration) -> Result<()> {
    if !process::command_exists("docker") {
        bail!("Docker is not installed");
    }

    if process::command_exists("nvidia-smi") {
        output::success("NVIDIA GPU detected");
        let _ = process::run(
            "nvidia-smi",
            &["--query-gpu=name,memory.total", "--format=csv,noheader"],
        );
    } else {
        output::warn("No NVIDIA GPU detected");
    }

    match process::run_output("docker", &["info", "--format", "{{json .Runtimes}}"]) {
        Ok(o) if String::from_utf8_lossy(&o.stdout).contains("nvidia") => {
            output::success("NVIDIA Docker runtime detected");
        },
        Ok(_) => output::warn("NVIDIA Docker runtime not detected"),
        Err(e) => output::warn(&format!("Could not query docker info: {e}")),
    }
    if std::env::consts::ARCH == "aarch64" {
        output::info("Detected ARM64 -- using comfyui-arm64.Dockerfile");
    }

    output::step("Building containers...");
    compose_with_profile(profile, &["build"], &SERVICES)?;

    output::step(&format!("Starting services with profile: {profile}"));
    compose_with_profile(profile, &["up", "-d"], &SERVICES)?;

    output::step("Waiting for services to become healthy...");
    let healthy = http::poll_until(
        timeout,
        Duration::from_secs(2),
        || {
            SERVICES
                .iter()
                .all(|s| docker::service_health(s).is_some_and(|h| is_ready_status(&h)))
        },
        || eprint!("."),
    );
    eprintln!();

    if healthy {
        output::success("AI services started successfully!");
    } else {
        for s in SERVICES {
            let status = docker::service_health(s).unwrap_or_else(|| "no container".into());
            output::warn(&format!("{s}: {status}"));
        }
        output::warn(&format!(
            "Services not healthy after {}s; they may still be initializing \
             (check `automation-cli service logs`)",
            timeout.as_secs()
        ));
    }
    println!();
    output::info("AI Toolkit web UI: http://localhost:8675");
    output::info("ComfyUI web UI:    http://localhost:8188");
    output::info("MCP ports are listed below (docker compose ps)");
    println!();

    compose_with_profile(profile, &["ps"], &SERVICES)
}

/// Container health/state strings that count as "up".
fn is_ready_status(status: &str) -> bool {
    // `running` is reported for containers without a healthcheck.
    matches!(status, "healthy" | "running")
}

/// A host-mode MCP server: Rust crate dir, binary name, standalone port.
struct HostServer {
    label: &'static str,
    crate_dir: &'static str,
    binary: &'static str,
    port: u16,
}

const HOST_SERVERS: [HostServer; 2] = [
    HostServer {
        label: "AI Toolkit MCP",
        crate_dir: "tools/mcp/mcp_ai_toolkit",
        binary: "mcp-ai-toolkit",
        port: 8020,
    },
    HostServer {
        label: "ComfyUI MCP",
        crate_dir: "tools/mcp/mcp_comfyui",
        binary: "mcp-comfyui",
        port: 8013,
    },
];

/// Build (if needed) and start the Rust MCP servers on the host in
/// standalone HTTP mode, logging to the temp directory.
fn start_host(root: &Path) -> Result<()> {
    output::step("Starting AI MCP servers on host...");
    if !process::command_exists("cargo") {
        bail!("cargo is required for host mode (install Rust from https://rustup.rs)");
    }
    let tmp = std::env::temp_dir();

    for server in &HOST_SERVERS {
        let dir = root.join(server.crate_dir);
        let binary = dir.join("target/release").join(server.binary);
        if !binary.is_file() {
            output::step(&format!("Building {}...", server.binary));
            process::run_in(&dir, "cargo", &["build", "--release"])?;
        }

        let log_path = tmp.join(format!("{}.log", server.binary));
        let log = std::fs::File::create(&log_path)
            .with_context(|| format!("cannot create {}", log_path.display()))?;
        output::step(&format!("Starting {}...", server.label));
        let child = std::process::Command::new(&binary)
            .args(["--mode", "standalone", "--port", &server.port.to_string()])
            .stdin(std::process::Stdio::null())
            .stdout(log.try_clone()?)
            .stderr(log)
            .spawn()
            .with_context(|| format!("failed to start {}", binary.display()))?;
        std::fs::write(
            tmp.join(format!("{}.pid", server.binary)),
            child.id().to_string(),
        )?;
        output::info(&format!(
            "{}: http://0.0.0.0:{} (PID {}, log {})",
            server.label,
            server.port,
            child.id(),
            log_path.display()
        ));
    }

    output::success("AI MCP servers started");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ready_statuses() {
        assert!(is_ready_status("healthy"));
        assert!(is_ready_status("running"));
        // "unhealthy" contains "healthy" -- the old substring check got this wrong.
        assert!(!is_ready_status("unhealthy"));
        assert!(!is_ready_status("starting"));
        assert!(!is_ready_status("exited"));
    }
}
