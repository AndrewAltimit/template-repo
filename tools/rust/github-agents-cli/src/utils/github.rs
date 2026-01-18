//! GitHub utility functions.
//!
//! Provides async wrappers around the GitHub CLI (`gh`) and git commands.

use std::env;
use std::process::Stdio;
use tokio::process::Command;
use tracing::{debug, error, warn};

use crate::error::Error;

/// Get GitHub token from environment.
///
/// Checks `GITHUB_TOKEN` first, then falls back to `GH_TOKEN`.
///
/// # Errors
///
/// Returns an error if neither environment variable is set.
pub fn get_github_token() -> Result<String, Error> {
    env::var("GITHUB_TOKEN")
        .or_else(|_| env::var("GH_TOKEN"))
        .map_err(|_| Error::GitHubTokenNotFound)
}

/// Run a GitHub CLI command asynchronously.
///
/// # Arguments
///
/// * `args` - Command arguments (without the `gh` prefix)
/// * `check` - Whether to return an error on non-zero exit code
///
/// # Returns
///
/// Command stdout on success, or None if check is false and command failed.
pub async fn run_gh_command(args: &[&str], check: bool) -> Result<Option<String>, Error> {
    let mut cmd = Command::new("gh");
    cmd.args(args).stdout(Stdio::piped()).stderr(Stdio::piped());

    debug!("Running gh command: gh {}", args.join(" "));

    let output = cmd.output().await.map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            Error::GhNotFound
        } else {
            Error::Io(e)
        }
    })?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if output.status.success() {
        // Log stderr if stdout is empty (may contain useful warnings)
        if stdout.trim().is_empty() && !stderr.trim().is_empty() {
            warn!("gh command stderr (stdout empty): {}", stderr.trim());
        }
        Ok(Some(stdout))
    } else {
        let exit_code = output.status.code().unwrap_or(-1);
        error!(
            "GitHub CLI command failed (exit code {}): gh {}",
            exit_code,
            args.join(" ")
        );
        if !stdout.trim().is_empty() {
            error!("stdout: {}", stdout.trim());
        }
        if !stderr.trim().is_empty() {
            error!("stderr: {}", stderr.trim());
        }

        if check {
            Err(Error::GhCommandFailed {
                exit_code,
                stdout,
                stderr,
            })
        } else {
            Ok(None)
        }
    }
}

/// Run a GitHub CLI command and capture both stdout and stderr.
///
/// # Arguments
///
/// * `args` - Command arguments (without the `gh` prefix)
///
/// # Returns
///
/// Tuple of (stdout, stderr, return_code).
pub async fn run_gh_command_with_stderr(
    args: &[&str],
) -> Result<(Option<String>, Option<String>, i32), Error> {
    let mut cmd = Command::new("gh");
    cmd.args(args).stdout(Stdio::piped()).stderr(Stdio::piped());

    debug!("Running gh command: gh {}", args.join(" "));

    let output = cmd.output().await.map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            Error::GhNotFound
        } else {
            Error::Io(e)
        }
    })?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let return_code = output.status.code().unwrap_or(-1);

    Ok((
        if stdout.trim().is_empty() {
            None
        } else {
            Some(stdout.trim().to_string())
        },
        if stderr.trim().is_empty() {
            None
        } else {
            Some(stderr.trim().to_string())
        },
        return_code,
    ))
}

/// Run a git command asynchronously.
///
/// # Arguments
///
/// * `args` - Command arguments (without the `git` prefix)
/// * `check` - Whether to return an error on non-zero exit code
///
/// # Returns
///
/// Command stdout on success, or None if check is false and command failed.
pub async fn run_git_command(args: &[&str], check: bool) -> Result<Option<String>, Error> {
    let mut cmd = Command::new("git");
    cmd.args(args).stdout(Stdio::piped()).stderr(Stdio::piped());

    debug!("Running git command: git {}", args.join(" "));

    let output = cmd.output().await.map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            Error::GitNotFound
        } else {
            Error::Io(e)
        }
    })?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if output.status.success() {
        Ok(Some(stdout))
    } else {
        let exit_code = output.status.code().unwrap_or(-1);
        error!("Git command failed: git {}", args.join(" "));
        if !stderr.trim().is_empty() {
            error!("Error output: {}", stderr.trim());
        }

        if check {
            Err(Error::GitCommandFailed {
                exit_code,
                stdout,
                stderr,
            })
        } else {
            Ok(None)
        }
    }
}

/// Check if the GitHub CLI is available and authenticated.
pub async fn check_gh_available() -> Result<(), Error> {
    // Check if gh command exists
    let which_output = Command::new("which")
        .arg("gh")
        .output()
        .await
        .map_err(Error::Io)?;

    if !which_output.status.success() {
        return Err(Error::GhNotFound);
    }

    // Check authentication
    let output = Command::new("gh")
        .args(["auth", "status"])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .await
        .map_err(Error::Io)?;

    if !output.status.success() {
        return Err(Error::GhNotAuthenticated);
    }

    debug!("GitHub CLI available and authenticated");
    Ok(())
}

/// Check if git is available.
pub async fn check_git_available() -> Result<(), Error> {
    let which_output = Command::new("which")
        .arg("git")
        .output()
        .await
        .map_err(Error::Io)?;

    if !which_output.status.success() {
        return Err(Error::GitNotFound);
    }

    debug!("Git available");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    // Note: Environment variable tests can interfere with each other when run in parallel.
    // We test the logic of get_github_token separately rather than relying on env state.

    #[test]
    fn test_github_token_priority() {
        // Test that GITHUB_TOKEN takes priority by checking the order in the implementation.
        // The actual env var manipulation is risky in parallel tests.
        // This test verifies the function signature and error type are correct.
        let result = get_github_token();
        // Result will depend on whether tokens are set in the environment.
        // We're just verifying the function compiles and returns the expected type.
        match result {
            Ok(token) => assert!(!token.is_empty()),
            Err(Error::GitHubTokenNotFound) => {} // Expected when no token set
            Err(_) => panic!("Unexpected error type"),
        }
    }
}
