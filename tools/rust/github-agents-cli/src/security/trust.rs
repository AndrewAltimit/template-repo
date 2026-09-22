//! Trusted configuration loading for PR-triggered workflow runs.
//!
//! Workflows triggered by pull request events check out PR code, so every
//! file in the working tree is attacker-controllable for a malicious PR.
//! Configuration that steers the agents (`.agents.yaml` including the
//! security allow-list, `review-profiles.yaml`, `.mcp.json`) must not be
//! taken from the PR when the PR modifies it. In such runs, those files are
//! read from the PR's base branch instead.
//!
//! The base branch is taken from `GITHUB_BASE_REF` (set for `pull_request`
//! and `pull_request_target`) or, for other PR events such as
//! `pull_request_review`, from `pull_request.base.ref` in the event payload
//! at `GITHUB_EVENT_PATH`.

use std::path::Path;
use std::process::Command;

use crate::error::{Error, Result};

/// Base branch of the pull request that triggered this run, if any.
fn base_ref() -> Option<String> {
    std::env::var("GITHUB_BASE_REF")
        .ok()
        .map(|b| b.trim().to_string())
        .filter(|b| !b.is_empty())
        .or_else(base_ref_from_event)
        .filter(|b| is_safe_ref(b))
}

/// `pull_request.base.ref` from the Actions event payload.
fn base_ref_from_event() -> Option<String> {
    let path = std::env::var("GITHUB_EVENT_PATH").ok()?;
    let content = std::fs::read_to_string(path).ok()?;
    base_ref_from_payload(&content)
}

fn base_ref_from_payload(json: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(json).ok()?;
    value
        .pointer("/pull_request/base/ref")?
        .as_str()
        .map(str::to_string)
}

/// Reject refs that could be parsed as git options or ranges.
fn is_safe_ref(r: &str) -> bool {
    !r.is_empty()
        && !r.starts_with('-')
        && !r.contains("..")
        && r.chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '/' | '-' | '_' | '.'))
}

/// Compare `path` between the PR base and `HEAD`.
///
/// `Some(true)` = modified, `Some(false)` = unchanged, `None` = unknown
/// (not a pull_request run, or git could not compare).
fn modification_status(path: &str) -> Option<bool> {
    let base = base_ref()?;
    let range = format!("origin/{}...HEAD", base);
    let status = Command::new("git")
        .args(["diff", "--quiet", &range, "--", path])
        .status()
        .ok()?;
    match status.code() {
        Some(0) => Some(false),
        Some(1) => Some(true),
        _ => None,
    }
}

/// Whether `path` (relative to the repository root) may have been changed
/// by the PR under review.
///
/// Returns `false` outside pull_request workflows. Inside one, an
/// inconclusive comparison is treated as modified (fail closed).
pub fn is_modified_in_pr(path: &str) -> bool {
    if base_ref().is_none() {
        return false;
    }
    modification_status(path).unwrap_or(true)
}

/// Read `path` from the PR base branch. A file absent on the base branch is
/// reported as `NotFound` so callers fall back to their defaults.
fn read_from_base(base: &str, path: &str) -> Result<String> {
    let spec = format!("origin/{}:{}", base, path.trim_start_matches("./"));
    let output = Command::new("git").args(["show", &spec]).output()?;
    if !output.status.success() {
        tracing::warn!(
            "{} does not exist on base branch '{}': {}",
            path,
            base,
            String::from_utf8_lossy(&output.stderr).trim()
        );
        return Err(Error::Io(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("{} not present on base branch", path),
        )));
    }
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}

/// Read a configuration file, preferring the base-branch version when the
/// current PR modifies it.
///
/// Only relative paths inside the working directory are subject to the
/// base-branch substitution. When the comparison is inconclusive the local
/// file is used (with a warning) so reviews keep working on unusual clones.
pub fn read_trusted_file(path: &Path) -> Result<String> {
    let rel = path.to_string_lossy();
    if path.is_relative()
        && let Some(base) = base_ref()
    {
        match modification_status(&rel) {
            Some(true) => {
                tracing::warn!(
                    "{} is modified by this PR; using the version from base branch '{}'",
                    rel,
                    base
                );
                return read_from_base(&base, &rel);
            },
            Some(false) => {},
            None => tracing::warn!(
                "Could not compare {} against base branch '{}'; using working tree copy",
                rel,
                base
            ),
        }
    }
    Ok(std::fs::read_to_string(path)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_refs() {
        assert!(is_safe_ref("main"));
        assert!(is_safe_ref("release/1.2"));
        assert!(!is_safe_ref(""));
        assert!(!is_safe_ref("--output=/tmp/x"));
        assert!(!is_safe_ref("main..evil"));
        assert!(!is_safe_ref("main;rm"));
    }

    #[test]
    fn base_ref_from_event_payload() {
        let payload = r#"{"action":"submitted","pull_request":{"base":{"ref":"main"}}}"#;
        assert_eq!(base_ref_from_payload(payload).as_deref(), Some("main"));
        assert_eq!(base_ref_from_payload(r#"{"schedule":"0 * * * *"}"#), None);
        assert_eq!(base_ref_from_payload("not json"), None);
    }
}
