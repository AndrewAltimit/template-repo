//! End-to-end tests of the pr-monitor binary against a fake `gh` executable.
//!
//! The fake `gh` serves canned GraphQL snapshots (`snap1.json`, `snap2.json`,
//! ... then `default.json`) from a temp directory, so exit codes, stdout JSON
//! and error handling are exercised without network access.

#![cfg(unix)]

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::process::{Command, Output};

use tempfile::TempDir;

const FAKE_GH: &str = r#"#!/bin/sh
case "$1" in
  --version)
    echo "gh version 2.99.0 (fake)"
    exit 0
    ;;
  api)
    if [ "$2" = "graphql" ]; then
      if [ -f "$FAKE_GH_STATE/error.txt" ]; then
        cat "$FAKE_GH_STATE/error.txt" >&2
        exit 1
      fi
      n=$(cat "$FAKE_GH_STATE/count" 2>/dev/null || echo 0)
      n=$((n + 1))
      echo "$n" > "$FAKE_GH_STATE/count"
      if [ -f "$FAKE_GH_STATE/snap$n.json" ]; then
        cat "$FAKE_GH_STATE/snap$n.json"
      else
        cat "$FAKE_GH_STATE/default.json"
      fi
      exit 0
    fi
    echo "2026-01-01T12:05:00Z"
    exit 0
    ;;
esac
echo "unexpected gh invocation: $*" >&2
exit 1
"#;

fn snapshot_json(comments: &str) -> String {
    format!(
        r#"{{"data": {{"repository": {{"pullRequest": {{
            "state": "OPEN",
            "headRefOid": "abcdef1234567890",
            "comments": {{"pageInfo": {{"hasPreviousPage": false, "startCursor": null}},
                          "nodes": [{comments}]}},
            "reviews": {{"pageInfo": {{"hasPreviousPage": false, "startCursor": null}},
                         "nodes": []}}
        }}}}}}}}"#
    )
}

const OLD_ADMIN_COMMENT: &str = r#"{"id": "IC_old", "author": {"login": "AndrewAltimit"},
    "body": "old feedback", "createdAt": "2026-01-01T12:00:00Z", "url": null}"#;

const NEW_REVIEW: &str = r###"{"id": "IC_review", "author": {"login": "github-actions"},
    "body": "## Claude AI Code Review\n<!-- claude-review-marker:commit:abcdef12 -->\nFix X",
    "createdAt": "2026-01-01T12:10:00Z", "url": "https://github.com/o/r/pull/7#c1"}"###;

const NEW_ADMIN_COMMENT: &str = r#"{"id": "IC_new", "author": {"login": "AndrewAltimit"},
    "body": "[Approved][Claude]", "createdAt": "2026-01-01T12:20:00Z", "url": null}"#;

/// Installs `contents` as an executable script at `dest`.
///
/// The script is staged in a sibling file and copied into place by `cp`, so
/// this process never holds a writable fd to `dest`. Writing it in-process
/// races with parallel tests: a sibling test's fork can inherit the open fd
/// before its exec closes it, and exec'ing `dest` then fails with ETXTBSY
/// ("Text file busy").
fn install_script(dest: &Path, contents: &str) {
    let staged = dest.with_extension("src");
    std::fs::write(&staged, contents).unwrap();
    let status = Command::new("cp").arg(&staged).arg(dest).status().unwrap();
    assert!(status.success(), "cp {} failed", dest.display());
    std::fs::set_permissions(dest, std::fs::Permissions::from_mode(0o755)).unwrap();
}

struct FakeGh {
    dir: TempDir,
}

impl FakeGh {
    fn new() -> Self {
        let dir = TempDir::new().unwrap();
        let gh = dir.path().join("gh");
        install_script(&gh, FAKE_GH);
        Self { dir }
    }

    fn write(&self, name: &str, contents: &str) {
        fs::write(self.dir.path().join(name), contents).unwrap();
    }

    fn run(&self, args: &[&str]) -> Output {
        run_with_path(
            args,
            &format!("{}:/usr/bin:/bin", self.dir.path().display()),
            self.dir.path(),
        )
    }
}

fn run_with_path(args: &[&str], path: &str, state: &Path) -> Output {
    Command::new(env!("CARGO_BIN_EXE_pr-monitor"))
        .args(args)
        .env("PATH", path)
        .env("FAKE_GH_STATE", state)
        .env_remove("PR_MONITOR_ADMIN_USER")
        .output()
        .unwrap()
}

fn stdout_json(output: &Output) -> serde_json::Value {
    serde_json::from_slice(&output.stdout).unwrap_or_else(|e| {
        panic!(
            "stdout is not JSON ({e}): {}\nstderr: {}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        )
    })
}

#[test]
fn since_commit_reports_existing_review() {
    let gh = FakeGh::new();
    gh.write(
        "default.json",
        &snapshot_json(&format!("{OLD_ADMIN_COMMENT},{NEW_REVIEW}")),
    );

    let output = gh.run(&["7", "--since-commit", "abc1234", "--json"]);
    assert_eq!(output.status.code(), Some(0));

    let json = stdout_json(&output);
    assert_eq!(json["needs_response"], true);
    assert_eq!(json["response_type"], "ai_agent_review");
    assert_eq!(json["priority"], "normal");
    assert_eq!(json["pr_number"], 7);
    assert_eq!(json["head_sha"], "abcdef1234567890");
    assert_eq!(json["comment"]["author"], "github-actions");
    assert_eq!(json["comment"]["url"], "https://github.com/o/r/pull/7#c1");
    assert_eq!(json["review_metadata"]["reviewer"], "claude");
    assert_eq!(json["review_metadata"]["commit_sha"], "abcdef12");
    assert!(json["review_metadata"].get("outdated").is_none());

    // --json keeps stderr free of progress output
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(!stderr.contains("MONITORING AGENT"), "stderr: {stderr}");
}

#[test]
fn detects_new_comment_while_polling() {
    let gh = FakeGh::new();
    gh.write("snap1.json", &snapshot_json(OLD_ADMIN_COMMENT));
    gh.write(
        "default.json",
        &snapshot_json(&format!("{OLD_ADMIN_COMMENT},{NEW_ADMIN_COMMENT}")),
    );

    let output = gh.run(&["7", "--poll-interval", "1", "--timeout", "30", "--compact"]);
    assert_eq!(output.status.code(), Some(0));

    let stdout = String::from_utf8_lossy(&output.stdout);
    assert_eq!(stdout.trim().lines().count(), 1, "compact output: {stdout}");
    let json = stdout_json(&output);
    assert_eq!(json["response_type"], "admin_command");
    assert_eq!(json["priority"], "high");
    assert_eq!(json["review_metadata"]["trigger_action"], "approved");
    assert_eq!(json["review_metadata"]["trigger_agent"], "claude");

    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        stderr.contains("RELEVANT COMMENT DETECTED"),
        "stderr: {stderr}"
    );
}

#[test]
fn type_filter_skips_other_comments() {
    let gh = FakeGh::new();
    gh.write(
        "default.json",
        &snapshot_json(&format!(
            "{OLD_ADMIN_COMMENT},{NEW_REVIEW},{NEW_ADMIN_COMMENT}"
        )),
    );

    let output = gh.run(&[
        "7",
        "--since-commit",
        "abc1234",
        "--type",
        "ai_agent_review",
        "--json",
    ]);
    assert_eq!(output.status.code(), Some(0));
    assert_eq!(stdout_json(&output)["response_type"], "ai_agent_review");
}

#[test]
fn timeout_uses_configurable_exit_code() {
    let gh = FakeGh::new();
    gh.write("default.json", &snapshot_json(OLD_ADMIN_COMMENT));

    let output = gh.run(&["7", "--timeout", "0", "--json"]);
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());

    let output = gh.run(&["7", "--timeout", "0", "--timeout-exit-code", "2", "--json"]);
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("Timeout"));
}

#[test]
fn missing_pr_is_reported() {
    let gh = FakeGh::new();
    gh.write(
        "error.txt",
        "GraphQL: Could not resolve to a PullRequest with the number of 9. (repository.pullRequest)",
    );

    let output = gh.run(&["9", "--json"]);
    assert_eq!(output.status.code(), Some(1));
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("#9 was not found"), "stderr: {stderr}");
}

#[test]
fn missing_gh_is_reported() {
    let empty = TempDir::new().unwrap();
    let output = run_with_path(&["9"], &empty.path().display().to_string(), empty.path());
    assert_eq!(output.status.code(), Some(1));
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("not found on PATH"), "stderr: {stderr}");
}

#[test]
fn invalid_repo_is_rejected() {
    let gh = FakeGh::new();
    let output = gh.run(&["9", "--repo", "not-a-repo"]);
    assert_eq!(output.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&output.stderr).contains("expected OWNER/REPO"));
}
