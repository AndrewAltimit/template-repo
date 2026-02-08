use anyhow::{Result, bail};
use clap::Subcommand;

use crate::shared::{output, process, project};

#[derive(Subcommand)]
pub enum ServiceAction {
    /// Start AI services (AI Toolkit + ComfyUI)
    Start {
        /// Run mode: docker (default) or host
        #[arg(long, default_value = "docker")]
        mode: String,
        /// Docker profile to use
        #[arg(long, default_value = "ai-services")]
        profile: String,
    },
    /// Stop AI services
    Stop,
    /// Restart AI services
    Restart,
    /// View service logs
    Logs,
    /// Check service status
    Status,
    /// Build service containers
    Build,
    /// Pull latest code from git
    Pull,
    /// Pull code, rebuild, and restart services
    Update,
}

pub fn run(action: ServiceAction) -> Result<()> {
    let root = project::find_project_root()?;
    std::env::set_current_dir(&root)?;

    match action {
        ServiceAction::Start { mode, profile } => start_services(&mode, &profile),
        ServiceAction::Stop => {
            output::step("Stopping AI MCP services...");
            process::run("docker", &["compose", "--profile", "ai-services", "down"])
        },
        ServiceAction::Restart => {
            output::step("Restarting AI MCP services...");
            process::run(
                "docker",
                &[
                    "compose",
                    "--profile",
                    "ai-services",
                    "restart",
                    "mcp-ai-toolkit",
                    "mcp-comfyui",
                ],
            )
        },
        ServiceAction::Logs => process::run(
            "docker",
            &["compose", "logs", "-f", "mcp-ai-toolkit", "mcp-comfyui"],
        ),
        ServiceAction::Status => process::run(
            "docker",
            &["compose", "ps", "mcp-ai-toolkit", "mcp-comfyui"],
        ),
        ServiceAction::Build => {
            output::step("Building AI MCP service containers...");
            process::run(
                "docker",
                &["compose", "build", "mcp-ai-toolkit", "mcp-comfyui"],
            )
        },
        ServiceAction::Pull => {
            output::step("Pulling latest code...");
            process::run("git", &["pull", "origin", "refine"])
        },
        ServiceAction::Update => {
            output::step("Updating and restarting services...");
            process::run("git", &["pull", "origin", "refine"])?;
            process::run(
                "docker",
                &["compose", "build", "mcp-ai-toolkit", "mcp-comfyui"],
            )?;
            process::run(
                "docker",
                &[
                    "compose",
                    "--profile",
                    "ai-services",
                    "up",
                    "-d",
                    "mcp-ai-toolkit",
                    "mcp-comfyui",
                ],
            )
        },
    }
}

fn start_services(mode: &str, profile: &str) -> Result<()> {
    output::header("AI Services MCP Server Launcher");

    match mode {
        "docker" => start_docker(profile),
        "host" => start_host(),
        _ => bail!("invalid mode: {mode}\nUse: docker or host"),
    }
}

fn start_docker(profile: &str) -> Result<()> {
    // Check Docker
    if !process::command_exists("docker") {
        bail!("Docker is not installed");
    }

    // Check GPU
    if process::command_exists("nvidia-smi") {
        output::success("NVIDIA GPU detected");
        let _ = process::run(
            "nvidia-smi",
            &["--query-gpu=name,memory.total", "--format=csv,noheader"],
        );
    } else {
        output::warn("No NVIDIA GPU detected");
    }

    // Check nvidia-docker
    if let Ok(info) = process::run_capture("docker", &["info"]) {
        if info.contains("nvidia") {
            output::success("NVIDIA Docker runtime detected");
        } else {
            output::warn("NVIDIA Docker runtime not detected");
        }
    }

    // Set ARM64 ComfyUI Dockerfile if needed
    if std::env::consts::ARCH == "aarch64" {
        // SAFETY: single-threaded at this point
        unsafe { std::env::set_var("COMFYUI_DOCKERFILE", "docker/comfyui-arm64.Dockerfile") };
        output::info("Detected ARM64 -- using comfyui-arm64.Dockerfile");
    }

    output::step("Building containers...");
    process::run(
        "docker",
        &["compose", "build", "mcp-ai-toolkit", "mcp-comfyui"],
    )?;

    output::step(&format!("Starting services with profile: {profile}"));
    process::run(
        "docker",
        &[
            "compose",
            "--profile",
            profile,
            "up",
            "-d",
            "mcp-ai-toolkit",
            "mcp-comfyui",
        ],
    )?;

    // Health check
    output::step("Waiting for services to become healthy...");
    for _ in 0..30 {
        if let Ok(ps) = process::run_capture("docker", &["compose", "ps"])
            && ps.contains("healthy")
        {
            output::success("Services are healthy");
            break;
        }
        eprint!(".");
        std::thread::sleep(std::time::Duration::from_secs(2));
    }
    eprintln!();

    output::success("AI services started successfully!");
    println!();
    output::info("AI Toolkit:");
    output::info("  Web UI: http://0.0.0.0:8675");
    output::info("  MCP Server: http://0.0.0.0:8012");
    println!();
    output::info("ComfyUI:");
    output::info("  Web UI: http://0.0.0.0:8188");
    output::info("  MCP Server: http://0.0.0.0:8013");
    println!();

    process::run(
        "docker",
        &["compose", "ps", "mcp-ai-toolkit", "mcp-comfyui"],
    )
}

fn start_host() -> Result<()> {
    output::step("Starting AI services on host...");

    if !process::command_exists("python3") {
        bail!("Python 3 is not installed");
    }

    let root = project::find_project_root()?;

    // Create venv if needed
    let venv_path = root.join("venv");
    if !venv_path.exists() {
        output::step("Creating virtual environment...");
        process::run("python3", &["-m", "venv", &venv_path.to_string_lossy()])?;
    }

    // Install dependencies
    output::step("Installing dependencies...");
    let pip = venv_path.join("bin/pip");
    let pip_str = pip.to_string_lossy().to_string();
    process::run(
        &pip_str,
        &[
            "install",
            "-q",
            "-r",
            "docker/requirements/requirements-ai-toolkit.txt",
        ],
    )?;
    process::run(
        &pip_str,
        &[
            "install",
            "-q",
            "-r",
            "docker/requirements/requirements-comfyui.txt",
        ],
    )?;

    let python = venv_path.join("bin/python3");
    let python_str = python.to_string_lossy().to_string();

    // Start services
    output::step("Starting AI Toolkit MCP Server...");
    let ai_child = std::process::Command::new(&python_str)
        .args([
            "-m",
            "mcp_ai_toolkit.server",
            "--mode",
            "http",
            "--host",
            "0.0.0.0",
        ])
        .env("PYTHONPATH", format!("{}/tools/mcp", root.display()))
        .stdout(std::fs::File::create("/tmp/ai-toolkit-mcp.log")?)
        .stderr(std::fs::File::create("/tmp/ai-toolkit-mcp.log")?)
        .spawn()?;
    std::fs::write("/tmp/ai-toolkit-mcp.pid", ai_child.id().to_string())?;

    output::step("Starting ComfyUI MCP Server...");
    let comfy_child = std::process::Command::new(&python_str)
        .args([
            "-m",
            "mcp_comfyui.server",
            "--mode",
            "http",
            "--host",
            "0.0.0.0",
        ])
        .env("PYTHONPATH", format!("{}/tools/mcp", root.display()))
        .stdout(std::fs::File::create("/tmp/comfyui-mcp.log")?)
        .stderr(std::fs::File::create("/tmp/comfyui-mcp.log")?)
        .spawn()?;
    std::fs::write("/tmp/comfyui-mcp.pid", comfy_child.id().to_string())?;

    output::success("AI services started successfully!");
    output::info(&format!(
        "AI Toolkit MCP: http://0.0.0.0:8012 (PID: {})",
        ai_child.id()
    ));
    output::info(&format!(
        "ComfyUI MCP: http://0.0.0.0:8013 (PID: {})",
        comfy_child.id()
    ));

    Ok(())
}
