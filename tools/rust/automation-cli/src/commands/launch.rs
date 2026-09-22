//! `automation-cli launch <service>` -- build + start a GPU web service (or
//! the Gemini MCP server) and wait for it to answer.

use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use clap::{Args, ValueEnum};

use crate::shared::{docker, http, output, process, project};

#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
pub enum LaunchService {
    /// AI Toolkit (LoRA training) web UI container
    AiToolkit,
    /// ComfyUI web UI container
    Comfyui,
    /// Gemini MCP server binary (disabled by project policy; testing only)
    GeminiMcp,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
pub enum LaunchMode {
    /// Service default (docker services; stdio usage info for gemini-mcp)
    Default,
    /// gemini-mcp only: print stdio usage info
    Stdio,
    /// gemini-mcp only: start a standalone HTTP server in the background
    Http,
}

#[derive(Args)]
pub struct LaunchArgs {
    /// Service to launch
    #[arg(value_enum)]
    pub service: LaunchService,

    /// Launch mode (gemini-mcp: stdio or http)
    #[arg(long, value_enum, default_value = "default")]
    pub mode: LaunchMode,

    /// gemini-mcp http mode port (default: $GEMINI_MCP_PORT or 8006)
    #[arg(long)]
    pub port: Option<u16>,

    /// Skip opening browser
    #[arg(long)]
    pub no_browser: bool,

    /// Health check timeout in seconds
    #[arg(long, default_value = "60")]
    pub timeout: u64,
}

/// A compose-managed web service.
struct DockerService {
    name: &'static str,
    profile: &'static str,
    port: u16,
    /// Path polled for readiness (2xx/3xx).
    health_path: &'static str,
}

const AI_TOOLKIT: DockerService = DockerService {
    name: "mcp-ai-toolkit",
    profile: "ai-services",
    port: 8675,
    health_path: "/",
};

const COMFYUI: DockerService = DockerService {
    name: "mcp-comfyui",
    profile: "ai-services",
    port: 8188,
    health_path: "/system_stats",
};

pub fn run(args: LaunchArgs) -> Result<()> {
    let root = project::enter_project_root()?;
    if args.port.is_some() && args.service != LaunchService::GeminiMcp {
        output::warn("--port only applies to gemini-mcp; docker services use docker-compose.yml");
    }
    match args.service {
        LaunchService::AiToolkit => launch_docker_service(&AI_TOOLKIT, &args),
        LaunchService::Comfyui => launch_docker_service(&COMFYUI, &args),
        LaunchService::GeminiMcp => launch_gemini_mcp(&root, &args),
    }
}

/// Env for compose: ARM64 hosts need the ARM ComfyUI Dockerfile.
fn compose_env() -> Vec<(&'static str, &'static str)> {
    if std::env::consts::ARCH == "aarch64" {
        output::info("Detected ARM64 -- using comfyui-arm64.Dockerfile");
        vec![("COMFYUI_DOCKERFILE", "docker/comfyui-arm64.Dockerfile")]
    } else {
        Vec::new()
    }
}

fn launch_docker_service(svc: &DockerService, args: &LaunchArgs) -> Result<()> {
    output::header(&format!("{} Launcher", svc.name));

    if !process::command_exists("docker") {
        bail!("Docker not found. Install: https://docs.docker.com/engine/install/");
    }
    let env = compose_env();

    output::step(&format!("Building {} container...", svc.name));
    process::run_with_env(
        "docker",
        &["compose", "--profile", svc.profile, "build", svc.name],
        &env,
    )?;

    output::step(&format!("Starting {} container...", svc.name));
    process::run_with_env(
        "docker",
        &["compose", "--profile", svc.profile, "up", "-d", svc.name],
        &env,
    )?;

    if !docker::is_service_running(svc.name) {
        output::fail(&format!("Failed to start {} container", svc.name));
        let _ = process::run("docker", &["compose", "logs", "--tail", "50", svc.name]);
        bail!("{} failed to start", svc.name);
    }

    output::step(&format!("Waiting for {} to initialize...", svc.name));
    let web_url = format!("http://localhost:{}", svc.port);
    let health_url = format!("{web_url}{}", svc.health_path);
    let client = http::client(Duration::from_secs(2))?;
    let ready = http::poll_until(
        Duration::from_secs(args.timeout),
        Duration::from_secs(2),
        || http::get_ok_or_redirect(&client, &health_url),
        || eprint!("."),
    );
    eprintln!();

    if ready {
        output::success(&format!("{} is ready!", svc.name));
    } else {
        output::warn(&format!(
            "{} may still be starting up (timed out after {}s)",
            svc.name, args.timeout
        ));
    }

    if !args.no_browser {
        output::step("Opening web UI in browser...");
        open_url(&web_url);
    }

    println!();
    output::info(&format!("Web UI: {web_url}"));
    println!();
    output::info("Commands:");
    output::info(&format!(
        "  View logs:  docker compose logs -f {}",
        svc.name
    ));
    output::info(&format!(
        "  Stop:       docker compose --profile {} stop {}",
        svc.profile, svc.name
    ));
    output::info(&format!(
        "  Restart:    docker compose --profile {} restart {}",
        svc.profile, svc.name
    ));
    Ok(())
}

fn launch_gemini_mcp(root: &Path, args: &LaunchArgs) -> Result<()> {
    output::header("Gemini MCP Server Launcher");
    output::warn(
        "Gemini integration is disabled by project policy (see AGENTS.md); \
         use this only for local testing.",
    );

    let crate_dir = root.join("tools/mcp/mcp_gemini");
    let binary = crate_dir.join("target/release/mcp-gemini");
    if !binary.is_file() {
        output::step("Binary not found, building mcp-gemini...");
        process::run_in(&crate_dir, "cargo", &["build", "--release"])?;
    }
    let binary_str = binary.to_string_lossy().into_owned();

    if args.mode != LaunchMode::Http {
        println!("Gemini MCP Server (Rust)");
        println!("========================");
        println!();
        println!("The stdio server needs to be connected to an MCP client.");
        println!();
        println!("Option 1: Direct execution (for testing)");
        println!("  {binary_str} --mode stdio");
        println!();
        println!("Option 2: Configure with an MCP client (recommended)");
        println!();
        println!("To test with HTTP mode:");
        println!("  automation-cli launch gemini-mcp --mode http");
        return Ok(());
    }

    let port = match args.port {
        Some(p) => p,
        None => match std::env::var("GEMINI_MCP_PORT") {
            Ok(v) => v
                .parse()
                .with_context(|| format!("invalid GEMINI_MCP_PORT `{v}`"))?,
            Err(_) => 8006,
        },
    };
    output::step(&format!(
        "Starting Gemini MCP server in HTTP mode on port {port}..."
    ));
    output::warn("HTTP mode is for testing only. Use stdio mode for production.");

    let tmp = std::env::temp_dir();
    let log_path = tmp.join("gemini-mcp.log");
    let pid_path = tmp.join("gemini-mcp.pid");
    let log = std::fs::File::create(&log_path)
        .with_context(|| format!("cannot create {}", log_path.display()))?;
    let mut child = std::process::Command::new(&binary)
        .args(["--mode", "standalone", "--port", &port.to_string()])
        .stdin(std::process::Stdio::null())
        .stdout(log.try_clone()?)
        .stderr(log)
        .spawn()
        .with_context(|| format!("failed to start {binary_str}"))?;

    let pid = child.id();
    std::fs::write(&pid_path, pid.to_string())?;
    output::info(&format!("Server started with PID {pid}"));
    output::info(&format!("Logs: {}", log_path.display()));

    output::step("Waiting for server to become healthy...");
    let client = http::client(Duration::from_secs(2))?;
    let url = format!("http://localhost:{port}/health");
    let healthy = http::poll_until(
        Duration::from_secs(args.timeout.min(60)),
        Duration::from_secs(1),
        || http::get_ok(&client, &url),
        || {},
    );
    if healthy {
        output::success("Server is healthy");
        return Ok(());
    }
    // Do not leave a half-started server running in the background.
    let _ = child.kill();
    let _ = child.wait();
    let _ = std::fs::remove_file(&pid_path);
    bail!("server did not become healthy; see {}", log_path.display())
}

fn open_url(url: &str) {
    let (cmd, args): (&str, Vec<&str>) = if cfg!(target_os = "macos") {
        ("open", vec![url])
    } else if cfg!(target_os = "windows") {
        ("cmd", vec!["/c", "start", "", url])
    } else {
        ("xdg-open", vec![url])
    };
    if !process::command_exists(cmd) {
        output::info(&format!("Open {url} in your browser"));
        return;
    }
    let spawned = std::process::Command::new(cmd)
        .args(&args)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();
    if spawned.is_err() {
        output::info(&format!("Open {url} in your browser"));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;

    #[derive(Parser)]
    struct Probe {
        #[command(flatten)]
        args: LaunchArgs,
    }

    #[test]
    fn service_names_are_stable() {
        for (name, svc) in [
            ("ai-toolkit", LaunchService::AiToolkit),
            ("comfyui", LaunchService::Comfyui),
            ("gemini-mcp", LaunchService::GeminiMcp),
        ] {
            let p = Probe::try_parse_from(["x", name]).unwrap();
            assert_eq!(p.args.service, svc);
            assert_eq!(p.args.mode, LaunchMode::Default);
            assert_eq!(p.args.timeout, 60);
        }
        assert!(Probe::try_parse_from(["x", "nope"]).is_err());
    }

    #[test]
    fn mode_and_port_flags() {
        let p =
            Probe::try_parse_from(["x", "gemini-mcp", "--mode", "http", "--port", "9000"]).unwrap();
        assert_eq!(p.args.mode, LaunchMode::Http);
        assert_eq!(p.args.port, Some(9000));
    }
}
