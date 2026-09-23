//! `docker compose` helpers for the `python-ci` and `rust-ci` containers.

use std::path::Path;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};

use anyhow::{Context, Result};

use crate::shared::{output, process};

/// Compose profile that the CI containers live under.
const CI_PROFILE: &str = "ci";

// Idempotent build guards -- prevent re-building the same image within one invocation
static PYTHON_CI_BUILT: AtomicBool = AtomicBool::new(false);
static RUST_CI_BUILT: AtomicBool = AtomicBool::new(false);

/// Build the Python CI Docker image (idempotent per process)
pub fn build_python_ci(compose_file: &Path) -> Result<()> {
    build_once(&PYTHON_CI_BUILT, compose_file, "python-ci", "Python")
}

/// Build the Rust CI Docker image (idempotent per process)
pub fn build_rust_ci(compose_file: &Path) -> Result<()> {
    build_once(&RUST_CI_BUILT, compose_file, "rust-ci", "Rust")
}

fn build_once(flag: &AtomicBool, compose_file: &Path, service: &str, label: &str) -> Result<()> {
    if flag.load(Ordering::SeqCst) {
        return Ok(());
    }
    output::step(&format!("Building {label} CI image..."));
    let args = compose_args(compose_file, Some(CI_PROFILE), &["build", service]);
    run_docker(&args)?;
    // Only mark as built on success so a later call can retry a failed build.
    flag.store(true, Ordering::SeqCst);
    Ok(())
}

/// `compose -f <file> [--profile <p>] <rest...>` as an owned argument vector.
pub fn compose_args(compose_file: &Path, profile: Option<&str>, rest: &[&str]) -> Vec<String> {
    let mut args = vec![
        "compose".to_string(),
        "-f".to_string(),
        compose_file.to_string_lossy().into_owned(),
    ];
    if let Some(p) = profile {
        args.push("--profile".into());
        args.push(p.into());
    }
    args.extend(rest.iter().map(|s| (*s).to_string()));
    args
}

fn run_docker(args: &[String]) -> Result<()> {
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    process::run("docker", &refs)
}

/// Argument vector for `docker compose run --rm [-w dir] [-e K=V]... <service> <cmd...>`.
pub fn ci_run_args(
    compose_file: &Path,
    service: &str,
    workdir: Option<&str>,
    env_vars: &[(&str, &str)],
    cmd: &[&str],
) -> Vec<String> {
    let mut args = compose_args(compose_file, Some(CI_PROFILE), &["run", "--rm"]);
    if let Some(dir) = workdir {
        args.push("-w".into());
        args.push(format!("/app/{}", dir.trim_start_matches("./")));
    }
    for (k, v) in env_vars {
        args.push("-e".into());
        args.push(format!("{k}={v}"));
    }
    args.push(service.into());
    args.extend(cmd.iter().map(|s| (*s).to_string()));
    args
}

/// Run a cargo command inside the Rust CI container at the given workspace path.
/// Pass "." for `workspace_path` to use the container's default workdir.
pub fn run_cargo(compose_file: &Path, workspace_path: &str, cargo_args: &[&str]) -> Result<()> {
    run_cargo_with_env(compose_file, workspace_path, cargo_args, &[])
}

/// [`run_cargo`] with extra container environment variables.
pub fn run_cargo_with_env(
    compose_file: &Path,
    workspace_path: &str,
    cargo_args: &[&str],
    env_vars: &[(&str, &str)],
) -> Result<()> {
    build_rust_ci(compose_file)?;
    let workdir = (workspace_path != ".").then_some(workspace_path);
    let mut cmd = vec!["cargo"];
    cmd.extend_from_slice(cargo_args);
    run_docker(&ci_run_args(
        compose_file,
        "rust-ci",
        workdir,
        env_vars,
        &cmd,
    ))
}

/// Run a bash script inside the Rust CI container (repo root as workdir).
pub fn run_rust_ci_script(compose_file: &Path, script: &str) -> Result<()> {
    build_rust_ci(compose_file)?;
    run_docker(&ci_run_args(
        compose_file,
        "rust-ci",
        None,
        &[],
        &["bash", "-c", script],
    ))
}

/// Run a command inside the Python CI container; non-zero exit is an error.
pub fn run_python_ci(
    compose_file: &Path,
    cmd_args: &[&str],
    env_vars: &[(&str, &str)],
) -> Result<()> {
    build_python_ci(compose_file)?;
    run_docker(&ci_run_args(
        compose_file,
        "python-ci",
        None,
        env_vars,
        cmd_args,
    ))
}

/// Run a command inside the Python CI container, returning Ok(true) on exit 0,
/// Ok(false) on non-zero exit, and Err only if docker could not be run.
pub fn run_python_ci_check(
    compose_file: &Path,
    cmd_args: &[&str],
    env_vars: &[(&str, &str)],
) -> Result<bool> {
    build_python_ci(compose_file)?;
    let args = ci_run_args(compose_file, "python-ci", None, env_vars, cmd_args);
    let status = Command::new("docker")
        .args(&args)
        .stdin(Stdio::null())
        .status()
        .context("failed to run docker compose")?;
    Ok(status.success())
}

/// Check whether a compose service has a running container.
pub fn is_service_running(service: &str) -> bool {
    process::run_output(
        "docker",
        &["compose", "ps", "--status", "running", "--services"],
    )
    .map(|o| {
        String::from_utf8_lossy(&o.stdout)
            .lines()
            .any(|l| l.trim() == service)
    })
    .unwrap_or(false)
}

/// Health (or plain state, if the container has no healthcheck) of a compose
/// service's container, e.g. `healthy`, `starting`, `running`, `exited`.
/// Returns None if the service has no container.
pub fn service_health(service: &str) -> Option<String> {
    let ids = process::run_output("docker", &["compose", "ps", "-q", service]).ok()?;
    let id = String::from_utf8_lossy(&ids.stdout)
        .lines()
        .next()?
        .trim()
        .to_string();
    if id.is_empty() {
        return None;
    }
    let out = process::run_output(
        "docker",
        &[
            "inspect",
            "-f",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
            &id,
        ],
    )
    .ok()?;
    out.status
        .success()
        .then(|| String::from_utf8_lossy(&out.stdout).trim().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ci_run_args_layout() {
        let args = ci_run_args(
            Path::new("dc.yml"),
            "rust-ci",
            Some("tools/rust/foo"),
            &[("A", "1")],
            &["cargo", "test"],
        );
        assert_eq!(
            args,
            [
                "compose",
                "-f",
                "dc.yml",
                "--profile",
                "ci",
                "run",
                "--rm",
                "-w",
                "/app/tools/rust/foo",
                "-e",
                "A=1",
                "rust-ci",
                "cargo",
                "test"
            ]
        );
    }

    #[test]
    fn compose_args_without_profile() {
        let args = compose_args(Path::new("x.yml"), None, &["ps"]);
        assert_eq!(args, ["compose", "-f", "x.yml", "ps"]);
    }
}
