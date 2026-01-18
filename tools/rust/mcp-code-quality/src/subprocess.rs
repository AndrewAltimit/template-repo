//! Subprocess execution with timeout handling

use std::path::Path;
use std::process::Stdio;
use std::time::Duration;

use tokio::process::Command;
use tokio::time::timeout;
use tracing::{debug, warn};

use crate::error::{Result, ToolError};

/// Result of a subprocess execution
#[derive(Debug)]
pub struct SubprocessResult {
    /// Exit code (0 = success)
    #[allow(dead_code)] // Available for callers
    pub exit_code: i32,
    /// Standard output
    pub stdout: String,
    /// Standard error
    pub stderr: String,
    /// Whether the process succeeded (exit code 0)
    pub success: bool,
}

/// Execute a subprocess with timeout
pub async fn run_command<S: AsRef<str> + std::fmt::Debug>(
    command: &str,
    args: &[S],
    cwd: Option<&Path>,
    timeout_duration: Duration,
) -> Result<SubprocessResult> {
    debug!(
        "Running command: {} {:?} (timeout: {:?})",
        command, args, timeout_duration
    );

    let mut cmd = Command::new(command);
    cmd.args(args.iter().map(|s| s.as_ref()))
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true); // Kill process if future is dropped

    if let Some(dir) = cwd {
        cmd.current_dir(dir);
    }

    // Spawn with timeout
    let result = timeout(timeout_duration, cmd.output()).await;

    match result {
        Ok(Ok(output)) => {
            let exit_code = output.status.code().unwrap_or(-1);
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();

            debug!("Command completed with exit code: {}", exit_code);

            Ok(SubprocessResult {
                exit_code,
                stdout,
                stderr,
                success: output.status.success(),
            })
        }
        Ok(Err(e)) => {
            warn!("Command failed to execute: {}", e);
            Err(ToolError::SubprocessFailed(format!(
                "Failed to execute {}: {}",
                command, e
            )))
        }
        Err(_) => {
            warn!(
                "Command timed out after {:?}: {} {:?}",
                timeout_duration, command, args
            );
            Err(ToolError::Timeout(timeout_duration.as_secs()))
        }
    }
}

/// Check if a command is available on the system
pub async fn check_tool_available(command: &str) -> bool {
    // Try running with --version to check availability
    let result = timeout(Duration::from_secs(5), async {
        Command::new(command)
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .await
    })
    .await;

    matches!(result, Ok(Ok(status)) if status.success())
}

/// Get the version of a tool (if available)
pub async fn get_tool_version(command: &str) -> Option<String> {
    let result = timeout(Duration::from_secs(5), async {
        Command::new(command)
            .arg("--version")
            .output()
            .await
    })
    .await;

    if let Ok(Ok(output)) = result
        && output.status.success()
    {
        let version = String::from_utf8_lossy(&output.stdout);
        // Get first line of version output
        return version.lines().next().map(|s| s.trim().to_string());
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_run_command_success() {
        let result = run_command("echo", &["hello"], None, Duration::from_secs(10)).await;

        assert!(result.is_ok());
        let output = result.unwrap();
        assert!(output.success);
        assert_eq!(output.exit_code, 0);
        assert!(output.stdout.contains("hello"));
    }

    #[tokio::test]
    async fn test_run_command_failure() {
        let args: &[&str] = &[];
        let result = run_command("false", args, None, Duration::from_secs(10)).await;

        assert!(result.is_ok());
        let output = result.unwrap();
        assert!(!output.success);
    }

    #[tokio::test]
    async fn test_run_command_not_found() {
        let args: &[&str] = &[];
        let result = run_command(
            "nonexistent_command_12345",
            args,
            None,
            Duration::from_secs(10),
        )
        .await;

        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_check_tool_available() {
        // 'echo' should always be available
        assert!(check_tool_available("echo").await);

        // This should not exist
        assert!(!check_tool_available("nonexistent_tool_12345").await);
    }
}
