use anyhow::Result;
use clap::Subcommand;

use crate::shared::{output, process, project};

#[derive(Subcommand)]
pub enum SetupAction {
    /// Setup host environment for AI agents
    Agents,
    /// Setup GitHub Actions runner (basic)
    Runner,
    /// Setup GitHub Actions runner (full with system dependencies)
    RunnerFull,
    /// Fix GitHub Actions runner permissions
    Permissions,
    /// Initialize Docker output directories
    InitDirs,
}

pub fn run(action: SetupAction) -> Result<()> {
    let root = project::find_project_root()?;
    std::env::set_current_dir(&root)?;

    match action {
        SetupAction::Agents => setup_agents(&root),
        SetupAction::Runner => {
            // Delegate to existing script for now -- this is a one-time setup
            process::run("bash", &["automation/setup/runner/setup-runner.sh"])
        },
        SetupAction::RunnerFull => {
            process::run("bash", &["automation/setup/runner/setup-runner-full.sh"])
        },
        SetupAction::Permissions => setup_permissions(),
        SetupAction::InitDirs => init_dirs(&root),
    }
}

fn setup_agents(root: &std::path::Path) -> Result<()> {
    output::header("Checking host environment for AI agents");

    let mut issues = Vec::new();

    // Check required tools
    let tools = [
        ("git", "Version control"),
        ("gh", "GitHub CLI"),
        ("docker", "Container runtime"),
        ("cargo", "Rust toolchain"),
    ];

    for (cmd, desc) in &tools {
        if process::command_exists(cmd) {
            output::success(&format!("{cmd} ({desc}) found"));
        } else {
            output::fail(&format!("{cmd} ({desc}) not found"));
            issues.push(format!("Install {cmd}: {desc}"));
        }
    }

    // Optional tools
    let optional = [("claude", "Claude CLI"), ("node", "Node.js runtime")];

    for (cmd, desc) in &optional {
        if process::command_exists(cmd) {
            output::success(&format!("{cmd} ({desc}) found"));
        } else {
            output::warn(&format!("{cmd} ({desc}) not found (optional)"));
        }
    }

    // Check gh auth
    if process::command_exists("gh") {
        if process::run_check("gh", &["auth", "status"])? {
            output::success("GitHub CLI authenticated");
        } else {
            output::warn("GitHub CLI not authenticated (run: gh auth login)");
            issues.push("Run: gh auth login".to_string());
        }
    }

    // Check github-agents binary
    let agents_binary = root.join("tools/rust/github-agents-cli/target/release/github-agents");
    if agents_binary.exists() {
        output::success("github-agents binary found");
    } else {
        output::warn("github-agents binary not built");
        output::info("  Build with: cd tools/rust/github-agents-cli && cargo build --release");
        issues.push("Build github-agents binary".to_string());
    }

    // Summary
    println!();
    if issues.is_empty() {
        output::success("All agent prerequisites satisfied!");
    } else {
        output::header("Action items");
        for issue in &issues {
            output::info(&format!("  - {issue}"));
        }
    }
    Ok(())
}

fn setup_permissions() -> Result<()> {
    output::header("Setting up GitHub Actions runner permissions");

    let root = project::find_project_root()?;

    // Create output directories
    let dirs = [
        "outputs",
        "outputs/video-editor",
        "outputs/manim",
        "outputs/latex",
        "outputs/content-creation",
        "outputs/blender",
        "outputs/meme-generator",
    ];

    for dir in &dirs {
        let path = root.join(dir);
        if !path.exists() {
            output::step(&format!("Creating {dir}..."));
            std::fs::create_dir_all(&path)?;
        }
    }

    // Clean problematic files
    output::step("Cleaning Python cache files...");
    for pattern in &["__pycache__", ".pytest_cache", "*.pyc"] {
        let _ = std::process::Command::new("find")
            .args([
                root.to_str().unwrap_or("."),
                "-name",
                pattern,
                "-exec",
                "rm",
                "-rf",
                "{}",
                "+",
            ])
            .status();
    }

    // Export docker user
    let uid = unsafe { libc::getuid() };
    let gid = unsafe { libc::getgid() };
    output::info(&format!("Docker user: {uid}:{gid}"));

    // Write .env for docker compose
    let env_content = format!("USER_ID={uid}\nGROUP_ID={gid}\n");
    std::fs::write(root.join(".env"), env_content)?;
    output::success(".env file written");

    // Git safe directory
    let _ = process::run(
        "git",
        &[
            "config",
            "--global",
            "--add",
            "safe.directory",
            root.to_str().unwrap_or("."),
        ],
    );

    output::success("Permissions setup complete");
    Ok(())
}

fn init_dirs(root: &std::path::Path) -> Result<()> {
    output::header("Initializing Docker output directories");

    let dirs = [
        "outputs",
        "outputs/video-editor",
        "outputs/manim",
        "outputs/latex",
        "outputs/content-creation",
        "outputs/blender",
        "outputs/meme-generator",
    ];

    for dir in &dirs {
        let path = root.join(dir);
        // Skip symlinks
        if path.is_symlink() {
            output::info(&format!("Skipping symlink: {dir}"));
            continue;
        }
        if !path.exists() {
            output::step(&format!("Creating {dir}..."));
            std::fs::create_dir_all(&path)?;
        }
    }

    // Fix ownership via Docker to avoid sudo
    output::step("Fixing directory ownership...");
    let uid = unsafe { libc::getuid() };
    let gid = unsafe { libc::getgid() };
    let _ = std::process::Command::new("docker")
        .args([
            "run",
            "--rm",
            "-v",
            &format!("{}:/work", root.join("outputs").display()),
            "busybox",
            "chown",
            "-R",
            &format!("{uid}:{gid}"),
            "/work",
        ])
        .status();

    output::success("Output directories initialized");
    Ok(())
}
