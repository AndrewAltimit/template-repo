//! Subprocess execution boundary.
//!
//! [`CommandRunner`] is the seam between the Crush backend and the operating
//! system, so tests can substitute a fake runner and never spawn processes.
//! [`TokioRunner`] is the real implementation: prompt via stdin (no argv
//! length limits, prompt not visible in `ps`), bounded output capture, and
//! a hard timeout that kills the child.

use std::fmt;
use std::io::ErrorKind;
use std::path::PathBuf;
use std::process::Stdio;
use std::time::Duration;

use async_trait::async_trait;
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWriteExt};
use tokio::process::Command;

/// Maximum captured stderr bytes (errors only need the tail).
const MAX_STDERR_BYTES: usize = 64 * 1024;

/// A fully specified command invocation.
#[derive(Clone, Default)]
pub struct CommandSpec {
    /// Program name or path.
    pub program: String,
    /// Arguments (never contain secrets).
    pub args: Vec<String>,
    /// Environment variables to set (values may be secret; never logged).
    pub env: Vec<(String, String)>,
    /// Environment variables to remove from the inherited environment.
    pub env_remove: Vec<String>,
    /// Working directory.
    pub cwd: Option<PathBuf>,
    /// Data written to stdin (then stdin is closed).
    pub stdin: String,
    /// Hard deadline; the child is killed when it elapses.
    pub timeout: Duration,
    /// Maximum captured stdout bytes; the rest is drained and discarded.
    pub max_output_bytes: usize,
}

impl fmt::Debug for CommandSpec {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Deliberately omits env values and stdin (may contain secrets/prompts).
        f.debug_struct("CommandSpec")
            .field("program", &self.program)
            .field("args", &self.args)
            .field(
                "env_keys",
                &self.env.iter().map(|(k, _)| k).collect::<Vec<_>>(),
            )
            .field("env_remove", &self.env_remove)
            .field("cwd", &self.cwd)
            .field("stdin_bytes", &self.stdin.len())
            .field("timeout", &self.timeout)
            .finish()
    }
}

/// Result of running a command.
#[derive(Debug, Clone, PartialEq)]
pub enum RunResult {
    /// The process exited (successfully or not).
    Completed {
        /// Whether the exit status was success.
        success: bool,
        /// Exit code, if the process was not killed by a signal.
        code: Option<i32>,
        /// Captured stdout (lossy UTF-8, possibly truncated).
        stdout: String,
        /// Captured stderr (lossy UTF-8, possibly truncated).
        stderr: String,
        /// Whether stdout exceeded `max_output_bytes`.
        stdout_truncated: bool,
    },
    /// The process could not be started.
    SpawnFailed {
        /// OS error kind (`NotFound` means the executable is missing).
        kind: ErrorKind,
        /// OS error message.
        message: String,
    },
    /// The deadline elapsed; the process was killed.
    TimedOut,
    /// Waiting on the process failed.
    Failed(String),
}

/// Executes [`CommandSpec`]s.
#[async_trait]
pub trait CommandRunner: Send + Sync + 'static {
    /// Run the command to completion (or timeout).
    async fn run(&self, spec: CommandSpec) -> RunResult;
}

/// Real runner backed by `tokio::process`.
#[derive(Debug, Default, Clone, Copy)]
pub struct TokioRunner;

/// Read a stream to EOF, keeping at most `cap` bytes. Continues draining past
/// the cap so the child never blocks on a full pipe.
async fn read_capped<R: AsyncRead + Unpin>(reader: Option<R>, cap: usize) -> (Vec<u8>, bool) {
    let Some(mut reader) = reader else {
        return (Vec::new(), false);
    };
    let mut kept = Vec::new();
    let mut truncated = false;
    let mut buf = [0u8; 8192];
    loop {
        match reader.read(&mut buf).await {
            Ok(0) | Err(_) => break,
            Ok(n) => {
                let room = cap.saturating_sub(kept.len());
                if n > room {
                    truncated = true;
                }
                kept.extend_from_slice(&buf[..n.min(room)]);
            },
        }
    }
    (kept, truncated)
}

#[async_trait]
impl CommandRunner for TokioRunner {
    async fn run(&self, spec: CommandSpec) -> RunResult {
        let mut cmd = Command::new(&spec.program);
        cmd.args(&spec.args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            // Dropping the child (e.g. on timeout or cancellation) kills it
            // instead of leaking an orphaned process.
            .kill_on_drop(true);
        for key in &spec.env_remove {
            cmd.env_remove(key);
        }
        for (key, value) in &spec.env {
            cmd.env(key, value);
        }
        if let Some(cwd) = &spec.cwd {
            cmd.current_dir(cwd);
        }

        let mut child = match cmd.spawn() {
            Ok(child) => child,
            Err(e) => {
                return RunResult::SpawnFailed {
                    kind: e.kind(),
                    message: e.to_string(),
                };
            },
        };

        let stdin = child.stdin.take();
        let stdout = child.stdout.take();
        let stderr = child.stderr.take();
        let input = spec.stdin;

        let outcome = {
            let work = async {
                let writer = async move {
                    if let Some(mut pipe) = stdin {
                        // A broken pipe just means the child exited early.
                        let _ = pipe.write_all(input.as_bytes()).await;
                        let _ = pipe.shutdown().await;
                    }
                };
                let (_, (out, out_truncated), (err, _), status) = tokio::join!(
                    writer,
                    read_capped(stdout, spec.max_output_bytes),
                    read_capped(stderr, MAX_STDERR_BYTES),
                    child.wait()
                );
                match status {
                    Ok(status) => RunResult::Completed {
                        success: status.success(),
                        code: status.code(),
                        stdout: String::from_utf8_lossy(&out).into_owned(),
                        stderr: String::from_utf8_lossy(&err).into_owned(),
                        stdout_truncated: out_truncated,
                    },
                    Err(e) => RunResult::Failed(format!("Failed to wait for process: {e}")),
                }
            };
            tokio::time::timeout(spec.timeout, work).await
        };

        match outcome {
            Ok(result) => result,
            Err(_) => {
                let _ = child.kill().await;
                RunResult::TimedOut
            },
        }
    }
}

/// Locate an executable the way a shell would, without spawning `which`.
///
/// Names containing a path separator are checked directly. On Windows the
/// `PATHEXT` extensions are tried as well.
pub fn find_executable(name: &str) -> Option<PathBuf> {
    let candidate = PathBuf::from(name);
    if candidate.components().count() > 1 || candidate.is_absolute() {
        return candidate.is_file().then_some(candidate);
    }
    let path = std::env::var_os("PATH")?;
    let extensions: Vec<String> = if cfg!(windows) {
        let pathext = std::env::var("PATHEXT").unwrap_or_else(|_| ".EXE;.CMD;.BAT;.COM".into());
        std::iter::once(String::new())
            .chain(
                pathext
                    .split(';')
                    .filter(|e| !e.is_empty())
                    .map(str::to_string),
            )
            .collect()
    } else {
        vec![String::new()]
    };
    std::env::split_paths(&path).find_map(|dir| {
        extensions.iter().find_map(|ext| {
            let full = dir.join(format!("{name}{ext}"));
            full.is_file().then_some(full)
        })
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn read_capped_truncates_but_drains() {
        let data = vec![b'x'; 20_000];
        let (kept, truncated) = read_capped(Some(&data[..]), 100).await;
        assert_eq!(kept.len(), 100);
        assert!(truncated);

        let (kept, truncated) = read_capped(Some(&b"short"[..]), 100).await;
        assert_eq!(kept, b"short");
        assert!(!truncated);

        let (kept, truncated) = read_capped(None::<&[u8]>, 100).await;
        assert!(kept.is_empty() && !truncated);
    }

    #[tokio::test]
    async fn missing_executable_reports_not_found() {
        let result = TokioRunner
            .run(CommandSpec {
                program: "definitely-not-a-real-binary-mcp-crush".into(),
                timeout: Duration::from_secs(5),
                max_output_bytes: 1024,
                ..Default::default()
            })
            .await;
        match result {
            RunResult::SpawnFailed { kind, .. } => assert_eq!(kind, ErrorKind::NotFound),
            other => panic!("expected SpawnFailed, got {other:?}"),
        }
    }

    #[tokio::test]
    async fn real_process_output_is_captured() {
        // `rustc` is always present where these tests run (cargo test).
        let Some(rustc) = find_executable("rustc") else {
            return;
        };
        let result = TokioRunner
            .run(CommandSpec {
                program: rustc.to_string_lossy().into_owned(),
                args: vec!["--version".into()],
                stdin: "ignored".into(),
                timeout: Duration::from_secs(30),
                max_output_bytes: 1024,
                ..Default::default()
            })
            .await;
        match result {
            RunResult::Completed {
                success, stdout, ..
            } => {
                assert!(success);
                assert!(stdout.starts_with("rustc "), "{stdout}");
            },
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn debug_hides_env_values_and_stdin() {
        let spec = CommandSpec {
            program: "crush".into(),
            env: vec![("OPENROUTER_API_KEY".into(), "sk-or-v1-secret".into())],
            stdin: "private prompt".into(),
            ..Default::default()
        };
        let dbg = format!("{spec:?}");
        assert!(dbg.contains("OPENROUTER_API_KEY"));
        assert!(!dbg.contains("sk-or-v1-secret"));
        assert!(!dbg.contains("private prompt"));
    }

    #[test]
    fn find_executable_handles_missing_and_paths() {
        assert!(find_executable("definitely-not-a-real-binary-mcp-crush").is_none());
        assert!(find_executable("/definitely/not/here/crush").is_none());
        // The test binary itself is a real file reachable by absolute path.
        let me = std::env::current_exe().unwrap();
        assert_eq!(find_executable(me.to_str().unwrap()), Some(me));
    }
}
