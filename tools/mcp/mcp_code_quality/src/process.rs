//! Bounded subprocess execution.
//!
//! [`run`] is the only place external tools are spawned. It guarantees:
//!
//! - **No shell**: the program and each argument are passed as separate argv
//!   entries (`tokio::process::Command`), so user strings are never parsed by
//!   a shell.
//! - **Hard timeout that actually kills**: on timeout the child (and, on Unix,
//!   its whole process group -- pytest/cargo spawn grandchildren) is sent
//!   SIGKILL. The previous implementation only dropped the future, leaving the
//!   tool running in the background.
//! - **Bounded memory**: stdout/stderr are streamed into [`CappedBuffer`]s that
//!   keep the head and tail of the output and count what was dropped, instead
//!   of buffering an unbounded amount of test output.
//! - **No stdin**: stdin is `/dev/null`, so a tool that prompts cannot hang.
//! - **Deterministic output**: colour is disabled via environment variables
//!   and any ANSI escapes that still appear (ruff colours output even when
//!   piped) are stripped, so the output parsers always see plain text.

use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::time::{Duration, Instant};
use tokio::io::{AsyncRead, AsyncReadExt};
use tokio::process::Command;
use tracing::debug;

/// A fully specified command: program, argv, working directory, extra env.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommandSpec {
    pub program: String,
    pub args: Vec<String>,
    pub cwd: Option<PathBuf>,
    pub env: Vec<(String, String)>,
}

impl CommandSpec {
    /// New command with no arguments.
    pub fn new(program: impl Into<String>) -> Self {
        Self {
            program: program.into(),
            args: Vec::new(),
            cwd: None,
            env: Vec::new(),
        }
    }

    /// Append one argument.
    pub fn arg(mut self, arg: impl Into<String>) -> Self {
        self.args.push(arg.into());
        self
    }

    /// Append several arguments.
    pub fn args<I, S>(mut self, args: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.args.extend(args.into_iter().map(Into::into));
        self
    }

    /// Append a path argument.
    pub fn path_arg(self, path: &std::path::Path) -> Self {
        self.arg(path.display().to_string())
    }

    /// Set the working directory.
    pub fn cwd(mut self, dir: impl Into<PathBuf>) -> Self {
        self.cwd = Some(dir.into());
        self
    }

    /// Add an environment variable.
    pub fn env(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.env.push((key.into(), value.into()));
        self
    }

    /// Human-readable command line (for results/audit only -- never executed
    /// through a shell). Arguments containing whitespace are quoted.
    pub fn display(&self) -> String {
        std::iter::once(self.program.as_str())
            .chain(self.args.iter().map(String::as_str))
            .map(|a| {
                if a.is_empty() || a.contains(char::is_whitespace) {
                    format!("'{}'", a.replace('\'', "'\\''"))
                } else {
                    a.to_string()
                }
            })
            .collect::<Vec<_>>()
            .join(" ")
    }
}

/// Captured result of a finished process.
#[derive(Debug, Clone)]
pub struct ProcessOutput {
    /// Exit code; `-1` when terminated by a signal.
    pub code: i32,
    pub stdout: String,
    pub stderr: String,
    /// True if either stream exceeded the capture limit.
    pub truncated: bool,
    pub duration: Duration,
}

impl ProcessOutput {
    /// stdout and stderr joined (stdout first), skipping empty streams.
    pub fn combined(&self) -> String {
        match (self.stdout.trim().is_empty(), self.stderr.trim().is_empty()) {
            (false, false) => format!("{}\n{}", self.stdout.trim_end(), self.stderr.trim_end()),
            (false, true) => self.stdout.clone(),
            (true, false) => self.stderr.clone(),
            (true, true) => String::new(),
        }
    }
}

/// Why a process could not produce an output.
#[derive(Debug)]
pub enum ProcessError {
    /// Program not found on PATH.
    NotFound(String),
    /// Killed after exceeding the timeout.
    Timeout { program: String, secs: u64 },
    /// Any other spawn / wait failure.
    Io(String),
}

impl std::fmt::Display for ProcessError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NotFound(p) => write!(f, "{p} not found on PATH; install it first"),
            Self::Timeout { program, secs } => {
                write!(f, "{program} timed out after {secs}s and was killed")
            },
            Self::Io(e) => write!(f, "failed to run command: {e}"),
        }
    }
}

/// Byte buffer that keeps the first `cap/2` and last `cap/2` bytes written to
/// it and counts everything dropped in between.
#[derive(Debug)]
pub struct CappedBuffer {
    head: Vec<u8>,
    tail: Vec<u8>,
    head_cap: usize,
    tail_cap: usize,
    total: usize,
}

impl CappedBuffer {
    /// A buffer retaining at most `cap` bytes.
    pub fn new(cap: usize) -> Self {
        let head_cap = cap / 2;
        Self {
            head: Vec::new(),
            tail: Vec::new(),
            head_cap,
            tail_cap: cap - head_cap,
            total: 0,
        }
    }

    /// Append bytes.
    pub fn push(&mut self, mut data: &[u8]) {
        self.total += data.len();
        if self.head.len() < self.head_cap {
            let take = (self.head_cap - self.head.len()).min(data.len());
            self.head.extend_from_slice(&data[..take]);
            data = &data[take..];
        }
        if data.is_empty() {
            return;
        }
        self.tail.extend_from_slice(data);
        // Amortized trimming: only compact once the tail is twice its budget.
        if self.tail.len() > self.tail_cap.saturating_mul(2).max(1) {
            let excess = self.tail.len() - self.tail_cap;
            self.tail.drain(..excess);
        }
    }

    /// Number of bytes discarded so far.
    #[cfg(test)]
    pub fn dropped(&self) -> usize {
        self.total
            .saturating_sub(self.head.len() + self.tail.len().min(self.tail_cap))
    }

    /// Final text (lossy UTF-8) and whether anything was dropped.
    pub fn finish(mut self) -> (String, bool) {
        if self.tail.len() > self.tail_cap {
            let excess = self.tail.len() - self.tail_cap;
            self.tail.drain(..excess);
        }
        let dropped = self.total - self.head.len() - self.tail.len();
        let mut text = String::from_utf8_lossy(&self.head).into_owned();
        if dropped > 0 {
            text.push_str(&format!(
                "\n\n... [{dropped} bytes of output truncated] ...\n\n"
            ));
        }
        text.push_str(&String::from_utf8_lossy(&self.tail));
        (text, dropped > 0)
    }
}

async fn read_capped<R: AsyncRead + Unpin>(mut reader: R, cap: usize) -> CappedBuffer {
    let mut buf = CappedBuffer::new(cap);
    let mut chunk = vec![0u8; 16 * 1024];
    loop {
        match reader.read(&mut chunk).await {
            Ok(0) | Err(_) => break,
            Ok(n) => buf.push(&chunk[..n]),
        }
    }
    buf
}

/// Environment applied to every child so output is plain text.
fn base_env() -> HashMap<&'static str, &'static str> {
    HashMap::from([
        // Note: no FORCE_COLOR -- several CLIs treat its mere presence (even
        // "0") as "force colour on".
        ("NO_COLOR", "1"),
        ("CLICOLOR", "0"),
        ("PY_COLORS", "0"),
        ("CARGO_TERM_COLOR", "never"),
        ("PYTHONDONTWRITEBYTECODE", "1"),
        ("PYTHONUNBUFFERED", "1"),
    ])
}

/// Kill the child and, on Unix, every process in its process group.
fn kill_tree(child: &mut tokio::process::Child) {
    #[cfg(unix)]
    if let Some(pid) = child.id() {
        // SAFETY: killpg only sends a signal; the child was spawned as the
        // leader of its own process group (process_group(0)), so this cannot
        // target the server's own group.
        unsafe {
            libc::killpg(pid as libc::pid_t, libc::SIGKILL);
        }
    }
    let _ = child.start_kill();
}

/// Run `spec` with a hard `timeout`, capturing at most `max_output` bytes per
/// stream.
pub async fn run(
    spec: &CommandSpec,
    timeout: Duration,
    max_output: usize,
) -> Result<ProcessOutput, ProcessError> {
    debug!("Running: {}", spec.display());

    let mut cmd = Command::new(&spec.program);
    cmd.args(&spec.args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    for (k, v) in base_env() {
        cmd.env(k, v);
    }
    for (k, v) in &spec.env {
        cmd.env(k, v);
    }
    if let Some(dir) = &spec.cwd {
        cmd.current_dir(dir);
    }
    #[cfg(unix)]
    cmd.process_group(0);

    let start = Instant::now();
    let mut child = cmd.spawn().map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            ProcessError::NotFound(spec.program.clone())
        } else {
            ProcessError::Io(e.to_string())
        }
    })?;

    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    let mut out_task = tokio::spawn(async move {
        match stdout {
            Some(s) => read_capped(s, max_output).await,
            None => CappedBuffer::new(max_output),
        }
    });
    let mut err_task = tokio::spawn(async move {
        match stderr {
            Some(s) => read_capped(s, max_output).await,
            None => CappedBuffer::new(max_output),
        }
    });

    let status = match tokio::time::timeout(timeout, child.wait()).await {
        Ok(Ok(status)) => status,
        Ok(Err(e)) => {
            kill_tree(&mut child);
            out_task.abort();
            err_task.abort();
            return Err(ProcessError::Io(e.to_string()));
        },
        Err(_) => {
            kill_tree(&mut child);
            let _ = tokio::time::timeout(Duration::from_secs(5), child.wait()).await;
            out_task.abort();
            err_task.abort();
            return Err(ProcessError::Timeout {
                program: spec.program.clone(),
                secs: timeout.as_secs(),
            });
        },
    };

    // A grandchild that inherited the pipes can keep them open after the
    // direct child exits; give the readers a short grace period, then kill
    // the group and give up on the remaining output.
    let grace = Duration::from_secs(5);
    let mut late = false;
    let out = match tokio::time::timeout(grace, &mut out_task).await {
        Ok(Ok(b)) => Some(b),
        _ => {
            late = true;
            None
        },
    };
    let err = match tokio::time::timeout(grace, &mut err_task).await {
        Ok(Ok(b)) => Some(b),
        _ => {
            late = true;
            None
        },
    };
    if late {
        kill_tree(&mut child);
        out_task.abort();
        err_task.abort();
    }

    let (stdout, t1) = out.map(CappedBuffer::finish).unwrap_or_default();
    let (stderr, t2) = err.map(CappedBuffer::finish).unwrap_or_default();

    Ok(ProcessOutput {
        code: status.code().unwrap_or(-1),
        stdout: strip_ansi(&stdout),
        stderr: strip_ansi(&stderr),
        truncated: t1 || t2 || late,
        duration: start.elapsed(),
    })
}

/// Remove ANSI escape sequences from `s`: CSI (`ESC [ ... final-byte`), OSC
/// (`ESC ] ... BEL` or `ESC ] ... ESC \`), and two-character `ESC x` escapes.
pub fn strip_ansi(s: &str) -> String {
    const ESC: char = '\u{1b}';
    const BEL: char = '\u{7}';
    if !s.contains(ESC) {
        return s.to_string();
    }
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c != ESC {
            out.push(c);
            continue;
        }
        match chars.next() {
            Some('[') => {
                // Parameters/intermediates until a final byte in 0x40..=0x7E.
                for c in chars.by_ref() {
                    if ('\u{40}'..='\u{7e}').contains(&c) {
                        break;
                    }
                }
            },
            Some(']') => {
                while let Some(c) = chars.next() {
                    if c == BEL {
                        break;
                    }
                    if c == ESC {
                        if chars.peek() == Some(&'\\') {
                            chars.next();
                        }
                        break;
                    }
                }
            },
            _ => {},
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strips_ansi_sequences() {
        let colored = "\u{1b}[1mwork/a.py\u{1b}[0m\u{1b}[36m:\u{1b}[0m1\u{1b}[36m:\u{1b}[0m8: F401";
        assert_eq!(strip_ansi(colored), "work/a.py:1:8: F401");
        assert_eq!(
            strip_ansi("\u{1b}]8;;http://x\u{7}link\u{1b}]8;;\u{1b}\\"),
            "link"
        );
        assert_eq!(strip_ansi("plain"), "plain");
        assert_eq!(strip_ansi("dangling\u{1b}"), "dangling");
    }

    #[test]
    fn capped_buffer_under_limit_keeps_everything() {
        let mut b = CappedBuffer::new(100);
        b.push(b"hello ");
        b.push(b"world");
        assert_eq!(b.dropped(), 0);
        let (s, t) = b.finish();
        assert_eq!(s, "hello world");
        assert!(!t);
    }

    #[test]
    fn capped_buffer_keeps_head_and_tail() {
        let mut b = CappedBuffer::new(10);
        for i in 0..1000 {
            b.push(format!("{}", i % 10).as_bytes());
        }
        let (s, t) = b.finish();
        assert!(t);
        assert!(s.starts_with("01234"), "{s}");
        assert!(s.ends_with("56789"), "{s}");
        assert!(s.contains("[990 bytes of output truncated]"), "{s}");
    }

    #[test]
    fn capped_buffer_large_single_chunk() {
        let mut b = CappedBuffer::new(4);
        b.push(b"abcdefghij");
        let (s, t) = b.finish();
        assert!(t);
        assert!(s.starts_with("ab"));
        assert!(s.ends_with("ij"));
    }

    #[test]
    fn capped_buffer_zero_cap_drops_all() {
        let mut b = CappedBuffer::new(0);
        b.push(b"abc");
        let (s, t) = b.finish();
        assert!(t);
        assert!(s.contains("3 bytes"));
    }

    #[test]
    fn display_quotes_whitespace() {
        let spec = CommandSpec::new("pytest")
            .arg("-k")
            .arg("not slow")
            .arg("x'y z");
        assert_eq!(spec.display(), r#"pytest -k 'not slow' 'x'\''y z'"#);
    }

    #[test]
    fn combined_output() {
        let o = ProcessOutput {
            code: 0,
            stdout: "a\n".into(),
            stderr: "b\n".into(),
            truncated: false,
            duration: Duration::ZERO,
        };
        assert_eq!(o.combined(), "a\nb");
    }

    #[tokio::test]
    async fn missing_program_is_not_found() {
        let spec = CommandSpec::new("definitely-not-a-real-binary-mcp-cq");
        let err = run(&spec, Duration::from_secs(5), 1024).await.unwrap_err();
        assert!(matches!(err, ProcessError::NotFound(_)), "{err}");
    }

    #[tokio::test]
    async fn captures_output_and_exit_code() {
        // cargo is always present when running `cargo test`.
        let spec = CommandSpec::new("cargo").arg("--version");
        let out = run(&spec, Duration::from_secs(30), 1024).await.unwrap();
        assert_eq!(out.code, 0);
        assert!(out.stdout.starts_with("cargo "), "{}", out.stdout);
        let spec = CommandSpec::new("cargo").arg("definitely-not-a-subcommand-xyz");
        let out = run(&spec, Duration::from_secs(30), 1024).await.unwrap();
        assert_ne!(out.code, 0);
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn timeout_kills_process() {
        let spec = CommandSpec::new("sh").arg("-c").arg("sleep 30");
        let start = Instant::now();
        let err = run(&spec, Duration::from_millis(300), 1024)
            .await
            .unwrap_err();
        assert!(matches!(err, ProcessError::Timeout { .. }), "{err}");
        assert!(start.elapsed() < Duration::from_secs(10));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn output_is_truncated() {
        let spec = CommandSpec::new("sh")
            .arg("-c")
            .arg("i=0; while [ $i -lt 2000 ]; do echo line$i; i=$((i+1)); done");
        let out = run(&spec, Duration::from_secs(30), 200).await.unwrap();
        assert!(out.truncated);
        assert!(out.stdout.starts_with("line0"));
        assert!(out.stdout.trim_end().ends_with("line1999"));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn env_and_cwd_are_applied() {
        let dir = std::env::temp_dir();
        let spec = CommandSpec::new("sh")
            .arg("-c")
            .arg("echo $NO_COLOR $MY_VAR; pwd")
            .env("MY_VAR", "hi")
            .cwd(&dir);
        let out = run(&spec, Duration::from_secs(10), 1024).await.unwrap();
        assert!(out.stdout.starts_with("1 hi"), "{}", out.stdout);
    }
}
