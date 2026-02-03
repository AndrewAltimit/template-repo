//! Platform-specific binary execution
//!
//! On Unix, uses exec() to replace the current process entirely.
//! On Windows, uses spawn() and exits with the child's exit code.

use crate::error::CommonError;
use std::path::Path;
use std::process::Command;

/// Execute a binary, replacing the current process on Unix.
///
/// This function does not return on success (the process is replaced).
/// On error, returns `CommonError::ExecFailed`.
///
/// # Arguments
/// * `binary_name` - Human-readable name for error messages (e.g., "git")
/// * `binary_path` - Path to the binary to execute
/// * `args` - Arguments to pass to the binary
#[cfg(unix)]
pub fn exec_binary(
    binary_name: &str,
    binary_path: &Path,
    args: &[String],
) -> Result<(), CommonError> {
    use std::os::unix::process::CommandExt;

    let err = Command::new(binary_path).args(args).exec();

    // exec() only returns on error
    Err(CommonError::ExecFailed {
        binary_name: binary_name.to_string(),
        source: err,
    })
}

/// Execute a binary via spawn on Windows (no exec() equivalent).
#[cfg(windows)]
pub fn exec_binary(
    binary_name: &str,
    binary_path: &Path,
    args: &[String],
) -> Result<(), CommonError> {
    let status =
        Command::new(binary_path)
            .args(args)
            .status()
            .map_err(|e| CommonError::ExecFailed {
                binary_name: binary_name.to_string(),
                source: e,
            })?;

    std::process::exit(status.code().unwrap_or(1));
}

/// Spawn a binary as a child process (does NOT replace current process).
///
/// Returns the child's exit status. Use this when you need to do work
/// after the child completes (e.g., post-command logging, PR monitoring).
///
/// # Arguments
/// * `binary_name` - Human-readable name for error messages
/// * `binary_path` - Path to the binary to execute
/// * `args` - Arguments to pass to the binary
pub fn spawn_binary(
    binary_name: &str,
    binary_path: &Path,
    args: &[String],
) -> Result<std::process::ExitStatus, CommonError> {
    use std::process::Stdio;

    Command::new(binary_path)
        .args(args)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .stdin(Stdio::inherit())
        .status()
        .map_err(|e| CommonError::ExecFailed {
            binary_name: binary_name.to_string(),
            source: e,
        })
}
