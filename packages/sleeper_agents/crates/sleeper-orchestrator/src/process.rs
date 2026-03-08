use std::process::{Command, ExitStatus, Stdio};
use std::time::Duration;

use anyhow::{Context, Result, bail};

/// Run a command, inheriting stdout/stderr so the user sees output in real time.
pub fn run(cmd: &str, args: &[&str]) -> Result<()> {
    let status = Command::new(cmd)
        .args(args)
        .stdin(Stdio::null())
        .status()
        .with_context(|| format!("failed to execute: {cmd} {}", args.join(" ")))?;
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

/// Run a command, returning Ok(true) on exit 0, Ok(false) on non-zero.
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

/// Run a command with a timeout.
pub fn run_with_timeout(cmd: &str, args: &[&str], timeout: Duration) -> Result<()> {
    let mut child = Command::new(cmd)
        .args(args)
        .stdin(Stdio::null())
        .spawn()
        .with_context(|| format!("failed to spawn: {cmd}"))?;

    match wait_timeout(&mut child, timeout) {
        Ok(Some(status)) => check_status(cmd, args, status),
        Ok(None) => {
            let _ = child.kill();
            bail!("{cmd} timed out after {}s", timeout.as_secs());
        },
        Err(e) => bail!("error waiting for {cmd}: {e}"),
    }
}

fn check_status(cmd: &str, args: &[&str], status: ExitStatus) -> Result<()> {
    if status.success() {
        Ok(())
    } else {
        bail!("{cmd} {} exited with {}", args.join(" "), status);
    }
}

fn wait_timeout(
    child: &mut std::process::Child,
    timeout: Duration,
) -> std::io::Result<Option<ExitStatus>> {
    let start = std::time::Instant::now();
    loop {
        match child.try_wait()? {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn run_check_success() {
        assert!(run_check("true", &[]).unwrap());
    }

    #[test]
    fn run_check_failure() {
        assert!(!run_check("false", &[]).unwrap());
    }

    #[test]
    fn run_capture_echoes() {
        let output = run_capture("echo", &["hello"]).unwrap();
        assert_eq!(output.trim(), "hello");
    }

    #[test]
    fn run_capture_failure() {
        let result = run_capture("false", &[]);
        assert!(result.is_err());
    }

    #[test]
    fn run_success() {
        assert!(run("true", &[]).is_ok());
    }

    #[test]
    fn run_failure() {
        assert!(run("false", &[]).is_err());
    }

    #[test]
    fn run_with_timeout_completes() {
        let result = run_with_timeout("true", &[], Duration::from_secs(5));
        assert!(result.is_ok());
    }

    #[test]
    fn run_with_timeout_kills() {
        let result = run_with_timeout("sleep", &["60"], Duration::from_millis(200));
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(
            msg.contains("timed out"),
            "expected timeout error, got: {msg}"
        );
    }

    #[test]
    fn run_nonexistent_command() {
        let result = run("nonexistent_cmd_12345", &[]);
        assert!(result.is_err());
    }
}
