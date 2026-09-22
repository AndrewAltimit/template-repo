//! Execution boundary: running the `board-manager` CLI.
//!
//! All GitHub API access is delegated to `board-manager` (see
//! `tools/rust/board-manager`), invoked as `board-manager --format json ...`.
//! Its contract: on success exactly one JSON document on stdout; on failure
//! exit status 1 and an `Error: ...` line on stderr (logs also go to stderr).
//!
//! The [`BoardRunner`] trait abstracts this boundary so the tool layer can be
//! tested offline with a mock (see `server.rs` tests).

use async_trait::async_trait;
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;
use tokio::process::Command;
use tokio::sync::Mutex;
use tracing::{debug, info, warn};

/// Name of the CLI binary (without platform suffix).
pub const BOARD_MANAGER_BIN: &str = "board-manager";

/// Default timeout for a single `board-manager` invocation.
///
/// `board-manager` itself waits out GitHub rate limits for up to 5 minutes and
/// applies a 30s per-request HTTP timeout, so this is deliberately generous.
pub const DEFAULT_TIMEOUT_SECS: u64 = 300;

/// Timeout for the `--version` probe used during discovery.
const PROBE_TIMEOUT: Duration = Duration::from_secs(10);

/// Maximum length of an error message extracted from stderr.
const MAX_ERROR_LEN: usize = 2000;

/// Errors from running `board-manager`.
#[derive(Debug, thiserror::Error)]
pub enum RunError {
    /// The binary could not be located (or the configured one is unusable).
    #[error("{0}")]
    NotFound(String),

    /// The process could not be started.
    #[error("failed to start board-manager at {path}: {message}")]
    Spawn {
        /// Binary that failed to start.
        path: String,
        /// OS error text.
        message: String,
    },

    /// The process exceeded the configured timeout and was killed.
    #[error(
        "board-manager timed out after {0}s and was killed (GitHub rate limiting or network \
         trouble?). Raise --timeout-secs / GITHUB_BOARD_TIMEOUT_SECS if this persists."
    )]
    Timeout(u64),

    /// The command ran and reported a failure.
    #[error("board-manager failed ({status}): {message}")]
    Failed {
        /// Exit status description.
        status: String,
        /// Error extracted from stderr.
        message: String,
    },

    /// The command succeeded but stdout was not valid JSON.
    #[error("board-manager returned invalid JSON: {0}")]
    InvalidOutput(String),
}

/// Something that can execute `board-manager` subcommands.
#[async_trait]
pub trait BoardRunner: Send + Sync {
    /// Run `board-manager --format json <args...>` and return its parsed
    /// stdout.
    async fn run(&self, args: &[String]) -> Result<Value, RunError>;

    /// Diagnostic information for the `board_status` tool.
    async fn diagnostics(&self) -> Value;
}

/// Runner configuration (from CLI flags / environment).
#[derive(Debug, Clone)]
pub struct RunnerConfig {
    /// Explicit binary path; disables auto-discovery when set.
    pub board_manager: Option<PathBuf>,
    /// Board config file forwarded as `--config` to every call.
    pub board_config: Option<PathBuf>,
    /// Per-invocation timeout.
    pub timeout: Duration,
}

impl Default for RunnerConfig {
    fn default() -> Self {
        Self {
            board_manager: None,
            board_config: None,
            timeout: Duration::from_secs(DEFAULT_TIMEOUT_SECS),
        }
    }
}

/// A located, verified `board-manager` binary.
#[derive(Debug, Clone)]
struct Located {
    path: PathBuf,
    version: String,
}

/// Runs the real `board-manager` binary as a child process.
///
/// The binary is discovered lazily on first use and cached. Discovery is
/// serialized behind a mutex so concurrent first calls probe only once; a
/// failed discovery is not cached, so installing the binary later works
/// without restarting the server.
pub struct CliRunner {
    config: RunnerConfig,
    located: Mutex<Option<Located>>,
}

impl CliRunner {
    /// Create a runner; nothing is spawned until the first call.
    pub fn new(config: RunnerConfig) -> Self {
        Self {
            config,
            located: Mutex::new(None),
        }
    }

    /// Return the cached binary, discovering it if necessary.
    async fn locate(&self) -> Result<Located, RunError> {
        let mut guard = self.located.lock().await;
        if let Some(found) = guard.as_ref() {
            return Ok(found.clone());
        }

        let found = match &self.config.board_manager {
            Some(path) => probe(path).await.map_err(|e| {
                RunError::NotFound(format!(
                    "configured board-manager '{}' is not usable: {e}",
                    path.display()
                ))
            })?,
            None => discover().await?,
        };
        info!(
            "Using board-manager {} at {}",
            found.version,
            found.path.display()
        );
        *guard = Some(found.clone());
        Ok(found)
    }

    /// Forget the cached binary (e.g. after it disappeared).
    async fn forget(&self) {
        *self.located.lock().await = None;
    }

    /// Build the full argument vector for an invocation.
    fn argv(&self, args: &[String]) -> Vec<String> {
        let mut argv = vec!["--format".to_string(), "json".to_string()];
        if let Some(cfg) = &self.config.board_config {
            argv.push(format!("--config={}", cfg.display()));
        }
        argv.extend(args.iter().cloned());
        argv
    }
}

#[async_trait]
impl BoardRunner for CliRunner {
    async fn run(&self, args: &[String]) -> Result<Value, RunError> {
        let located = self.locate().await?;
        let argv = self.argv(args);
        debug!("Running {} {:?}", located.path.display(), argv);

        let mut cmd = Command::new(&located.path);
        cmd.args(&argv)
            // Never let the child read the MCP stdio channel.
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            // Dropping the future on timeout kills the child.
            .kill_on_drop(true);

        let child = cmd.spawn().map_err(|e| RunError::Spawn {
            path: located.path.display().to_string(),
            message: e.to_string(),
        });
        let child = match child {
            Ok(c) => c,
            Err(e) => {
                // The binary may have been removed or replaced; rediscover next time.
                self.forget().await;
                return Err(e);
            },
        };

        let secs = self.config.timeout.as_secs();
        let output = match tokio::time::timeout(self.config.timeout, child.wait_with_output()).await
        {
            Ok(Ok(out)) => out,
            Ok(Err(e)) => {
                return Err(RunError::Spawn {
                    path: located.path.display().to_string(),
                    message: e.to_string(),
                });
            },
            Err(_) => {
                warn!("board-manager {:?} timed out after {}s", args, secs);
                return Err(RunError::Timeout(secs));
            },
        };

        interpret_output(
            output.status.success(),
            &describe_status(&output.status),
            &output.stdout,
            &output.stderr,
        )
    }

    async fn diagnostics(&self) -> Value {
        let mut info = json!({
            "timeout_secs": self.config.timeout.as_secs(),
            "board_config": self.config.board_config.as_ref().map(|p| p.display().to_string()),
            "board_manager_override": self.config.board_manager.as_ref().map(|p| p.display().to_string()),
        });
        match self.locate().await {
            Ok(found) => {
                info["board_manager_available"] = json!(true);
                info["board_manager_path"] = json!(found.path.display().to_string());
                info["board_manager_version"] = json!(found.version);
            },
            Err(e) => {
                info["board_manager_available"] = json!(false);
                info["board_manager_error"] = json!(e.to_string());
            },
        }
        info
    }
}

fn describe_status(status: &std::process::ExitStatus) -> String {
    match status.code() {
        Some(code) => format!("exit code {code}"),
        None => "terminated by signal".to_string(),
    }
}

/// Turn a finished process' output into a result.
///
/// Empty stdout on success maps to `{}`. On failure the error message is
/// extracted from stderr (see [`extract_error`]).
pub fn interpret_output(
    success: bool,
    status: &str,
    stdout: &[u8],
    stderr: &[u8],
) -> Result<Value, RunError> {
    if !success {
        return Err(RunError::Failed {
            status: status.to_string(),
            message: extract_error(&String::from_utf8_lossy(stderr)),
        });
    }
    let stdout = String::from_utf8_lossy(stdout);
    let trimmed = stdout.trim();
    if trimmed.is_empty() {
        return Ok(json!({}));
    }
    serde_json::from_str(trimmed).map_err(|e| {
        let preview: String = trimmed.chars().take(200).collect();
        RunError::InvalidOutput(format!("{e} (output starts with: {preview:?})"))
    })
}

/// Extract the most useful error message from `board-manager` stderr.
///
/// Prefers the last `Error: ...` line (the CLI's failure contract); otherwise
/// falls back to the last non-empty lines (e.g. clap usage errors). The
/// result is truncated to a sane length.
pub fn extract_error(stderr: &str) -> String {
    let lines: Vec<&str> = stderr
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .collect();

    let message = if let Some(line) = lines.iter().rev().find(|l| l.starts_with("Error:")) {
        line.trim_start_matches("Error:").trim().to_string()
    } else if let Some(line) = lines.iter().rev().find(|l| l.starts_with("error:")) {
        // clap argument errors
        line.trim_start_matches("error:").trim().to_string()
    } else if lines.is_empty() {
        "no error output".to_string()
    } else {
        let start = lines.len().saturating_sub(5);
        lines[start..].join(" | ")
    };

    if message.chars().count() > MAX_ERROR_LEN {
        let mut truncated: String = message.chars().take(MAX_ERROR_LEN).collect();
        truncated.push_str("...");
        truncated
    } else {
        message
    }
}

/// File name of the binary on this platform.
fn bin_file_name() -> String {
    format!("{BOARD_MANAGER_BIN}{}", std::env::consts::EXE_SUFFIX)
}

/// Candidate locations, in priority order, without duplicates.
///
/// 1. `PATH`
/// 2. next to the running `mcp-github-board` executable
/// 3. `~/.local/bin`, `~/.cargo/bin`, `/usr/local/bin`
/// 4. `./tools/rust/board-manager/target/release` (repo checkout as CWD)
pub fn candidate_paths(
    path_hit: Option<PathBuf>,
    exe_dir: Option<&Path>,
    home: Option<&Path>,
    cwd: Option<&Path>,
) -> Vec<PathBuf> {
    let name = bin_file_name();
    let mut out: Vec<PathBuf> = Vec::new();
    let mut push = |p: PathBuf| {
        if !out.contains(&p) {
            out.push(p);
        }
    };

    if let Some(p) = path_hit {
        push(p);
    }
    if let Some(dir) = exe_dir {
        push(dir.join(&name));
    }
    if let Some(home) = home {
        push(home.join(".local").join("bin").join(&name));
        push(home.join(".cargo").join("bin").join(&name));
    }
    if cfg!(unix) {
        push(PathBuf::from("/usr/local/bin").join(&name));
    }
    if let Some(cwd) = cwd {
        push(
            cwd.join("tools")
                .join("rust")
                .join("board-manager")
                .join("target")
                .join("release")
                .join(&name),
        );
    }
    out
}

/// Search the candidate locations for a working binary.
async fn discover() -> Result<Located, RunError> {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(Path::to_path_buf));
    let home = dirs::home_dir();
    let cwd = std::env::current_dir().ok();
    let candidates = candidate_paths(
        which::which(BOARD_MANAGER_BIN).ok(),
        exe_dir.as_deref(),
        home.as_deref(),
        cwd.as_deref(),
    );

    let mut problems = Vec::new();
    for path in &candidates {
        if !path.is_file() {
            continue;
        }
        match probe(path).await {
            Ok(found) => return Ok(found),
            Err(e) => {
                debug!("{} rejected: {}", path.display(), e);
                problems.push(format!("{}: {e}", path.display()));
            },
        }
    }

    let searched: Vec<String> = candidates.iter().map(|p| p.display().to_string()).collect();
    let mut msg = format!(
        "board-manager CLI not found. Build it with 'cargo build --release' in \
         tools/rust/board-manager (then run its install.sh), put it on PATH, or set \
         BOARD_MANAGER_PATH / --board-manager. Searched: PATH, {}",
        searched.join(", ")
    );
    if !problems.is_empty() {
        msg.push_str(&format!(". Unusable candidates: {}", problems.join("; ")));
    }
    Err(RunError::NotFound(msg))
}

/// Verify a binary by running `--version` (with a timeout).
async fn probe(path: &Path) -> Result<Located, String> {
    let mut cmd = Command::new(path);
    cmd.arg("--version")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .kill_on_drop(true);
    let output = match tokio::time::timeout(PROBE_TIMEOUT, cmd.output()).await {
        Ok(Ok(out)) => out,
        Ok(Err(e)) => return Err(e.to_string()),
        Err(_) => return Err("--version timed out".to_string()),
    };
    if !output.status.success() {
        return Err(format!(
            "--version failed ({})",
            describe_status(&output.status)
        ));
    }
    let version = String::from_utf8_lossy(&output.stdout).trim().to_string();
    Ok(Located {
        path: path.to_path_buf(),
        version: if version.is_empty() {
            "unknown".to_string()
        } else {
            version
        },
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interpret_success_json() {
        let v = interpret_output(true, "exit code 0", b"{\"success\": true}\n", b"").unwrap();
        assert_eq!(v, json!({"success": true}));
        let v = interpret_output(true, "exit code 0", b"null", b"").unwrap();
        assert!(v.is_null());
        let v = interpret_output(true, "exit code 0", b"  \n", b"").unwrap();
        assert_eq!(v, json!({}));
    }

    #[test]
    fn interpret_invalid_json() {
        let err = interpret_output(true, "exit code 0", b"Claimed issue #4", b"").unwrap_err();
        match err {
            RunError::InvalidOutput(msg) => assert!(msg.contains("Claimed issue #4"), "{msg}"),
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn interpret_failure_uses_stderr() {
        let stderr = b"2026-01-01 WARN something\nError: Issue #9 is not on the project board\n";
        let err = interpret_output(false, "exit code 1", b"", stderr).unwrap_err();
        assert_eq!(
            err.to_string(),
            "board-manager failed (exit code 1): Issue #9 is not on the project board"
        );
    }

    #[test]
    fn extract_error_variants() {
        assert_eq!(
            extract_error("error: unexpected argument '--foo' found\n\nUsage: x"),
            "unexpected argument '--foo' found"
        );
        assert_eq!(extract_error(""), "no error output");
        assert_eq!(extract_error("a\nb\n\nc"), "a | b | c");
        let long = format!("Error: {}", "x".repeat(MAX_ERROR_LEN * 2));
        assert_eq!(extract_error(&long).chars().count(), MAX_ERROR_LEN + 3);
    }

    #[test]
    fn candidates_are_ordered_and_deduplicated() {
        let name = bin_file_name();
        let home = PathBuf::from("/home/u");
        let exe = home.join(".cargo").join("bin");
        let c = candidate_paths(
            Some(PathBuf::from("/opt/bm").join(&name)),
            Some(&exe),
            Some(&home),
            Some(Path::new("/repo")),
        );
        assert_eq!(c[0], PathBuf::from("/opt/bm").join(&name));
        // exe dir == ~/.cargo/bin: listed once, in exe-dir position
        assert_eq!(c[1], exe.join(&name));
        assert_eq!(c[2], home.join(".local").join("bin").join(&name));
        assert_eq!(c.iter().filter(|p| **p == exe.join(&name)).count(), 1);
        assert!(
            c.last()
                .unwrap()
                .ends_with(Path::new("tools/rust/board-manager/target/release").join(&name))
        );
    }

    #[test]
    fn argv_prefixes_format_and_config() {
        let runner = CliRunner::new(RunnerConfig {
            board_config: Some(PathBuf::from("board.yml")),
            ..RunnerConfig::default()
        });
        assert_eq!(
            runner.argv(&["agents".to_string()]),
            vec!["--format", "json", "--config=board.yml", "agents"]
        );
        let plain = CliRunner::new(RunnerConfig::default());
        assert_eq!(
            plain.argv(&["config".to_string()]),
            vec!["--format", "json", "config"]
        );
    }

    #[tokio::test]
    async fn missing_override_reports_not_found() {
        let runner = CliRunner::new(RunnerConfig {
            board_manager: Some(PathBuf::from("/definitely/not/here/board-manager")),
            ..RunnerConfig::default()
        });
        let err = runner.run(&["agents".to_string()]).await.unwrap_err();
        assert!(matches!(err, RunError::NotFound(_)), "{err:?}");
        let diag = runner.diagnostics().await;
        assert_eq!(diag["board_manager_available"], json!(false));
        assert!(
            diag["board_manager_error"]
                .as_str()
                .unwrap()
                .contains("not usable")
        );
    }

    /// End-to-end tests against a fake `board-manager` shell script.
    #[cfg(unix)]
    mod process {
        use super::*;
        use std::os::unix::fs::PermissionsExt;

        fn fake(dir: &Path, body: &str) -> PathBuf {
            let path = dir.join("board-manager");
            let script = format!(
                "#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then echo 'board-manager 9.9.9'; exit 0; fi\n{body}\n"
            );
            std::fs::write(&path, script).unwrap();
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o755)).unwrap();
            path
        }

        fn tmpdir(tag: &str) -> PathBuf {
            let dir = std::env::temp_dir().join(format!(
                "mcp-github-board-test-{tag}-{}",
                std::process::id()
            ));
            std::fs::create_dir_all(&dir).unwrap();
            dir
        }

        fn runner(path: PathBuf, timeout: Duration) -> CliRunner {
            CliRunner::new(RunnerConfig {
                board_manager: Some(path),
                board_config: None,
                timeout,
            })
        }

        #[tokio::test]
        async fn passes_arguments_and_parses_json() {
            let dir = tmpdir("ok");
            // Echo the argument count and the last argument as JSON.
            let path = fake(
                &dir,
                "eval last=\\${$#}; printf '{\"argc\": %s, \"last\": \"%s\"}' \"$#\" \"$last\"",
            );
            let r = runner(path, Duration::from_secs(10));
            let v = r
                .run(&["claim".into(), "5".into(), "--agent=-x y".into()])
                .await
                .unwrap();
            assert_eq!(v, json!({"argc": 5, "last": "--agent=-x y"}));
            let diag = r.diagnostics().await;
            assert_eq!(diag["board_manager_version"], json!("board-manager 9.9.9"));
            let _ = std::fs::remove_dir_all(dir);
        }

        #[tokio::test]
        async fn failure_surfaces_stderr_error() {
            let dir = tmpdir("fail");
            let path = fake(
                &dir,
                "echo 'Error: Authentication failed: bad token' >&2; exit 1",
            );
            let err = runner(path, Duration::from_secs(10))
                .run(&["agents".into()])
                .await
                .unwrap_err();
            assert_eq!(
                err.to_string(),
                "board-manager failed (exit code 1): Authentication failed: bad token"
            );
            let _ = std::fs::remove_dir_all(dir);
        }

        #[tokio::test]
        async fn slow_process_times_out() {
            let dir = tmpdir("slow");
            let path = fake(&dir, "sleep 30");
            let started = std::time::Instant::now();
            let err = runner(path, Duration::from_millis(300))
                .run(&["ready".into()])
                .await
                .unwrap_err();
            assert!(matches!(err, RunError::Timeout(_)), "{err:?}");
            assert!(started.elapsed() < Duration::from_secs(10));
            let _ = std::fs::remove_dir_all(dir);
        }
    }
}
