//! Subprocess execution with timeouts, bounded output capture, and
//! process-tree cleanup.
//!
//! Every external tool (pdflatex, pdftoppm, manim, ...) goes through [`run`],
//! which guarantees that:
//! - stdin is closed, so a tool that tries to prompt fails instead of hanging;
//! - the process is killed when it exceeds its deadline (on Unix the whole
//!   process group is killed, so grandchildren such as ffmpeg die too);
//! - only the last [`OUTPUT_CAP_BYTES`] of stdout/stderr are kept in memory,
//!   so a runaway `\typeout` loop cannot exhaust the server's memory.

use std::fmt;
use std::process::{ExitStatus, Stdio};
use std::time::Duration;

use tokio::io::{AsyncRead, AsyncReadExt};
use tokio::process::Command;

/// Maximum bytes of stdout/stderr retained per stream (the tail is kept).
pub const OUTPUT_CAP_BYTES: usize = 64 * 1024;

/// How long to wait for output pipes to drain after the process exits.
const PIPE_DRAIN_TIMEOUT: Duration = Duration::from_secs(5);

/// Captured result of a finished process.
#[derive(Debug)]
pub struct CmdOutput {
    pub status: ExitStatus,
    pub stdout: String,
    pub stderr: String,
}

impl CmdOutput {
    /// The last `max_lines` non-empty lines of stderr (falling back to stdout
    /// when stderr is empty), for use in error messages.
    pub fn diagnostic_tail(&self, max_lines: usize) -> String {
        let source = if self.stderr.trim().is_empty() {
            &self.stdout
        } else {
            &self.stderr
        };
        tail_lines(source, max_lines)
    }
}

/// Why a process could not be run to completion.
#[derive(Debug)]
pub enum CmdError {
    /// The executable does not exist on `PATH`.
    NotFound { program: String },
    /// The process exceeded its deadline and was killed.
    Timeout { program: String, secs: u64 },
    /// Any other spawn/wait failure.
    Io {
        program: String,
        source: std::io::Error,
    },
}

impl fmt::Display for CmdError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CmdError::NotFound { program } => write!(
                f,
                "'{}' was not found on PATH ({})",
                program,
                install_hint(program)
            ),
            CmdError::Timeout { program, secs } => write!(
                f,
                "'{}' timed out after {}s and was killed (infinite loop or very large job?)",
                program, secs
            ),
            CmdError::Io { program, source } => {
                write!(f, "failed to run '{}': {}", program, source)
            },
        }
    }
}

impl std::error::Error for CmdError {}

/// Suggest which package provides a missing tool.
pub fn install_hint(program: &str) -> &'static str {
    let name = std::path::Path::new(program)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(program);
    match name {
        "pdflatex" | "latex" => "install texlive-latex-base",
        "dvips" | "bibtex" => "install texlive-binaries",
        "pdfinfo" | "pdftoppm" => "install poppler-utils",
        "pdf2svg" => "install pdf2svg",
        "manim" => "pip install manim",
        _ => "install it or use the mcp-content-creation Docker image",
    }
}

/// Run `cmd` to completion with a deadline.
///
/// `program` is only used for error messages. The command's stdin, stdout, and
/// stderr are overridden by this function.
pub async fn run(
    mut cmd: Command,
    program: &str,
    timeout: Duration,
) -> Result<CmdOutput, CmdError> {
    cmd.stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    #[cfg(unix)]
    cmd.process_group(0);

    let mut child = cmd.spawn().map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            CmdError::NotFound {
                program: program.to_string(),
            }
        } else {
            CmdError::Io {
                program: program.to_string(),
                source: e,
            }
        }
    })?;

    let pid = child.id();
    let stdout_task = child.stdout.take().map(|s| tokio::spawn(read_tail(s)));
    let stderr_task = child.stderr.take().map(|s| tokio::spawn(read_tail(s)));

    let status = match tokio::time::timeout(timeout, child.wait()).await {
        Ok(Ok(status)) => status,
        Ok(Err(e)) => {
            kill_tree(pid);
            return Err(CmdError::Io {
                program: program.to_string(),
                source: e,
            });
        },
        Err(_) => {
            kill_tree(pid);
            let _ = child.kill().await;
            if let Some(t) = stdout_task {
                t.abort();
            }
            if let Some(t) = stderr_task {
                t.abort();
            }
            return Err(CmdError::Timeout {
                program: program.to_string(),
                secs: timeout.as_secs(),
            });
        },
    };

    // A grandchild that inherited the pipes could keep them open after the
    // main process exits; `collect` bounds how long we wait for EOF.
    Ok(CmdOutput {
        status,
        stdout: collect(stdout_task).await,
        stderr: collect(stderr_task).await,
    })
}

async fn collect(task: Option<tokio::task::JoinHandle<Vec<u8>>>) -> String {
    let Some(task) = task else {
        return String::new();
    };
    match tokio::time::timeout(PIPE_DRAIN_TIMEOUT, task).await {
        Ok(Ok(bytes)) => String::from_utf8_lossy(&bytes).into_owned(),
        _ => String::new(),
    }
}

/// Read a stream to EOF, keeping only the last [`OUTPUT_CAP_BYTES`].
async fn read_tail<R: AsyncRead + Unpin>(mut reader: R) -> Vec<u8> {
    let mut kept: Vec<u8> = Vec::new();
    let mut buf = vec![0u8; 8192];
    loop {
        match reader.read(&mut buf).await {
            Ok(0) | Err(_) => break,
            Ok(n) => {
                kept.extend_from_slice(&buf[..n]);
                if kept.len() > OUTPUT_CAP_BYTES * 2 {
                    let excess = kept.len() - OUTPUT_CAP_BYTES;
                    kept.drain(..excess);
                }
            },
        }
    }
    if kept.len() > OUTPUT_CAP_BYTES {
        let excess = kept.len() - OUTPUT_CAP_BYTES;
        kept.drain(..excess);
    }
    kept
}

/// Kill the process group led by `pid` (Unix only; no-op elsewhere).
#[cfg(unix)]
fn kill_tree(pid: Option<u32>) {
    if let Some(pid) = pid.and_then(|p| i32::try_from(p).ok()).filter(|p| *p > 0) {
        // SAFETY: kill(2) has no memory-safety preconditions. The child was
        // spawned with process_group(0), so -pid addresses only its group.
        unsafe {
            libc::kill(-pid, libc::SIGKILL);
        }
    }
}

#[cfg(not(unix))]
fn kill_tree(_pid: Option<u32>) {}

/// Last `max_lines` non-empty lines of `text`, joined with newlines.
pub fn tail_lines(text: &str, max_lines: usize) -> String {
    let lines: Vec<&str> = text.lines().filter(|l| !l.trim().is_empty()).collect();
    let start = lines.len().saturating_sub(max_lines);
    lines[start..].join("\n")
}

/// Truncate `text` to at most `max_chars` characters, appending a marker.
pub fn truncate_chars(text: &str, max_chars: usize) -> String {
    match text.char_indices().nth(max_chars) {
        Some((idx, _)) => format!("{}... [truncated]", &text[..idx]),
        None => text.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn missing_binary_reports_not_found_with_hint() {
        let cmd = Command::new("definitely-not-a-real-binary-mcp-xyz");
        let err = run(cmd, "pdflatex", Duration::from_secs(5))
            .await
            .unwrap_err();
        assert!(matches!(err, CmdError::NotFound { .. }));
        assert!(err.to_string().contains("texlive"), "{err}");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn slow_process_is_killed_on_timeout() {
        let mut cmd = Command::new("sh");
        cmd.args(["-c", "sleep 30"]);
        let start = std::time::Instant::now();
        let err = run(cmd, "sh", Duration::from_millis(300))
            .await
            .unwrap_err();
        assert!(matches!(err, CmdError::Timeout { .. }));
        assert!(start.elapsed() < Duration::from_secs(10));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn output_is_captured_and_capped() {
        let mut cmd = Command::new("sh");
        cmd.args([
            "-c",
            "head -c 300000 /dev/zero | tr '\\0' 'a'; echo tail-marker",
        ]);
        let out = run(cmd, "sh", Duration::from_secs(10)).await.unwrap();
        assert!(out.status.success());
        assert!(out.stdout.len() <= OUTPUT_CAP_BYTES);
        assert!(out.stdout.trim_end().ends_with("tail-marker"));
    }

    #[test]
    fn tail_lines_skips_blank_lines() {
        assert_eq!(tail_lines("a\n\nb\nc\n\n", 2), "b\nc");
        assert_eq!(tail_lines("", 3), "");
    }

    #[test]
    fn truncate_chars_is_utf8_safe() {
        assert_eq!(truncate_chars("abc", 5), "abc");
        assert_eq!(
            truncate_chars("\u{00e9}\u{00e9}\u{00e9}", 2),
            "\u{00e9}\u{00e9}... [truncated]"
        );
    }

    #[test]
    fn install_hint_ignores_directories() {
        assert_eq!(install_hint("/usr/bin/pdftoppm"), "install poppler-utils");
    }
}
