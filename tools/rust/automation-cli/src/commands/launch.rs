use std::time::{Duration, Instant};

use anyhow::{Result, bail};
use clap::Args;

use crate::shared::{output, process, project};

#[derive(Args)]
pub struct LaunchArgs {
    /// Service to launch (ai-toolkit, comfyui, gemini-mcp)
    pub service: String,

    /// Launch mode (for gemini-mcp: stdio or http)
    #[arg(long, default_value = "default")]
    pub mode: String,

    /// Skip opening browser
    #[arg(long)]
    pub no_browser: bool,

    /// Health check timeout in seconds
    #[arg(long, default_value = "60")]
    pub timeout: u64,
}

pub fn run(args: LaunchArgs) -> Result<()> {
    let root = project::find_project_root()?;
    std::env::set_current_dir(&root)?;

    match args.service.as_str() {
        "ai-toolkit" => launch_docker_service(
            "mcp-ai-toolkit",
            "ai-services",
            "http://localhost:8675",
            8675,
            &args,
        ),
        "comfyui" => launch_docker_service(
            "mcp-comfyui",
            "ai-services",
            "http://localhost:8188",
            8188,
            &args,
        ),
        "gemini-mcp" => launch_gemini_mcp(&args),
        other => bail!("unknown service: {other}\nAvailable: ai-toolkit, comfyui, gemini-mcp"),
    }
}

fn launch_docker_service(
    service: &str,
    profile: &str,
    web_url: &str,
    port: u16,
    args: &LaunchArgs,
) -> Result<()> {
    output::header(&format!("{service} Launcher"));

    // Check Docker
    if !process::command_exists("docker") {
        bail!("Docker not found. Install: https://docs.docker.com/engine/install/");
    }

    // Set ARM64 ComfyUI Dockerfile if needed
    if service == "mcp-comfyui" && std::env::consts::ARCH == "aarch64" {
        // SAFETY: single-threaded at this point
        unsafe { std::env::set_var("COMFYUI_DOCKERFILE", "docker/comfyui-arm64.Dockerfile") };
        output::info("Detected ARM64 -- using comfyui-arm64.Dockerfile");
    }

    // Build
    output::step(&format!("Building {service} container..."));
    process::run("docker", &["compose", "build", service])?;

    // Start
    output::step(&format!("Starting {service} container..."));
    process::run(
        "docker",
        &["compose", "--profile", profile, "up", "-d", service],
    )?;

    // Verify it started
    if !crate::shared::docker::is_service_running(service) {
        output::fail(&format!("Failed to start {service} container"));
        process::run("docker", &["compose", "logs", service])?;
        bail!("{service} failed to start");
    }

    // Health check with polling
    output::step(&format!("Waiting for {service} to initialize..."));
    let timeout = Duration::from_secs(args.timeout);
    let start = Instant::now();
    let mut ready = false;

    while start.elapsed() < timeout {
        if reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(2))
            .build()
            .ok()
            .and_then(|c| c.get(format!("http://localhost:{port}/")).send().ok())
            .is_some_and(|r| r.status().is_success() || r.status().is_redirection())
        {
            ready = true;
            break;
        }
        eprint!(".");
        std::thread::sleep(Duration::from_secs(2));
    }
    eprintln!();

    if ready {
        output::success(&format!("{service} is ready!"));
    } else {
        output::warn(&format!(
            "{service} may still be starting up (timed out after {}s)",
            args.timeout
        ));
    }

    // Open browser
    if !args.no_browser {
        output::step("Opening web UI in browser...");
        open_url(web_url);
    }

    // Print info
    println!();
    output::info(&format!("Web UI: {web_url}"));
    println!();
    output::info("Commands:");
    output::info(&format!("  View logs:  docker compose logs -f {service}"));
    output::info(&format!(
        "  Stop:       docker compose --profile {profile} stop {service}"
    ));
    output::info(&format!(
        "  Restart:    docker compose --profile {profile} restart {service}"
    ));

    Ok(())
}

fn launch_gemini_mcp(args: &LaunchArgs) -> Result<()> {
    output::header("Gemini MCP Server Launcher");

    let root = project::find_project_root()?;
    let binary = root.join("tools/mcp/mcp_gemini/target/release/mcp-gemini");

    // Build if needed
    if !binary.exists() {
        output::step("Binary not found, building mcp-gemini...");
        process::run_in(
            &root.join("tools/mcp/mcp_gemini"),
            "cargo",
            &["build", "--release"],
        )?;
    }

    let binary_str = binary.to_string_lossy().to_string();

    if args.mode == "http" {
        let port = std::env::var("GEMINI_MCP_PORT").unwrap_or_else(|_| "8006".to_string());

        output::step(&format!(
            "Starting Gemini MCP server in HTTP mode on port {port}..."
        ));
        output::warn("HTTP mode is for testing only. Use stdio mode for production.");

        // Start as background process
        let child = std::process::Command::new(&binary_str)
            .args(["--mode", "standalone", "--port", &port])
            .stdout(std::fs::File::create("/tmp/gemini-mcp.log")?)
            .stderr(std::fs::File::create("/tmp/gemini-mcp.log")?)
            .spawn()?;

        let pid = child.id();
        std::fs::write("/tmp/gemini-mcp.pid", pid.to_string())?;
        output::info(&format!("Server started with PID {pid}"));
        output::info("Logs: /tmp/gemini-mcp.log");

        // Health check
        output::step("Waiting for server to become healthy...");
        for _ in 0..10 {
            if reqwest::blocking::Client::builder()
                .timeout(Duration::from_secs(2))
                .build()
                .ok()
                .and_then(|c| c.get(format!("http://localhost:{port}/health")).send().ok())
                .is_some_and(|r| r.status().is_success())
            {
                output::success("Server is healthy");
                return Ok(());
            }
            std::thread::sleep(Duration::from_secs(1));
        }
        bail!("Server did not become healthy after 10 seconds");
    }

    // stdio mode: print usage info
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
    Ok(())
}

fn open_url(url: &str) {
    #[cfg(target_os = "linux")]
    {
        if process::command_exists("xdg-open") {
            let _ = std::process::Command::new("xdg-open")
                .arg(url)
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .spawn();
        }
    }
    #[cfg(target_os = "macos")]
    {
        let _ = std::process::Command::new("open").arg(url).spawn();
    }
    #[cfg(target_os = "windows")]
    {
        let _ = std::process::Command::new("cmd")
            .args(["/c", "start", url])
            .spawn();
    }
}
