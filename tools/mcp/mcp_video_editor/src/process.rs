//! Subprocess execution helpers with a wall-clock timeout.
//!
//! All media work shells out to external tools (ffmpeg, ffprobe, whisper). Those
//! can hang indefinitely on a malformed input or a stuck device, which would
//! pin the worker task forever. Routing every invocation through
//! [`output_with_timeout`] bounds the runtime and guarantees the child process
//! is killed (via `kill_on_drop`) if it overruns.

use std::process::Output;
use std::time::Duration;

use anyhow::{Context, Result};
use tokio::process::Command;
use tracing::warn;

/// Default timeout for a media subprocess call. Generous because renders and
/// transcriptions are legitimately slow; override with
/// `VIDEO_EDITOR_SUBPROCESS_TIMEOUT_SECS`.
const DEFAULT_TIMEOUT_SECS: u64 = 1800;

/// Resolve the configured subprocess timeout.
fn subprocess_timeout() -> Duration {
    Duration::from_secs(
        std::env::var("VIDEO_EDITOR_SUBPROCESS_TIMEOUT_SECS")
            .ok()
            .and_then(|v| v.parse().ok())
            .filter(|&secs| secs > 0)
            .unwrap_or(DEFAULT_TIMEOUT_SECS),
    )
}

/// Run a command to completion, killing it if it exceeds the timeout.
///
/// `what` is a short human-readable label for the command, used in error
/// messages (e.g. `"ffmpeg for scene detection"`).
pub async fn output_with_timeout(cmd: &mut Command, what: &str) -> Result<Output> {
    // If the timeout future is dropped, the child is killed rather than orphaned.
    cmd.kill_on_drop(true);
    let timeout = subprocess_timeout();

    match tokio::time::timeout(timeout, cmd.output()).await {
        Ok(Ok(output)) => Ok(output),
        Ok(Err(e)) => Err(e).with_context(|| format!("Failed to run {what}")),
        Err(_elapsed) => {
            warn!(
                "{} timed out after {}s; process killed",
                what,
                timeout.as_secs()
            );
            anyhow::bail!("{what} timed out after {}s", timeout.as_secs())
        },
    }
}
