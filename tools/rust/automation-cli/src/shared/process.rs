//! Thin, consistent wrappers around `std::process::Command`.
//!
//! Every helper closes stdin (so a child never blocks waiting for a TTY) and
//! produces an `anyhow` error that names the full command line on failure.

use std::ffi::OsStr;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Output, Stdio};
use std::time::{Duration, Instant};

use anyhow::{Context, Result, anyhow, bail};

/// Run a command, inheriting stdout/stderr so the user sees output in real time.
/// Returns Ok(()) if the command exits 0, Err otherwise.
pub fn run(cmd: &str, args: &[&str]) -> Result<()> {
    run_with_env(cmd, args, &[])
}

/// Like [`run`], but with extra environment variables set on the child only.
pub fn run_with_env(cmd: &str, args: &[&str], env: &[(&str, &str)]) -> Result<()> {
    let status = Command::new(cmd)
        .args(args)
        .envs(env.iter().copied())
        .stdin(Stdio::null())
        .status()
        .with_context(|| format!("failed to execute: {}", display_cmd(cmd, args)))?;
    check_status(cmd, args, status)
}

/// Run a command in a specific working directory.
pub fn run_in(dir: &Path, cmd: &str, args: &[&str]) -> Result<()> {
    let status = Command::new(cmd)
        .args(args)
        .current_dir(dir)
        .stdin(Stdio::null())
        .status()
        .with_context(|| {
            format!(
                "failed to execute in {}: {}",
                dir.display(),
                display_cmd(cmd, args)
            )
        })?;
    check_status(cmd, args, status)
}

/// Run a command and capture its stdout as a string (stderr is inherited).
pub fn run_capture(cmd: &str, args: &[&str]) -> Result<String> {
    let output = Command::new(cmd)
        .args(args)
        .stdin(Stdio::null())
        .stderr(Stdio::inherit())
        .output()
        .with_context(|| format!("failed to execute: {}", display_cmd(cmd, args)))?;
    check_status(cmd, args, output.status)?;
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}

/// Run a command capturing both stdout and stderr, without judging the exit
/// status. Use this when the caller needs to inspect stderr (e.g. to classify
/// a `git push` rejection).
pub fn run_output(cmd: &str, args: &[&str]) -> Result<Output> {
    Command::new(cmd)
        .args(args)
        .stdin(Stdio::null())
        .output()
        .with_context(|| format!("failed to execute: {}", display_cmd(cmd, args)))
}

/// Run a command silently, returning Ok(true) if exit 0, Ok(false) if non-zero,
/// Err only when the process could not be spawned.
pub fn run_check(cmd: &str, args: &[&str]) -> Result<bool> {
    let status = Command::new(cmd)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .with_context(|| format!("failed to execute: {}", display_cmd(cmd, args)))?;
    Ok(status.success())
}

/// Run a command with retries and exponential backoff
/// (`initial_delay_secs`, then doubling).
/// Returns Ok(()) if any attempt succeeds, Err with the last error otherwise.
pub fn run_with_retries(
    cmd: &str,
    args: &[&str],
    max_retries: u32,
    initial_delay_secs: u64,
) -> Result<()> {
    let mut attempt = 0;
    loop {
        match run(cmd, args) {
            Ok(()) => return Ok(()),
            Err(e) if attempt >= max_retries => return Err(e),
            Err(e) => {
                let delay = backoff_secs(initial_delay_secs, attempt);
                eprintln!(
                    "[retry] {cmd} failed (attempt {}/{}), retrying in {delay}s: {e}",
                    attempt + 1,
                    max_retries + 1,
                );
                std::thread::sleep(Duration::from_secs(delay));
                attempt += 1;
            },
        }
    }
}

/// Exponential backoff: `initial * 2^attempt`, saturating instead of overflowing.
pub fn backoff_secs(initial: u64, attempt: u32) -> u64 {
    initial.saturating_mul(2u64.saturating_pow(attempt))
}

/// Run a command with stdin from a file, capture stdout, and enforce a timeout.
/// Returns the captured stdout on success. Kills the process on timeout.
///
/// Stdout is drained in a separate thread to prevent deadlocks when the child
/// writes more than the OS pipe buffer capacity (~64KB).
pub fn run_capture_with_timeout(
    cmd: &str,
    args: &[&str],
    stdin_path: &Path,
    timeout: Duration,
) -> Result<String> {
    let stdin_file = std::fs::File::open(stdin_path)
        .with_context(|| format!("failed to open stdin file: {}", stdin_path.display()))?;

    let mut child = Command::new(cmd)
        .args(args)
        .stdin(stdin_file)
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .with_context(|| format!("failed to spawn: {}", display_cmd(cmd, args)))?;

    let mut stdout_pipe = child
        .stdout
        .take()
        .ok_or_else(|| anyhow!("child stdout was not captured"))?;
    let reader_handle = std::thread::spawn(move || {
        let mut buf = Vec::new();
        let _ = stdout_pipe.read_to_end(&mut buf);
        buf
    });

    let waited = wait_timeout(&mut child, timeout);
    if !matches!(waited, Ok(Some(_))) {
        // Timed out or wait failed: make sure the child is gone before joining
        // the reader, otherwise the reader could block forever.
        let _ = child.kill();
        let _ = child.wait();
    }
    let stdout = reader_handle.join().unwrap_or_default();

    match waited {
        Ok(Some(status)) => {
            check_status(cmd, args, status)?;
            Ok(String::from_utf8_lossy(&stdout).into_owned())
        },
        Ok(None) => bail!("{cmd} timed out after {}s", timeout.as_secs()),
        Err(e) => bail!("error waiting for {cmd}: {e}"),
    }
}

/// Check if an executable exists on `PATH` (no subprocess spawned).
pub fn command_exists(cmd: &str) -> bool {
    find_on_path(cmd).is_some()
}

/// Locate an executable on `PATH`, honouring `PATHEXT` on Windows.
pub fn find_on_path(cmd: &str) -> Option<PathBuf> {
    let path_var = std::env::var_os("PATH")?;
    find_in_dirs(cmd, std::env::split_paths(&path_var))
}

fn find_in_dirs(cmd: &str, dirs: impl Iterator<Item = PathBuf>) -> Option<PathBuf> {
    // A path with a separator is checked directly rather than searched for.
    if Path::new(cmd).components().count() > 1 {
        let p = PathBuf::from(cmd);
        return is_executable(&p).then_some(p);
    }
    let exts = executable_extensions();
    for dir in dirs {
        for ext in &exts {
            let mut candidate = dir.join(cmd);
            if !ext.is_empty() {
                let mut name = candidate.into_os_string();
                name.push(ext);
                candidate = PathBuf::from(name);
            }
            if is_executable(&candidate) {
                return Some(candidate);
            }
        }
    }
    None
}

#[cfg(windows)]
fn executable_extensions() -> Vec<String> {
    let mut exts = vec![String::new()];
    let pathext = std::env::var("PATHEXT").unwrap_or_else(|_| ".EXE;.CMD;.BAT;.COM".into());
    exts.extend(
        pathext
            .split(';')
            .filter(|e| !e.is_empty())
            .map(str::to_string),
    );
    exts
}

#[cfg(not(windows))]
fn executable_extensions() -> Vec<String> {
    vec![String::new()]
}

#[cfg(unix)]
fn is_executable(path: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    path.metadata()
        .is_ok_and(|m| m.is_file() && m.permissions().mode() & 0o111 != 0)
}

#[cfg(not(unix))]
fn is_executable(path: &Path) -> bool {
    path.is_file()
}

/// A `Command` that re-invokes this very binary. Used to run CI stages from
/// the review commands without depending on any shell wrapper being present.
pub fn self_command() -> Result<Command> {
    let exe = std::env::current_exe().context("cannot locate the automation-cli executable")?;
    Ok(Command::new(exe))
}

/// Wait for a child with a deadline. Returns Ok(None) on timeout.
pub fn wait_timeout(
    child: &mut std::process::Child,
    timeout: Duration,
) -> std::io::Result<Option<ExitStatus>> {
    let start = Instant::now();
    loop {
        if let Some(status) = child.try_wait()? {
            return Ok(Some(status));
        }
        if start.elapsed() >= timeout {
            return Ok(None);
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

fn display_cmd<S: AsRef<OsStr>>(cmd: &str, args: &[S]) -> String {
    let mut s = cmd.to_string();
    for a in args {
        s.push(' ');
        s.push_str(&a.as_ref().to_string_lossy());
    }
    s
}

fn check_status(cmd: &str, args: &[&str], status: ExitStatus) -> Result<()> {
    if status.success() {
        Ok(())
    } else {
        bail!("{} exited with {status}", display_cmd(cmd, args));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backoff_doubles_and_saturates() {
        assert_eq!(backoff_secs(2, 0), 2);
        assert_eq!(backoff_secs(2, 1), 4);
        assert_eq!(backoff_secs(2, 3), 16);
        assert_eq!(backoff_secs(2, 200), u64::MAX);
    }

    #[test]
    fn find_in_dirs_locates_executable() {
        let dir = tempfile::tempdir().unwrap();
        let name = if cfg!(windows) { "tool.exe" } else { "tool" };
        let path = dir.path().join(name);
        std::fs::write(&path, "#!/bin/sh\n").unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o755)).unwrap();
        }
        let found = find_in_dirs("tool", std::iter::once(dir.path().to_path_buf()));
        assert_eq!(found.as_deref(), Some(path.as_path()));
        assert!(find_in_dirs("missing-tool", std::iter::once(dir.path().to_path_buf())).is_none());
    }

    #[cfg(unix)]
    #[test]
    fn find_in_dirs_skips_non_executable() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("plain"), "data").unwrap();
        assert!(find_in_dirs("plain", std::iter::once(dir.path().to_path_buf())).is_none());
    }

    #[test]
    fn run_check_reports_spawn_failure_as_error() {
        assert!(run_check("definitely-not-a-real-binary-xyz", &[]).is_err());
    }

    #[test]
    fn display_cmd_joins_args() {
        assert_eq!(display_cmd("git", &["push", "origin"]), "git push origin");
    }
}
