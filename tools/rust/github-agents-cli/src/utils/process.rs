//! Subprocess helpers shared by every agent backend.
//!
//! Centralizes the pieces that were previously copy-pasted into each agent:
//! binary discovery, stdin feeding, timeouts that actually kill the child,
//! and transient-error classification.

use std::process::{Output, Stdio};
use std::time::Duration;

use tokio::io::AsyncWriteExt;
use tokio::process::Command;
use tracing::{debug, warn};

use crate::error::Error;

/// Run `cmd` to completion, optionally feeding `stdin_input`, and enforce
/// `timeout`.
///
/// Guarantees:
/// - The child is killed if the timeout elapses (`kill_on_drop`), so a hung
///   agent CLI running with elevated permissions never outlives the call.
/// - Stdin is written concurrently with output collection, so a child that
///   produces lots of output before reading its input cannot deadlock us,
///   and the timeout covers the stdin write as well.
///
/// Spawn failures are mapped to [`Error::AgentNotAvailable`] when the
/// executable does not exist; timeouts map to [`Error::AgentTimeout`].
/// A non-zero exit status is *not* treated as an error here; callers decide.
pub async fn run_with_timeout(
    name: &str,
    mut cmd: Command,
    stdin_input: Option<&str>,
    timeout: Duration,
) -> Result<Output, Error> {
    cmd.stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(if stdin_input.is_some() {
            Stdio::piped()
        } else {
            Stdio::null()
        })
        .kill_on_drop(true);

    let mut child = cmd.spawn().map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            Error::AgentNotAvailable {
                name: name.to_string(),
                reason: "executable not found".to_string(),
            }
        } else {
            Error::Io(e)
        }
    })?;

    let stdin_task = match (stdin_input, child.stdin.take()) {
        (Some(input), Some(mut stdin)) => {
            let input = input.as_bytes().to_vec();
            Some(tokio::spawn(async move {
                // A child that exits without reading stdin yields EPIPE; that is
                // not our failure to report, the exit status will tell the story.
                if let Err(e) = stdin.write_all(&input).await {
                    debug!("stdin write ended early: {}", e);
                }
                let _ = stdin.shutdown().await;
            }))
        },
        _ => None,
    };

    let result = tokio::time::timeout(timeout, child.wait_with_output()).await;
    if let Some(task) = stdin_task {
        task.abort();
    }

    match result {
        Ok(output) => output.map_err(Error::Io),
        Err(_) => {
            warn!("{} timed out after {}s", name, timeout.as_secs());
            Err(Error::AgentTimeout {
                name: name.to_string(),
                timeout: timeout.as_secs(),
                stdout: String::new(),
                stderr: String::new(),
            })
        },
    }
}

/// Check whether a subprocess error message indicates a transient network or
/// service failure (as opposed to a configuration error).
///
/// Transient failures are reported as `Error::AgentExecutionFailed` with a
/// `service unavailable (transient)` prefix so workflow wrappers can match
/// them and skip gracefully.
pub fn is_transient_error(stderr: &str) -> bool {
    const PATTERNS: &[&str] = &[
        "fetch failed",
        "econnrefused",
        "etimedout",
        "econnreset",
        "enetunreach",
        "enotfound",
        "socket hang up",
        "network error",
        "dns resolution",
        "service unavailable",
        "server error",
        "overloaded",
        "503",
        "502",
        "504",
    ];
    let lower = stderr.to_lowercase();
    PATTERNS.iter().any(|p| lower.contains(p))
}

/// Verify a binary exists and exits successfully when run with `arg`.
pub fn verify_binary(path: &str, arg: &str) -> bool {
    std::process::Command::new(path)
        .arg(arg)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// Locate an agent CLI binary.
///
/// Search order:
/// 1. The `env_override` environment variable (explicit path)
/// 2. `name` on `PATH`
/// 3. `/usr/local/bin/<name>`, `/usr/bin/<name>`, `~/.local/bin/<name>`,
///    `~/go/bin/<name>`
/// 4. Every `~/.nvm/versions/node/*/bin/<name>` (newest version first)
///
/// Candidates are verified by running `<candidate> --version`, which also
/// avoids depending on `which` (absent in some containers).
pub fn find_binary(env_override: &str, name: &str) -> Option<String> {
    if let Ok(path) = std::env::var(env_override)
        && !path.is_empty()
    {
        if verify_binary(&path, "--version") {
            debug!("Using {} from {}: {}", name, env_override, path);
            return Some(path);
        }
        warn!(
            "{}={} does not point to a working binary, searching defaults",
            env_override, path
        );
    }

    candidate_paths(name, std::env::var("HOME").ok().as_deref())
        .into_iter()
        .find(|c| verify_binary(c, "--version"))
}

/// Build the ordered candidate list used by [`find_binary`].
fn candidate_paths(name: &str, home: Option<&str>) -> Vec<String> {
    let mut candidates = vec![
        name.to_string(),
        format!("/usr/local/bin/{name}"),
        format!("/usr/bin/{name}"),
    ];

    if let Some(home) = home.filter(|h| !h.is_empty()) {
        candidates.push(format!("{home}/.local/bin/{name}"));
        candidates.push(format!("{home}/go/bin/{name}"));

        let nvm_dir = format!("{home}/.nvm/versions/node");
        if let Ok(entries) = std::fs::read_dir(&nvm_dir) {
            let mut versions: Vec<String> = entries
                .filter_map(|e| e.ok())
                .filter(|e| e.path().is_dir())
                .map(|e| e.file_name().to_string_lossy().to_string())
                .collect();
            versions.sort_by(|a, b| compare_node_versions(b, a));
            for version in versions {
                candidates.push(format!("{nvm_dir}/{version}/bin/{name}"));
            }
        }
    }

    candidates
}

/// Compare `vMAJOR.MINOR.PATCH` directory names numerically (so v22 sorts
/// above v8). Unparseable names sort below every parseable version, which
/// keeps this a total order (required by `sort_by`).
fn compare_node_versions(a: &str, b: &str) -> std::cmp::Ordering {
    fn key(v: &str) -> (Option<Vec<u64>>, &str) {
        let parsed = v
            .trim_start_matches('v')
            .split('.')
            .map(|p| p.parse().ok())
            .collect();
        (parsed, v)
    }
    key(a).cmp(&key(b))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn transient_error_detection() {
        assert!(is_transient_error("TypeError: fetch failed"));
        assert!(is_transient_error(
            "Error: connect ECONNREFUSED 127.0.0.1:443"
        ));
        assert!(is_transient_error("HTTP 503 Service Unavailable"));
        assert!(is_transient_error("502 Bad Gateway"));
        assert!(is_transient_error("Error: socket hang up"));
        assert!(is_transient_error("getaddrinfo ENOTFOUND api.example.com"));
        assert!(is_transient_error("Internal Server Error"));
        assert!(is_transient_error("FETCH FAILED"));
        assert!(is_transient_error("Network Error"));
        assert!(!is_transient_error("Invalid API key"));
        assert!(!is_transient_error("Permission denied"));
        assert!(!is_transient_error("File not found"));
    }

    #[test]
    fn node_versions_sort_numerically() {
        let mut v = vec!["v8.1.0", "v22.16.0", "v20.18.0", "weird"];
        v.sort_by(|a, b| compare_node_versions(b, a));
        assert_eq!(v, vec!["v22.16.0", "v20.18.0", "v8.1.0", "weird"]);
    }

    #[test]
    fn candidate_paths_include_defaults() {
        let c = candidate_paths("claude", None);
        assert_eq!(c[0], "claude");
        assert!(c.contains(&"/usr/local/bin/claude".to_string()));
        let c = candidate_paths("crush", Some("/home/u"));
        assert!(c.contains(&"/home/u/go/bin/crush".to_string()));
    }

    #[tokio::test]
    async fn missing_binary_is_agent_not_available() {
        let cmd = Command::new("definitely-not-a-real-binary-xyz");
        let err = run_with_timeout("x", cmd, None, Duration::from_secs(5))
            .await
            .unwrap_err();
        assert!(matches!(err, Error::AgentNotAvailable { .. }));
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn stdin_is_forwarded() {
        let cmd = Command::new("cat");
        let out = run_with_timeout("cat", cmd, Some("hello"), Duration::from_secs(5))
            .await
            .unwrap();
        assert_eq!(String::from_utf8_lossy(&out.stdout), "hello");
    }

    #[cfg(unix)]
    #[tokio::test]
    async fn timeout_is_enforced() {
        let mut cmd = Command::new("sleep");
        cmd.arg("10");
        let err = run_with_timeout("sleep", cmd, None, Duration::from_millis(200))
            .await
            .unwrap_err();
        assert!(matches!(err, Error::AgentTimeout { .. }));
    }
}
