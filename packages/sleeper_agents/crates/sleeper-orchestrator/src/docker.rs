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

/// Arguments for `docker compose run --rm --name <container_name>` of the GPU service.
///
/// `env` entries become `-e KEY=VALUE` flags; `cmd` is run inside the container.
pub fn compose_run_args(
    compose_file: &Path,
    container_name: &str,
    env: &[(String, String)],
    cmd: &[String],
) -> Vec<String> {
    let mut args: Vec<String> = vec![
        "compose".into(),
        "-f".into(),
        compose_file.to_string_lossy().into_owned(),
        "run".into(),
        "--rm".into(),
        "--name".into(),
        container_name.into(),
    ];
    for (key, value) in env {
        args.push("-e".into());
        args.push(format!("{key}={value}"));
    }
    args.push(GPU_SERVICE.into());
    args.extend(cmd.iter().cloned());
    args
}

/// Arguments for `docker rm -f <container_name>`.
pub fn force_remove_args(container_name: &str) -> Vec<String> {
    vec!["rm".into(), "-f".into(), container_name.into()]
}

/// A container name for a one-shot run, unique per process and start time.
///
/// Knowing the name up front lets a timed-out run be removed: killing the
/// `docker compose run` client alone leaves the container (and its GPU work) running.
pub fn one_shot_container_name() -> String {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or_default();
    format!("{GPU_SERVICE}-run-{}-{nanos}", std::process::id())
}

/// Run a one-shot command in the GPU container, removing the container if it times out.
pub fn run_in_container_with_timeout(
    compose_file: &Path,
    env: &[(String, String)],
    cmd: &[String],
    timeout: std::time::Duration,
) -> Result<()> {
    let name = one_shot_container_name();
    let args = compose_run_args(compose_file, &name, env, cmd);
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    process::run_with_timeout_then("docker", &refs, timeout, || {
        crate::output::warn(&format!("Timed out; removing container {name}"));
        let rm = force_remove_args(&name);
        let rm_refs: Vec<&str> = rm.iter().map(String::as_str).collect();
        if !process::run_check("docker", &rm_refs).unwrap_or(false) {
            crate::output::warn(&format!(
                "Could not remove container {name}; stop it with: docker rm -f {name}"
            ));
        }
    })
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

impl std::fmt::Display for ContainerState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Running(s) => write!(f, "running ({s})"),
            Self::Stopped(s) => write!(f, "stopped ({s})"),
            Self::NotFound => write!(f, "not found"),
            Self::DockerUnavailable => write!(f, "docker unavailable"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gpu_service_name() {
        assert_eq!(GPU_SERVICE, "sleeper-eval-gpu");
    }

    #[test]
    fn compose_run_args_names_the_container() {
        let args = compose_run_args(
            Path::new("docker/docker-compose.gpu.yml"),
            "sleeper-eval-gpu-run-1-2",
            &[("SLEEPER_BATCH_SIZE".into(), "8".into())],
            &["python3".into(), "-m".into(), "sleeper_agents.cli".into()],
        );
        assert_eq!(
            args,
            [
                "compose",
                "-f",
                "docker/docker-compose.gpu.yml",
                "run",
                "--rm",
                "--name",
                "sleeper-eval-gpu-run-1-2",
                "-e",
                "SLEEPER_BATCH_SIZE=8",
                "sleeper-eval-gpu",
                "python3",
                "-m",
                "sleeper_agents.cli",
            ]
        );
    }

    #[test]
    fn force_remove_targets_the_named_container() {
        assert_eq!(force_remove_args("abc"), ["rm", "-f", "abc"]);
    }

    #[test]
    fn one_shot_container_names_are_valid_and_distinct() {
        let a = one_shot_container_name();
        std::thread::sleep(std::time::Duration::from_millis(2));
        let b = one_shot_container_name();
        assert_ne!(a, b);
        assert!(a.starts_with("sleeper-eval-gpu-run-"));
        // Docker container names: [a-zA-Z0-9][a-zA-Z0-9_.-]*
        assert!(
            a.chars()
                .all(|c| c.is_ascii_alphanumeric() || "_.-".contains(c))
        );
    }

    #[test]
    fn container_state_display() {
        assert_eq!(
            ContainerState::Running("Up 5 minutes".into()).to_string(),
            "running (Up 5 minutes)"
        );
        assert_eq!(
            ContainerState::Stopped("Exited (0)".into()).to_string(),
            "stopped (Exited (0))"
        );
        assert_eq!(ContainerState::NotFound.to_string(), "not found");
        assert_eq!(
            ContainerState::DockerUnavailable.to_string(),
            "docker unavailable"
        );
    }

    #[test]
    fn container_state_debug() {
        // Verify Debug derive works
        let state = ContainerState::Running("Up".into());
        let debug = format!("{state:?}");
        assert!(debug.contains("Running"));
    }

    #[test]
    fn is_container_running_returns_bool() {
        // Just verifies the function doesn't panic; actual result
        // depends on whether Docker is running on the host.
        let _running = is_container_running();
    }

    #[test]
    fn container_status_returns_state() {
        // Verifies the function doesn't panic.
        let state = container_status();
        let display = state.to_string();
        assert!(!display.is_empty());
    }
}
