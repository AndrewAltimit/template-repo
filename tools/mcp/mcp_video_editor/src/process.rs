//! Subprocess execution helpers with a wall-clock timeout.
//!
//! All media work shells out to external tools (ffmpeg, ffprobe, whisper). Those
//! can hang indefinitely on a malformed input or a stuck device, which would
//! pin the worker task forever. Routing every invocation through
//! [`output_with_timeout`] bounds the runtime and guarantees the child process
//! is killed (via `kill_on_drop`) if it overruns *or* if the calling future is
//! dropped (which is how job cancellation stops a running ffmpeg).
//!
//! Commands are always spawned directly (never through a shell), with stdin
//! connected to the null device so a child can never consume the MCP STDIO
//! transport's input.

use std::process::{Output, Stdio};
use std::sync::OnceLock;
use std::time::Duration;

use anyhow::{Context, Result};
use tokio::process::Command;
use tracing::warn;

/// Default timeout for a media subprocess call. Generous because renders and
/// transcriptions are legitimately slow; override with
/// `VIDEO_EDITOR_SUBPROCESS_TIMEOUT_SECS`.
const DEFAULT_TIMEOUT_SECS: u64 = 1800;

/// Maximum number of trailing stderr lines included in error messages.
const STDERR_TAIL_LINES: usize = 15;

/// Resolve the configured subprocess timeout.
///
/// Read from the environment once and cached for the process lifetime, so we
/// neither re-parse on every invocation nor race a concurrent `set_var` on the
/// global environment.
fn subprocess_timeout() -> Duration {
    static TIMEOUT: OnceLock<Duration> = OnceLock::new();
    *TIMEOUT.get_or_init(|| {
        Duration::from_secs(
            std::env::var("VIDEO_EDITOR_SUBPROCESS_TIMEOUT_SECS")
                .ok()
                .and_then(|v| v.parse().ok())
                .filter(|&secs| secs > 0)
                .unwrap_or(DEFAULT_TIMEOUT_SECS),
        )
    })
}

/// Run a command to completion, killing it if it exceeds the timeout.
///
/// `what` is a short human-readable label for the command, used in error
/// messages (e.g. `"ffmpeg for scene detection"`). stdout and stderr are
/// captured; stdin is null.
pub async fn output_with_timeout(cmd: &mut Command, what: &str) -> Result<Output> {
    // If the timeout future is dropped, the child is killed rather than orphaned.
    cmd.kill_on_drop(true)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let timeout = subprocess_timeout();

    match tokio::time::timeout(timeout, cmd.output()).await {
        Ok(Ok(output)) => Ok(output),
        Ok(Err(e)) if e.kind() == std::io::ErrorKind::NotFound => {
            Err(e).with_context(|| format!("Failed to run {what}: executable not found in PATH"))
        },
        Ok(Err(e)) => Err(e).with_context(|| format!("Failed to run {what}")),
        Err(_elapsed) => {
            warn!(
                "{} timed out after {}s; process killed",
                what,
                timeout.as_secs()
            );
            anyhow::bail!(
                "{what} timed out after {}s (raise VIDEO_EDITOR_SUBPROCESS_TIMEOUT_SECS for long media)",
                timeout.as_secs()
            )
        },
    }
}

/// Run a command and turn a non-zero exit status into an error that carries
/// the tail of stderr.
pub async fn run_checked(cmd: &mut Command, what: &str) -> Result<Output> {
    let output = output_with_timeout(cmd, what).await?;
    if !output.status.success() {
        anyhow::bail!(
            "{what} failed ({}): {}",
            output.status,
            stderr_tail(&output.stderr)
        );
    }
    Ok(output)
}

/// Last few non-empty lines of a process's stderr, for error messages.
pub fn stderr_tail(stderr: &[u8]) -> String {
    let text = String::from_utf8_lossy(stderr);
    let lines: Vec<&str> = text
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .collect();
    let start = lines.len().saturating_sub(STDERR_TAIL_LINES);
    let tail = lines[start..].join("\n");
    if tail.is_empty() {
        "(no error output)".to_string()
    } else {
        tail
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stderr_tail_keeps_last_lines() {
        let input: String = (0..40).map(|i| format!("line {i}\n")).collect();
        let tail = stderr_tail(input.as_bytes());
        assert!(tail.starts_with("line 25"));
        assert!(tail.ends_with("line 39"));
    }

    #[test]
    fn stderr_tail_empty() {
        assert_eq!(stderr_tail(b"\n  \n"), "(no error output)");
    }

    #[tokio::test]
    async fn missing_executable_reports_not_found() {
        let err = output_with_timeout(
            &mut Command::new("definitely-not-a-real-binary-xyz"),
            "fake",
        )
        .await
        .unwrap_err();
        assert!(format!("{err:#}").contains("not found"));
    }
}
