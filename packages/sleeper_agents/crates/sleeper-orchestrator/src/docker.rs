use std::path::Path;

use anyhow::{Context, Result};

use crate::process;

/// The docker compose service name for the GPU evaluation container.
const GPU_SERVICE: &str = "sleeper-eval-gpu";

/// Run `docker compose` with the given compose file and subcommand args.
pub fn docker_compose(compose_file: &Path, args: &[&str]) -> Result<()> {
    let cf = compose_file.to_string_lossy();
    let mut cmd_args: Vec<&str> = vec!["compose", "-f", &cf];
    cmd_args.extend_from_slice(args);
    process::run("docker", &cmd_args)
}

/// Build the GPU evaluation container image.
pub fn build_gpu_image(compose_file: &Path) -> Result<()> {
    crate::output::info("Building GPU container image...");
    docker_compose(compose_file, &["build", GPU_SERVICE])
}

/// Start the GPU evaluation container in detached mode.
pub fn start_container(compose_file: &Path) -> Result<()> {
    crate::output::info("Starting GPU container...");
    docker_compose(compose_file, &["up", "-d", GPU_SERVICE])
}

/// Stop the GPU evaluation container.
pub fn stop_container(compose_file: &Path) -> Result<()> {
    crate::output::info("Stopping GPU container...");
    docker_compose(compose_file, &["down"])
}

/// Run a one-shot command inside the GPU container.
pub fn run_in_container(compose_file: &Path, cmd_args: &[&str]) -> Result<()> {
    let cf = compose_file.to_string_lossy();
    let mut args: Vec<&str> = vec!["compose", "-f", &cf, "run", "--rm", GPU_SERVICE];
    args.extend_from_slice(cmd_args);
    process::run("docker", &args)
}

/// Run a one-shot command and capture stdout.
pub fn run_in_container_capture(compose_file: &Path, cmd_args: &[&str]) -> Result<String> {
    let cf = compose_file.to_string_lossy();
    let mut args: Vec<&str> = vec!["compose", "-f", &cf, "run", "--rm", GPU_SERVICE];
    args.extend_from_slice(cmd_args);
    process::run_capture("docker", &args)
}

/// Check if the GPU service container is currently running.
pub fn is_container_running() -> bool {
    std::process::Command::new("docker")
        .args(["ps", "--format", "{{.Names}}"])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .output()
        .map(|o| {
            String::from_utf8_lossy(&o.stdout)
                .lines()
                .any(|l| l.contains(GPU_SERVICE))
        })
        .unwrap_or(false)
}

/// Get container status (running, exited, not found).
pub fn container_status() -> ContainerState {
    let output = std::process::Command::new("docker")
        .args([
            "ps",
            "-a",
            "--filter",
            &format!("name={GPU_SERVICE}"),
            "--format",
            "{{.Status}}",
        ])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .output();

    match output {
        Ok(o) => {
            let status = String::from_utf8_lossy(&o.stdout);
            let status = status.trim();
            if status.is_empty() {
                ContainerState::NotFound
            } else if status.starts_with("Up") {
                ContainerState::Running(status.to_string())
            } else {
                ContainerState::Stopped(status.to_string())
            }
        },
        Err(_) => ContainerState::DockerUnavailable,
    }
}

/// Check if nvidia-smi is available inside the container.
pub fn check_gpu(compose_file: &Path) -> Result<String> {
    run_in_container_capture(
        compose_file,
        &[
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader",
        ],
    )
    .context("nvidia-smi failed inside container")
}

/// Remove stopped containers and dangling images for this service.
pub fn clean_containers(compose_file: &Path) -> Result<()> {
    crate::output::info("Removing stopped containers...");
    docker_compose(compose_file, &["down", "--remove-orphans"])?;

    // Remove dangling images
    let _ = process::run_check("docker", &["image", "prune", "-f"]);
    Ok(())
}

/// Remove named volumes used by the sleeper agents containers.
pub fn clean_volumes() -> Result<()> {
    crate::output::info("Removing sleeper agent volumes...");
    for vol in &["sleeper-models", "sleeper-results", "sleeper-gpu-cache"] {
        let _ = process::run_check("docker", &["volume", "rm", vol]);
    }
    Ok(())
}

/// State of the GPU evaluation container.
#[derive(Debug)]
pub enum ContainerState {
    Running(String),
    Stopped(String),
    NotFound,
    DockerUnavailable,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gpu_service_name() {
        assert_eq!(GPU_SERVICE, "sleeper-eval-gpu");
    }
}
