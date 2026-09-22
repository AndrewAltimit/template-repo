//! Headless Blender process management.
//!
//! One tool call = one `blender --background` process running one of the
//! Python scripts in `scripts/`. The contract with those scripts (see
//! `scripts/mcp_common.py`):
//!
//! * arguments go through a JSON file: `-- <args.json> <job_id>` (never
//!   inline on the command line, so there is no size limit and nothing is
//!   interpolated into Python source -- tool arguments are pure data);
//! * the script prints exactly one `MCP_RESULT:{json}` line and exits 0 on
//!   success / 1 on failure (`--python-exit-code 1` also turns uncaught
//!   exceptions into exit code 1);
//! * long operations write progress to `$BLENDER_MCP_JOBS_DIR/<job_id>.status`.
//!
//! Every process has a wall-clock timeout and can be cancelled; in both cases
//! the child is killed. Output is captured incrementally with a bounded tail
//! so a chatty render cannot exhaust memory.

use crate::config::Config;
use crate::jobs::CancelSignal;
use serde_json::Value;
use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::Arc;
use std::time::Duration;
use tokio::io::{AsyncBufReadExt, AsyncRead, BufReader};
use tokio::process::Command;
use tokio::sync::{Mutex, OwnedSemaphorePermit, Semaphore};
use tracing::{debug, info, warn};
use uuid::Uuid;

/// Prefix of the single machine-readable result line printed by scripts.
pub const RESULT_MARKER: &str = "MCP_RESULT:";
/// Lines of stdout/stderr kept for error reporting.
const TAIL_LINES: usize = 200;
/// Longest line kept in the tail (longer lines are truncated).
const MAX_LINE_LEN: usize = 2000;
/// How many tail lines are included in error messages.
const ERROR_TAIL_LINES: usize = 15;
/// Timeout for `blender --version` probes.
const VERSION_PROBE_TIMEOUT: Duration = Duration::from_secs(30);
/// Status-file poll interval for progress reporting.
const PROGRESS_POLL: Duration = Duration::from_secs(1);

/// Failure modes of a Blender invocation.
#[derive(Debug, Clone, thiserror::Error)]
pub enum ExecError {
    /// No usable Blender executable.
    #[error("{0}")]
    BlenderNotFound(String),
    /// The requested script is missing from the scripts directory.
    #[error("Blender script '{0}' not found in {1}")]
    ScriptMissing(String, String),
    /// Local I/O problem (temp files, spawning).
    #[error("{0}")]
    Io(String),
    /// Wall-clock timeout; the process was killed.
    #[error(
        "Blender did not finish within {0}s and was killed (raise BLENDER_JOB_TIMEOUT_SECS / BLENDER_RENDER_TIMEOUT_SECS for long operations)"
    )]
    Timeout(u64),
    /// Cancelled through the job's cancellation signal; the process was killed.
    #[error("cancelled")]
    Cancelled,
    /// The script ran and reported (or implied) failure.
    #[error("{message}")]
    Failed {
        /// Human-readable reason, taken from the script's result when present.
        message: String,
        /// Last lines of Blender's output for diagnosis.
        log_tail: Vec<String>,
    },
}

/// A located, verified Blender executable.
#[derive(Debug, Clone)]
pub struct BlenderInfo {
    /// Executable path.
    pub path: PathBuf,
    /// First line of `blender --version`.
    pub version: String,
}

/// Which concurrency pool an invocation draws from.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Slot {
    /// Quick scene edits (`MAX_CONCURRENT_OPERATIONS`).
    Operation,
    /// Long renders/bakes (`MAX_CONCURRENT_JOBS`).
    Job,
}

/// Progress callback: `(percent, message)`.
pub type ProgressFn<'a> = &'a (dyn Fn(u8, &str) + Send + Sync);

/// One script invocation.
pub struct Invocation<'a> {
    /// Script file name inside the scripts directory.
    pub script: &'a str,
    /// Arguments (serialized to the args file).
    pub args: &'a Value,
    /// Id used for the args/status files (the job id for async jobs).
    pub id: Uuid,
    /// Wall-clock limit.
    pub timeout: Duration,
    /// Optional cancellation signal.
    pub cancel: Option<CancelSignal>,
    /// Optional progress sink fed from the status file.
    pub progress: Option<ProgressFn<'a>>,
}

/// Runs Blender scripts; cheap to clone (all state is shared).
#[derive(Clone)]
pub struct BlenderExecutor {
    config: Arc<Config>,
    blender: Arc<Mutex<Option<BlenderInfo>>>,
    job_slots: Arc<Semaphore>,
    operation_slots: Arc<Semaphore>,
}

impl BlenderExecutor {
    /// Executor using `config` for paths, limits and the Blender location.
    pub fn new(config: Arc<Config>) -> Self {
        Self {
            job_slots: Arc::new(Semaphore::new(config.max_concurrent_jobs)),
            operation_slots: Arc::new(Semaphore::new(config.max_concurrent_operations)),
            blender: Arc::new(Mutex::new(None)),
            config,
        }
    }

    /// Free slots in `(job, operation)` pools.
    pub fn available_slots(&self) -> (usize, usize) {
        (
            self.job_slots.available_permits(),
            self.operation_slots.available_permits(),
        )
    }

    /// Wait for a free slot in the given pool.
    pub async fn acquire(&self, slot: Slot) -> Result<OwnedSemaphorePermit, ExecError> {
        let semaphore = match slot {
            Slot::Job => self.job_slots.clone(),
            Slot::Operation => self.operation_slots.clone(),
        };
        semaphore
            .acquire_owned()
            .await
            .map_err(|_| ExecError::Io("executor is shutting down".to_string()))
    }

    /// Locate and verify Blender (cached after the first success).
    pub async fn blender(&self) -> Result<BlenderInfo, ExecError> {
        let mut cached = self.blender.lock().await;
        if let Some(info) = cached.as_ref() {
            return Ok(info.clone());
        }
        let info = locate_blender(self.config.blender_path.as_deref()).await?;
        info!(
            "Using Blender at {} ({})",
            info.path.display(),
            info.version
        );
        *cached = Some(info.clone());
        Ok(info)
    }

    /// Run one script to completion (or timeout/cancellation).
    ///
    /// The caller is responsible for holding a slot permit from
    /// [`acquire`](Self::acquire) and any project lock.
    pub async fn run(&self, inv: Invocation<'_>) -> Result<Value, ExecError> {
        let blender = self.blender().await?;
        let script_path = self.config.scripts_dir.join(inv.script);
        if !script_path.is_file() {
            return Err(ExecError::ScriptMissing(
                inv.script.to_string(),
                self.config.scripts_dir.display().to_string(),
            ));
        }

        let jobs_dir = self.config.jobs_dir();
        for dir in [&self.config.temp_dir, &jobs_dir] {
            tokio::fs::create_dir_all(dir)
                .await
                .map_err(|e| ExecError::Io(format!("cannot create {}: {}", dir.display(), e)))?;
        }
        let args_file = TempFile(self.config.temp_dir.join(format!("{}.json", inv.id)));
        let status_file = TempFile(jobs_dir.join(format!("{}.status", inv.id)));
        let payload = serde_json::to_vec(inv.args)
            .map_err(|e| ExecError::Io(format!("cannot serialize script arguments: {e}")))?;
        tokio::fs::write(&args_file.0, payload)
            .await
            .map_err(|e| ExecError::Io(format!("cannot write {}: {}", args_file.0.display(), e)))?;

        let mut cmd = Command::new(&blender.path);
        cmd.arg("--background")
            .arg("--factory-startup")
            .arg("-noaudio")
            .arg("--python-exit-code")
            .arg("1")
            .arg("--python")
            .arg(&script_path)
            .arg("--")
            .arg(&args_file.0)
            .arg(inv.id.to_string())
            .env("BLENDER_MCP_JOBS_DIR", &jobs_dir)
            // Never let Blender read the MCP stdio stream or write to our stdout.
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        debug!("Running {} for {}", inv.script, inv.id);
        let mut child = cmd
            .spawn()
            .map_err(|e| ExecError::Io(format!("failed to start Blender: {e}")))?;
        let stdout_task = child.stdout.take().map(|s| tokio::spawn(capture(s)));
        let stderr_task = child.stderr.take().map(|s| tokio::spawn(capture(s)));

        let mut cancel = inv.cancel;
        let deadline = tokio::time::sleep(inv.timeout);
        tokio::pin!(deadline);
        let mut ticker = tokio::time::interval(PROGRESS_POLL);

        enum Outcome {
            Exited(std::io::Result<std::process::ExitStatus>),
            TimedOut,
            Cancelled,
        }
        let outcome = loop {
            tokio::select! {
                status = child.wait() => break Outcome::Exited(status),
                _ = &mut deadline => break Outcome::TimedOut,
                _ = wait_cancelled(&mut cancel) => break Outcome::Cancelled,
                _ = ticker.tick(), if inv.progress.is_some() => {
                    if let (Some(progress), Some(status)) = (inv.progress, read_status(&status_file.0).await) {
                        progress(status.progress, &status.message);
                    }
                }
            }
        };

        if !matches!(outcome, Outcome::Exited(_))
            && let Err(e) = child.kill().await
        {
            warn!("Failed to kill Blender for {}: {}", inv.id, e);
        }
        let stdout = collect(stdout_task).await;
        let stderr = collect(stderr_task).await;
        for line in &stderr.tail {
            debug!(target: "blender", "{}", line);
        }

        match outcome {
            Outcome::TimedOut => {
                warn!("{} ({}) timed out; Blender killed", inv.script, inv.id);
                Err(ExecError::Timeout(inv.timeout.as_secs()))
            },
            Outcome::Cancelled => {
                info!("{} ({}) cancelled; Blender killed", inv.script, inv.id);
                Err(ExecError::Cancelled)
            },
            Outcome::Exited(Err(e)) => {
                Err(ExecError::Io(format!("failed to wait for Blender: {e}")))
            },
            Outcome::Exited(Ok(status)) => interpret(
                ExitInfo::from(status),
                stdout.result_line.as_deref(),
                &stdout.tail,
                &stderr.tail,
            ),
        }
    }
}

/// Resolve once the cancellation signal fires (never, without a signal).
pub(crate) async fn wait_cancelled(cancel: &mut Option<CancelSignal>) {
    match cancel {
        Some(rx) => {
            if rx.wait_for(|cancelled| *cancelled).await.is_err() {
                // Sender dropped without cancelling: never resolve.
                std::future::pending::<()>().await;
            }
        },
        None => std::future::pending::<()>().await,
    }
}

/// Deletes the wrapped file when dropped (args/status files).
struct TempFile(PathBuf);

impl Drop for TempFile {
    fn drop(&mut self) {
        if let Err(e) = std::fs::remove_file(&self.0)
            && e.kind() != std::io::ErrorKind::NotFound
        {
            debug!("could not remove {}: {}", self.0.display(), e);
        }
    }
}

/// Parsed job status file written by `mcp_common.update_status`.
#[derive(Debug, Clone, PartialEq, serde::Deserialize)]
pub struct StatusFile {
    /// Script-reported state (informational).
    #[serde(default)]
    pub status: String,
    /// Percent complete.
    #[serde(default)]
    pub progress: u8,
    /// Progress message.
    #[serde(default)]
    pub message: String,
    /// Output reported so far.
    #[serde(default)]
    pub output_path: Option<String>,
}

async fn read_status(path: &Path) -> Option<StatusFile> {
    let raw = tokio::fs::read(path).await.ok()?;
    serde_json::from_slice(&raw).ok()
}

/// Bounded capture of one output stream.
#[derive(Debug, Default)]
struct Captured {
    tail: VecDeque<String>,
    result_line: Option<String>,
}

async fn capture<R: AsyncRead + Unpin>(stream: R) -> Captured {
    let mut reader = BufReader::new(stream);
    let mut captured = Captured::default();
    let mut buf = Vec::new();
    loop {
        buf.clear();
        match reader.read_until(b'\n', &mut buf).await {
            Ok(0) | Err(_) => break,
            Ok(_) => {
                let line = String::from_utf8_lossy(&buf);
                let line = line.trim_end();
                if let Some(result) = line.strip_prefix(RESULT_MARKER) {
                    captured.result_line = Some(result.to_string());
                    continue;
                }
                if line.trim().is_empty() {
                    continue;
                }
                let mut kept = line.to_string();
                if kept.len() > MAX_LINE_LEN {
                    let mut cut = MAX_LINE_LEN;
                    while !kept.is_char_boundary(cut) {
                        cut -= 1;
                    }
                    kept.truncate(cut);
                    kept.push_str("...");
                }
                if captured.tail.len() == TAIL_LINES {
                    captured.tail.pop_front();
                }
                captured.tail.push_back(kept);
            },
        }
    }
    captured
}

async fn collect(task: Option<tokio::task::JoinHandle<Captured>>) -> Captured {
    let Some(task) = task else {
        return Captured::default();
    };
    // A leaked grandchild could keep the pipe open; don't wait forever for EOF.
    let abort = task.abort_handle();
    match tokio::time::timeout(Duration::from_secs(5), task).await {
        Ok(Ok(captured)) => captured,
        _ => {
            abort.abort();
            Captured::default()
        },
    }
}

/// Exit information, decoupled from `std::process::ExitStatus` for testing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExitInfo {
    /// Exit code, if the process exited normally.
    pub code: Option<i32>,
    /// Terminating signal (Unix), if any.
    pub signal: Option<i32>,
}

impl ExitInfo {
    fn success(self) -> bool {
        self.code == Some(0)
    }

    fn describe(self) -> String {
        match (self.code, self.signal) {
            (_, Some(sig)) => format!("was killed by signal {sig} (crash)"),
            (Some(code), _) if code >= 128 => {
                format!(
                    "exited with status {code} (killed by signal {}, likely a crash)",
                    code - 128
                )
            },
            (Some(code), _) => format!("exited with status {code}"),
            (None, None) => "exited abnormally".to_string(),
        }
    }
}

impl From<std::process::ExitStatus> for ExitInfo {
    fn from(status: std::process::ExitStatus) -> Self {
        #[cfg(unix)]
        let signal = std::os::unix::process::ExitStatusExt::signal(&status);
        #[cfg(not(unix))]
        let signal = None;
        Self {
            code: status.code(),
            signal,
        }
    }
}

/// Turn a finished process into the script's result or a descriptive error.
pub fn interpret(
    exit: ExitInfo,
    result_line: Option<&str>,
    stdout_tail: &VecDeque<String>,
    stderr_tail: &VecDeque<String>,
) -> Result<Value, ExecError> {
    let log_tail = merged_tail(stdout_tail, stderr_tail);
    let Some(raw) = result_line else {
        let mut message = format!("Blender {} without reporting a result", exit.describe());
        if let Some(hint) = diagnose(&log_tail) {
            message.push_str(". ");
            message.push_str(hint);
        }
        if !log_tail.is_empty() {
            message.push_str(". Last output:\n");
            message.push_str(&log_tail.join("\n"));
        }
        return Err(ExecError::Failed { message, log_tail });
    };

    let result: Value = serde_json::from_str(raw).map_err(|e| ExecError::Failed {
        message: format!("Blender script printed a malformed result ({e})"),
        log_tail: log_tail.clone(),
    })?;
    let reported_success = result
        .get("success")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    if reported_success && exit.success() {
        return Ok(result);
    }
    let message = result
        .get("error")
        .and_then(Value::as_str)
        .map(str::to_string)
        .unwrap_or_else(|| format!("Blender script failed ({})", exit.describe()));
    Err(ExecError::Failed { message, log_tail })
}

fn merged_tail(stdout: &VecDeque<String>, stderr: &VecDeque<String>) -> Vec<String> {
    let take = |q: &VecDeque<String>| {
        q.iter()
            .skip(q.len().saturating_sub(ERROR_TAIL_LINES))
            .cloned()
            .collect::<Vec<_>>()
    };
    let mut lines = take(stdout);
    lines.extend(take(stderr));
    lines
}

/// Known environment problems worth an explicit hint.
fn diagnose(log: &[String]) -> Option<&'static str> {
    let text = log.join("\n");
    if text.contains("libEGL")
        || text.contains("Unable to open a display")
        || text.contains("GPU backend")
    {
        Some(
            "Blender could not create an OpenGL/EGL context, which EEVEE and Workbench need. \
             Render with engine CYCLES, or run in an image with libegl1/Mesa (or a GPU) installed",
        )
    } else if text.contains("Segmentation fault") || text.contains(".crash.txt") {
        Some("Blender crashed; see the output below")
    } else {
        None
    }
}

/// Find a working Blender: `BLENDER_PATH` first, then `PATH` and common
/// install locations.
pub async fn locate_blender(explicit: Option<&Path>) -> Result<BlenderInfo, ExecError> {
    if let Some(path) = explicit {
        if !path.is_file() {
            return Err(ExecError::BlenderNotFound(format!(
                "BLENDER_PATH points to {}, which does not exist",
                path.display()
            )));
        }
        return probe(path).await.map_err(|e| {
            ExecError::BlenderNotFound(format!(
                "BLENDER_PATH={} is not a working Blender: {e}",
                path.display()
            ))
        });
    }

    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(found) = which::which("blender") {
        candidates.push(found);
    }
    candidates.extend(
        [
            "/usr/local/bin/blender",
            "/usr/bin/blender",
            "/opt/blender/blender",
            "/snap/bin/blender",
            "/Applications/Blender.app/Contents/MacOS/Blender",
        ]
        .iter()
        .map(PathBuf::from),
    );
    if let Some(home) = dirs::home_dir() {
        candidates.push(home.join(".local/bin/blender"));
    }
    if cfg!(windows)
        && let Ok(entries) = std::fs::read_dir(r"C:\Program Files\Blender Foundation")
    {
        let mut installs: Vec<PathBuf> = entries
            .flatten()
            .map(|e| e.path().join("blender.exe"))
            .collect();
        installs.sort();
        candidates.extend(installs.into_iter().rev());
    }

    let mut tried = Vec::new();
    for path in candidates {
        if !path.is_file() || tried.contains(&path) {
            continue;
        }
        match probe(&path).await {
            Ok(info) => return Ok(info),
            Err(e) => debug!("{} rejected: {}", path.display(), e),
        }
        tried.push(path);
    }
    Err(ExecError::BlenderNotFound(
        "Blender executable not found. Install Blender (4.2+) or set BLENDER_PATH".to_string(),
    ))
}

async fn probe(path: &Path) -> Result<BlenderInfo, String> {
    let output = Command::new(path)
        .arg("--version")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .output();
    let output = tokio::time::timeout(VERSION_PROBE_TIMEOUT, output)
        .await
        .map_err(|_| "timed out running --version".to_string())?
        .map_err(|e| e.to_string())?;
    if !output.status.success() {
        return Err(format!("--version exited with {}", output.status));
    }
    let version = String::from_utf8_lossy(&output.stdout)
        .lines()
        .find(|l| l.trim_start().starts_with("Blender"))
        .unwrap_or("unknown version")
        .trim()
        .to_string();
    Ok(BlenderInfo {
        path: path.to_path_buf(),
        version,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn lines(items: &[&str]) -> VecDeque<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    const OK: ExitInfo = ExitInfo {
        code: Some(0),
        signal: None,
    };
    const FAIL: ExitInfo = ExitInfo {
        code: Some(1),
        signal: None,
    };

    #[test]
    fn successful_result_is_returned() {
        let out = interpret(
            OK,
            Some(r#"{"success": true, "objects": ["Cube"]}"#),
            &lines(&["Blender 4.5"]),
            &VecDeque::new(),
        )
        .unwrap();
        assert_eq!(out, json!({"success": true, "objects": ["Cube"]}));
    }

    #[test]
    fn reported_failure_uses_script_error_message() {
        let err = interpret(
            FAIL,
            Some(r#"{"success": false, "error": "Object 'X' not found"}"#),
            &lines(&["noise"]),
            &lines(&["Traceback ..."]),
        )
        .unwrap_err();
        match err {
            ExecError::Failed { message, log_tail } => {
                assert_eq!(message, "Object 'X' not found");
                assert_eq!(log_tail, vec!["noise", "Traceback ..."]);
            },
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn success_with_nonzero_exit_is_a_failure() {
        let err = interpret(
            FAIL,
            Some(r#"{"success": true}"#),
            &VecDeque::new(),
            &VecDeque::new(),
        )
        .unwrap_err();
        assert!(err.to_string().contains("exited with status 1"));
    }

    #[test]
    fn missing_result_reports_exit_and_tail() {
        let err = interpret(
            ExitInfo {
                code: Some(139),
                signal: None,
            },
            None,
            &lines(&["Read blend: /x.blend"]),
            &lines(&["Couldn't open libEGL.so.1"]),
        )
        .unwrap_err();
        let msg = err.to_string();
        assert!(msg.contains("status 139"), "{msg}");
        assert!(msg.contains("likely a crash"), "{msg}");
        assert!(msg.contains("CYCLES"), "EGL hint expected: {msg}");
        assert!(msg.contains("libEGL.so.1"), "{msg}");
    }

    #[test]
    fn malformed_result_is_reported() {
        let err = interpret(OK, Some("{not json"), &VecDeque::new(), &VecDeque::new()).unwrap_err();
        assert!(err.to_string().contains("malformed result"));
    }

    #[test]
    fn signal_exit_is_described() {
        let info = ExitInfo {
            code: None,
            signal: Some(9),
        };
        assert!(info.describe().contains("signal 9"));
        assert!(!info.success());
    }

    #[test]
    fn merged_tail_is_bounded() {
        let many: VecDeque<String> = (0..100).map(|i| i.to_string()).collect();
        let tail = merged_tail(&many, &many);
        assert_eq!(tail.len(), ERROR_TAIL_LINES * 2);
        assert_eq!(tail.first().map(String::as_str), Some("85"));
    }

    #[tokio::test]
    async fn capture_extracts_marker_and_bounds_tail() {
        let mut data = String::new();
        for i in 0..(TAIL_LINES + 50) {
            data.push_str(&format!("line {i}\n"));
        }
        data.push_str("MCP_RESULT:{\"success\": false}\n");
        data.push_str("MCP_RESULT:{\"success\": true}\n");
        data.push_str(&"x".repeat(MAX_LINE_LEN * 2));
        data.push('\n');
        data.push_str("\n   \nlast line without newline");
        let captured = capture(data.as_bytes()).await;
        assert_eq!(captured.result_line.as_deref(), Some("{\"success\": true}"));
        assert_eq!(captured.tail.len(), TAIL_LINES);
        assert_eq!(
            captured.tail.back().map(String::as_str),
            Some("last line without newline")
        );
        assert!(captured.tail.iter().all(|l| l.len() <= MAX_LINE_LEN + 3));
    }

    #[tokio::test]
    async fn capture_tolerates_invalid_utf8() {
        let bytes: &[u8] = b"ok\n\xff\xfe broken\nMCP_RESULT:{\"success\": true}\n";
        let captured = capture(bytes).await;
        assert_eq!(captured.tail.len(), 2);
        assert!(captured.result_line.is_some());
    }

    #[tokio::test]
    async fn explicit_missing_blender_path_is_reported() {
        let err = locate_blender(Some(Path::new("/definitely/not/blender")))
            .await
            .unwrap_err();
        assert!(err.to_string().contains("BLENDER_PATH"));
    }

    #[tokio::test]
    async fn wait_cancelled_fires_on_signal() {
        let (tx, rx) = tokio::sync::watch::channel(false);
        let mut signal = Some(rx);
        let waiter = tokio::spawn(async move { wait_cancelled(&mut signal).await });
        tx.send(true).unwrap();
        tokio::time::timeout(Duration::from_secs(2), waiter)
            .await
            .expect("cancellation must be observed")
            .unwrap();
    }

    #[tokio::test]
    async fn status_file_parsing() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("x.status");
        std::fs::write(
            &path,
            r#"{"status":"RUNNING","progress":42,"message":"frame 3"}"#,
        )
        .unwrap();
        let status = read_status(&path).await.unwrap();
        assert_eq!(status.progress, 42);
        assert_eq!(status.message, "frame 3");
        std::fs::write(&path, "garbage").unwrap();
        assert!(read_status(&path).await.is_none());
        assert!(read_status(&tmp.path().join("missing")).await.is_none());
    }
}
