use std::path::Path;
use std::process::{Command, ExitStatus, Stdio};
use std::time::Duration;

use anyhow::{Context, Result, bail};

/// Run a command, inheriting stdout/stderr so the user sees output in real time.
/// Returns Ok(()) if the command exits 0, Err otherwise.
pub fn run(cmd: &str, args: &[&str]) -> Result<()> {
    let status = Command::new(cmd)
        .args(args)
        .stdin(Stdio::null())
        .status()
        .with_context(|| format!("failed to execute: {cmd} {}", args.join(" ")))?;
    check_status(cmd, args, status)
}

/// Run a command in a specific working directory.
pub fn run_in(dir: &Path, cmd: &str, args: &[&str]) -> Result<()> {
    let status = Command::new(cmd)
        .args(args)
        .current_dir(dir)
        .stdin(Stdio::null())
        .status()
        .with_context(|| {
            format!(
                "failed to execute in {}: {cmd} {}",
                dir.display(),
                args.join(" ")
            )
        })?;
    check_status(cmd, args, status)
}

/// Run a command and capture its stdout as a string.
pub fn run_capture(cmd: &str, args: &[&str]) -> Result<String> {
    let output = Command::new(cmd)
        .args(args)
        .stdin(Stdio::null())
        .stderr(Stdio::inherit())
        .output()
        .with_context(|| format!("failed to execute: {cmd} {}", args.join(" ")))?;
    if !output.status.success() {
        bail!("{cmd} {} exited with {}", args.join(" "), output.status);
    }
    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

/// Run a command, returning Ok(true) if exit 0, Ok(false) if non-zero, Err on spawn failure.
pub fn run_check(cmd: &str, args: &[&str]) -> Result<bool> {
    let status = Command::new(cmd)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .with_context(|| format!("failed to execute: {cmd}"))?;
    Ok(status.success())
}

/// Run a command with a timeout. Returns Ok(()) on success, Err on failure or timeout.
#[allow(dead_code)]
pub fn run_with_timeout(cmd: &str, args: &[&str], timeout: Duration) -> Result<()> {
    let mut child = Command::new(cmd)
        .args(args)
        .stdin(Stdio::null())
        .spawn()
        .with_context(|| format!("failed to spawn: {cmd}"))?;

    match child.wait_timeout(timeout) {
        Ok(Some(status)) => check_status(cmd, args, status),
        Ok(None) => {
            let _ = child.kill();
            bail!("{cmd} timed out after {}s", timeout.as_secs());
        },
        Err(e) => bail!("error waiting for {cmd}: {e}"),
    }
}

/// Check if a command exists on PATH.
pub fn command_exists(cmd: &str) -> bool {
    Command::new("which")
        .arg(cmd)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .is_ok_and(|s| s.success())
}

fn check_status(cmd: &str, args: &[&str], status: ExitStatus) -> Result<()> {
    if status.success() {
        Ok(())
    } else {
        bail!("{cmd} {} exited with {}", args.join(" "), status);
    }
}

/// Extension trait to add wait_timeout to Child
trait ChildExt {
    fn wait_timeout(&mut self, timeout: Duration) -> std::io::Result<Option<ExitStatus>>;
}

impl ChildExt for std::process::Child {
    fn wait_timeout(&mut self, timeout: Duration) -> std::io::Result<Option<ExitStatus>> {
        let start = std::time::Instant::now();
        loop {
            match self.try_wait()? {
                Some(status) => return Ok(Some(status)),
                None => {
                    if start.elapsed() >= timeout {
                        return Ok(None);
                    }
                    std::thread::sleep(Duration::from_millis(100));
                },
            }
        }
    }
}
