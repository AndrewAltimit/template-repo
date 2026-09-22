//! Project-root discovery and GitHub Actions integration helpers.

use std::env;
use std::io::Write;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};

/// Marker files that identify the repository root.
const ROOT_MARKERS: [&str; 2] = ["docker-compose.yml", "CLAUDE.md"];

/// Find the project root by walking up from the current directory looking for
/// `docker-compose.yml` + `CLAUDE.md`.
pub fn find_project_root() -> Result<PathBuf> {
    let cwd = env::current_dir().context("failed to get current directory")?;
    find_root_from(&cwd)
}

/// Walk up from `start` until a directory containing all [`ROOT_MARKERS`] is found.
pub fn find_root_from(start: &Path) -> Result<PathBuf> {
    let mut dir = start.to_path_buf();
    loop {
        if ROOT_MARKERS.iter().all(|m| dir.join(m).is_file()) {
            return Ok(dir);
        }
        if !dir.pop() {
            bail!(
                "could not find project root (no directory containing {} above {})",
                ROOT_MARKERS.join(" + "),
                start.display()
            );
        }
    }
}

/// Locate the project root and make it the process working directory.
/// All subcommands resolve relative paths (compose file, scripts) from there.
pub fn enter_project_root() -> Result<PathBuf> {
    let root = find_project_root()?;
    env::set_current_dir(&root)
        .with_context(|| format!("failed to enter project root {}", root.display()))?;
    Ok(root)
}

/// Get the compose file path from the project root
pub fn compose_file(root: &Path) -> PathBuf {
    root.join("docker-compose.yml")
}

/// Check if running in CI environment (GitHub Actions)
pub fn is_ci() -> bool {
    env::var_os("CI").is_some()
}

/// Host user and group IDs, used so files written by CI containers are owned
/// by the invoking user. Non-Unix hosts fall back to 1000:1000, matching the
/// defaults in docker-compose.yml.
pub fn user_ids() -> (u32, u32) {
    #[cfg(unix)]
    {
        // SAFETY: getuid/getgid have no preconditions and cannot fail.
        unsafe { (libc::getuid(), libc::getgid()) }
    }
    #[cfg(not(unix))]
    {
        (1000, 1000)
    }
}

/// Export `USER_ID` / `GROUP_ID` (and Python bytecode settings) so every
/// `docker compose` child picks them up via variable interpolation.
///
/// Must be called while the process is still single-threaded (i.e. at the
/// start of a subcommand, before any HTTP client or worker thread exists).
pub fn export_compose_env() {
    let (uid, gid) = user_ids();
    // SAFETY: called at subcommand start before any threads are spawned.
    unsafe {
        env::set_var("USER_ID", uid.to_string());
        env::set_var("GROUP_ID", gid.to_string());
        env::set_var("PYTHONDONTWRITEBYTECODE", "1");
        env::set_var("PYTHONPYCACHEPREFIX", "/tmp/pycache");
    }
}

/// Write a key=value pair to `$GITHUB_OUTPUT` if available.
pub fn set_github_output(key: &str, value: &str) {
    append_github_file("GITHUB_OUTPUT", key, value);
}

/// Write a key=value pair to `$GITHUB_ENV` if available.
pub fn set_github_env(key: &str, value: &str) {
    append_github_file("GITHUB_ENV", key, value);
}

fn append_github_file(var: &str, key: &str, value: &str) {
    let Ok(path) = env::var(var) else {
        return;
    };
    let result = std::fs::OpenOptions::new()
        .append(true)
        .create(true)
        .open(&path)
        .and_then(|mut f| f.write_all(format_github_kv(key, value).as_bytes()));
    if let Err(e) = result {
        // Not fatal (the command's own work already happened), but a missing
        // output silently changes downstream workflow behavior, so say so.
        crate::shared::output::warn(&format!("failed to write {key} to ${var} ({path}): {e}"));
    }
}

/// Format a `$GITHUB_OUTPUT` / `$GITHUB_ENV` entry. Multi-line values use the
/// heredoc form, since a raw newline would otherwise start a new (bogus) entry.
pub fn format_github_kv(key: &str, value: &str) -> String {
    if !value.contains('\n') && !value.contains('\r') {
        return format!("{key}={value}\n");
    }
    let mut delim = String::from("AUTOMATION_CLI_EOF");
    while value.lines().any(|l| l == delim) {
        delim.push('_');
    }
    format!("{key}<<{delim}\n{value}\n{delim}\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn github_kv_single_line() {
        assert_eq!(format_github_kv("errors", "3"), "errors=3\n");
    }

    #[test]
    fn github_kv_multiline_uses_heredoc() {
        let out = format_github_kv("summary", "a\nb");
        assert_eq!(
            out,
            "summary<<AUTOMATION_CLI_EOF\na\nb\nAUTOMATION_CLI_EOF\n"
        );
    }

    #[test]
    fn github_kv_delimiter_avoids_collision() {
        let out = format_github_kv("k", "x\nAUTOMATION_CLI_EOF\ny");
        assert!(out.starts_with("k<<AUTOMATION_CLI_EOF_\n"));
        assert!(out.ends_with("\nAUTOMATION_CLI_EOF_\n"));
    }

    #[test]
    fn find_root_walks_up() {
        let dir = tempfile::tempdir().unwrap();
        for m in ROOT_MARKERS {
            std::fs::write(dir.path().join(m), "").unwrap();
        }
        let nested = dir.path().join("a/b/c");
        std::fs::create_dir_all(&nested).unwrap();
        let root = find_root_from(&nested).unwrap();
        assert_eq!(
            root.canonicalize().unwrap(),
            dir.path().canonicalize().unwrap()
        );
    }

    #[test]
    fn find_root_requires_all_markers() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("docker-compose.yml"), "").unwrap();
        // CLAUDE.md missing: must not match this directory. (It may still
        // match a real ancestor on the host, so only assert it isn't `dir`.)
        if let Ok(found) = find_root_from(dir.path()) {
            assert_ne!(found, dir.path());
        }
    }
}
