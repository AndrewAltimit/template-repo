use std::path::Path;
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};

use anyhow::{Context, Result};

// Idempotent build guards -- prevent re-building the same image within one invocation
static PYTHON_CI_BUILT: AtomicBool = AtomicBool::new(false);
static RUST_CI_BUILT: AtomicBool = AtomicBool::new(false);
static RUST_CI_NIGHTLY_BUILT: AtomicBool = AtomicBool::new(false);

/// Build the Python CI Docker image (idempotent per process)
pub fn build_python_ci(compose_file: &Path) -> Result<()> {
    if PYTHON_CI_BUILT.swap(true, Ordering::SeqCst) {
        return Ok(());
    }
    crate::shared::output::step("Building Python CI image...");
    docker_compose(compose_file, &[], &["build", "python-ci"])
}

/// Build the Rust CI Docker image (idempotent per process)
pub fn build_rust_ci(compose_file: &Path) -> Result<()> {
    if RUST_CI_BUILT.swap(true, Ordering::SeqCst) {
        return Ok(());
    }
    crate::shared::output::step("Building Rust CI image...");
    docker_compose(compose_file, &["--profile", "ci"], &["build", "rust-ci"])
}

/// Build the Rust CI nightly Docker image (idempotent per process)
pub fn build_rust_ci_nightly(compose_file: &Path) -> Result<()> {
    if RUST_CI_NIGHTLY_BUILT.swap(true, Ordering::SeqCst) {
        return Ok(());
    }
    crate::shared::output::step("Building Rust CI nightly image...");
    docker_compose(
        compose_file,
        &["--profile", "ci"],
        &["build", "rust-ci-nightly"],
    )
}

/// Run `docker compose` with the given compose file, global flags, and subcommand args.
pub fn docker_compose(compose_file: &Path, global_flags: &[&str], args: &[&str]) -> Result<()> {
    let cf = compose_file.to_string_lossy();
    let mut cmd_args: Vec<&str> = vec!["compose", "-f", &cf];
    cmd_args.extend_from_slice(global_flags);
    cmd_args.extend_from_slice(args);
    crate::shared::process::run("docker", &cmd_args)
}

/// Run a cargo command inside the Rust CI container at the given workspace path.
/// Pass "." for workspace_path to use the container's default workdir.
pub fn run_cargo(compose_file: &Path, workspace_path: &str, cargo_args: &[&str]) -> Result<()> {
    build_rust_ci(compose_file)?;
    let cf = compose_file.to_string_lossy();

    let mut args: Vec<String> = vec![
        "compose".into(),
        "-f".into(),
        cf.to_string(),
        "--profile".into(),
        "ci".into(),
        "run".into(),
        "--rm".into(),
    ];

    if workspace_path != "." {
        args.push("-w".into());
        args.push(format!("/app/{workspace_path}"));
    }

    args.push("rust-ci".into());
    args.push("cargo".into());
    for a in cargo_args {
        args.push((*a).to_string());
    }

    let str_args: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    crate::shared::process::run("docker", &str_args)
}

/// Run a command inside the Python CI container.
pub fn run_python_ci(
    compose_file: &Path,
    cmd_args: &[&str],
    env_vars: &[(&str, &str)],
) -> Result<()> {
    build_python_ci(compose_file)?;
    let cf = compose_file.to_string_lossy();

    let mut args: Vec<String> = vec![
        "compose".into(),
        "-f".into(),
        cf.to_string(),
        "run".into(),
        "--rm".into(),
    ];

    for (k, v) in env_vars {
        args.push("-e".into());
        args.push(format!("{k}={v}"));
    }

    args.push("python-ci".into());
    for a in cmd_args {
        args.push((*a).to_string());
    }

    let str_args: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    crate::shared::process::run("docker", &str_args)
}

/// Run a command inside the Python CI container, returning Ok(true) if exit 0, Ok(false) if non-zero.
pub fn run_python_ci_check(
    compose_file: &Path,
    cmd_args: &[&str],
    env_vars: &[(&str, &str)],
) -> Result<bool> {
    build_python_ci(compose_file)?;
    let cf = compose_file.to_string_lossy();

    let mut args: Vec<String> = vec![
        "compose".into(),
        "-f".into(),
        cf.to_string(),
        "run".into(),
        "--rm".into(),
    ];

    for (k, v) in env_vars {
        args.push("-e".into());
        args.push(format!("{k}={v}"));
    }

    args.push("python-ci".into());
    for a in cmd_args {
        args.push((*a).to_string());
    }

    let str_args: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    let status = Command::new("docker")
        .args(&str_args)
        .stdin(Stdio::null())
        .status()
        .context("failed to run docker compose")?;
    Ok(status.success())
}

/// Check if a Docker service is running
pub fn is_service_running(service: &str) -> bool {
    Command::new("docker")
        .args(["ps", "--format", "{{.Names}}"])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .map(|o| {
            String::from_utf8_lossy(&o.stdout)
                .lines()
                .any(|l| l.contains(service))
        })
        .unwrap_or(false)
}
