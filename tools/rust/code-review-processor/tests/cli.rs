//! End-to-end tests of the `code-review-processor` binary.
//!
//! Tests that apply fixes run against a throwaway git repository. Nothing here
//! talks to GitHub: comment/PR actions are exercised in `--dry-run` mode.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

use serde_json::Value;
use tempfile::TempDir;

const DB_RS: &str = "use crate::conn::Connection;\n\n\
pub fn query_user(conn: &Connection, name: &str) -> Vec<String> {\n    \
let sql = format!(\"SELECT * FROM users WHERE name = '{}'\", name);\n    \
conn.query(&sql, &[])\n}\n";

const README: &str = "# Demo\n\nRun with cargo run.\n";

fn fixture(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name)
}

/// Build a command for the binary with a hermetic git environment.
fn cmd(cwd: &Path) -> Command {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_code-review-processor"));
    cmd.current_dir(cwd)
        .env_remove("GITHUB_REPOSITORY")
        .env_remove("RUST_LOG")
        .env("HOME", cwd)
        .env("GIT_CONFIG_NOSYSTEM", "1")
        .env("GIT_AUTHOR_NAME", "Test")
        .env("GIT_AUTHOR_EMAIL", "test@example.com")
        .env("GIT_COMMITTER_NAME", "Test")
        .env("GIT_COMMITTER_EMAIL", "test@example.com");
    cmd
}

fn run(cwd: &Path, args: &[&str]) -> Output {
    cmd(cwd).args(args).output().expect("binary runs")
}

fn git(repo: &Path, args: &[&str]) -> String {
    let out = Command::new("git")
        .args(args)
        .current_dir(repo)
        .env("HOME", repo)
        .env("GIT_CONFIG_NOSYSTEM", "1")
        .env("GIT_AUTHOR_NAME", "Test")
        .env("GIT_AUTHOR_EMAIL", "test@example.com")
        .env("GIT_COMMITTER_NAME", "Test")
        .env("GIT_COMMITTER_EMAIL", "test@example.com")
        .output()
        .expect("git runs");
    assert!(
        out.status.success(),
        "git {args:?}: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    String::from_utf8_lossy(&out.stdout).into_owned()
}

/// A git repo containing the files the fixtures patch.
fn repo() -> TempDir {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path();
    git(path, &["init", "-q", "-b", "main"]);
    fs::create_dir_all(path.join("src")).unwrap();
    fs::write(path.join("src/db.rs"), DB_RS).unwrap();
    fs::write(path.join("README.md"), README).unwrap();
    git(path, &["add", "."]);
    git(path, &["commit", "-q", "-m", "initial"]);
    dir
}

fn stdout_json(out: &Output) -> Value {
    serde_json::from_slice(&out.stdout).unwrap_or_else(|e| {
        panic!(
            "stdout is not JSON ({e}): {}\nstderr: {}",
            String::from_utf8_lossy(&out.stdout),
            String::from_utf8_lossy(&out.stderr)
        )
    })
}

fn stderr(out: &Output) -> String {
    String::from_utf8_lossy(&out.stderr).into_owned()
}

#[test]
fn parse_only_prints_nothing_in_text_mode() {
    let dir = tempfile::tempdir().unwrap();
    for name in [
        "envelope_with_fixes.json",
        "review_only_flat.json",
        "legacy_tagged.json",
        "failed_envelope.json",
    ] {
        let out = run(dir.path(), &["--input", fixture(name).to_str().unwrap()]);
        assert!(out.status.success(), "{name}: {}", stderr(&out));
        assert!(out.stdout.is_empty(), "{name}: logs must not go to stdout");
    }
}

#[test]
fn json_summary_for_envelope() {
    let dir = tempfile::tempdir().unwrap();
    let input = fixture("envelope_with_fixes.json");
    let out = run(
        dir.path(),
        &["-i", input.to_str().unwrap(), "--output-format", "json"],
    );
    assert!(out.status.success(), "{}", stderr(&out));
    let summary = stdout_json(&out);
    assert_eq!(summary["severity"], "critical");
    assert_eq!(summary["findings_count"], 2);
    assert_eq!(summary["review_id"], "rev-7f3a2c");
    assert_eq!(summary["review_status"], "completed");
    assert_eq!(summary["made_changes"], false);
}

#[test]
fn stdin_input_and_lenient_fields() {
    let dir = tempfile::tempdir().unwrap();
    let mut child = cmd(dir.path())
        .args(["--output-format", "json"])
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap();
    {
        use std::io::Write;
        let body = fs::read(fixture("review_only_flat.json")).unwrap();
        child.stdin.take().unwrap().write_all(&body).unwrap();
    }
    let out = child.wait_with_output().unwrap();
    assert!(out.status.success(), "{}", stderr(&out));
    let summary = stdout_json(&out);
    assert_eq!(summary["severity"], "low");
    assert_eq!(summary["findings_count"], 1);
}

#[test]
fn errors_exit_1_with_message_on_stderr() {
    let dir = tempfile::tempdir().unwrap();
    let denied = run(
        dir.path(),
        &["-i", fixture("security_denied.json").to_str().unwrap()],
    );
    assert_eq!(denied.status.code(), Some(1));
    assert!(stderr(&denied).contains("security-denied"));
    assert!(denied.stdout.is_empty());

    let garbage = dir.path().join("garbage.json");
    fs::write(&garbage, "{\"review_markdown\": ").unwrap();
    let out = run(dir.path(), &["-i", garbage.to_str().unwrap()]);
    assert_eq!(out.status.code(), Some(1));

    let missing = run(dir.path(), &["-i", "does-not-exist.json"]);
    assert_eq!(missing.status.code(), Some(1));
    assert!(stderr(&missing).contains("does-not-exist.json"));

    let not_utf8 = dir.path().join("latin1.json");
    fs::write(&not_utf8, b"{\"review_markdown\": \"caf\xe9\"}").unwrap();
    assert_eq!(
        run(dir.path(), &["-i", not_utf8.to_str().unwrap()])
            .status
            .code(),
        Some(1)
    );
}

#[test]
fn usage_errors_exit_2() {
    let dir = tempfile::tempdir().unwrap();
    assert_eq!(
        run(dir.path(), &["--output-format", "xml"]).status.code(),
        Some(2)
    );
    assert_eq!(run(dir.path(), &["--no-such-flag"]).status.code(), Some(2));
}

#[test]
fn missing_pr_number_fails_before_anything_happens() {
    let dir = tempfile::tempdir().unwrap();
    let input = fixture("legacy_tagged.json");
    let out = run(
        dir.path(),
        &[
            "-i",
            input.to_str().unwrap(),
            "--post-comment",
            "--repository",
            "o/r",
        ],
    );
    assert_eq!(out.status.code(), Some(1));
    assert!(stderr(&out).contains("--pr-number"));
}

#[test]
fn severity_threshold_exits_3() {
    let dir = tempfile::tempdir().unwrap();
    let input = fixture("envelope_with_fixes.json");
    let input = input.to_str().unwrap();
    assert_eq!(
        run(dir.path(), &["-i", input, "--fail-on-severity", "high"])
            .status
            .code(),
        Some(3)
    );
    let low = fixture("review_only_flat.json");
    assert_eq!(
        run(
            dir.path(),
            &["-i", low.to_str().unwrap(), "--fail-on-severity", "high"]
        )
        .status
        .code(),
        Some(0)
    );
}

#[test]
fn commit_changes_applies_normalized_fixes() {
    let repo = repo();
    let path = repo.path();
    // Untracked junk (like the workflow's review_response.json) must not be committed.
    fs::copy(
        fixture("envelope_with_fixes.json"),
        path.join("review_response.json"),
    )
    .unwrap();

    let out = run(
        path,
        &[
            "-i",
            "review_response.json",
            "--commit-changes",
            "--commit-message",
            "fix: apply review",
            "--output-format",
            "json",
        ],
    );
    assert!(out.status.success(), "{}", stderr(&out));
    let summary = stdout_json(&out);
    assert_eq!(summary["made_changes"], true);
    assert_eq!(
        summary["files_changed"],
        serde_json::json!(["src/db.rs", "README.md"])
    );
    assert_eq!(summary["pushed"], false);
    let sha = summary["commit_sha"].as_str().unwrap();
    assert_eq!(git(path, &["rev-parse", "HEAD"]).trim(), sha);

    let db = fs::read_to_string(path.join("src/db.rs")).unwrap();
    assert!(db.contains("WHERE name = $1"));
    assert!(!db.contains("format!"));
    let readme = fs::read_to_string(path.join("README.md")).unwrap();
    assert_eq!(readme, "# Demo\n\nRun with `cargo run --release`.\n");

    assert_eq!(
        git(path, &["log", "-1", "--format=%s"]).trim(),
        "fix: apply review"
    );
    let committed = git(path, &["show", "--name-only", "--format=", "HEAD"]);
    assert!(
        !committed.contains("review_response.json"),
        "committed: {committed}"
    );
    assert!(git(path, &["status", "--porcelain"]).contains("?? review_response.json"));
}

#[test]
fn failing_fix_leaves_tree_untouched() {
    let repo = repo();
    let path = repo.path();
    let input = fixture("conflicting_fixes.json");
    let out = run(path, &["-i", input.to_str().unwrap(), "--commit-changes"]);
    assert_eq!(out.status.code(), Some(1));
    assert!(stderr(&out).contains("Failed to apply"));
    assert!(
        git(path, &["status", "--porcelain"]).is_empty(),
        "patch must be atomic"
    );
    assert_eq!(git(path, &["rev-list", "--count", "HEAD"]).trim(), "1");
}

#[test]
fn diff_targeting_another_path_is_rejected() {
    let repo = repo();
    let input = fixture("path_escape.json");
    let out = run(
        repo.path(),
        &["-i", input.to_str().unwrap(), "--commit-changes"],
    );
    assert_eq!(out.status.code(), Some(1));
    assert!(stderr(&out).contains("different file"));
    assert!(git(repo.path(), &["status", "--porcelain"]).is_empty());
}

#[test]
fn dry_run_checks_patch_without_changing_anything() {
    let repo = repo();
    let path = repo.path();
    let input = fixture("envelope_with_fixes.json");
    let out = run(
        path,
        &[
            "-i",
            input.to_str().unwrap(),
            "--dry-run",
            "--post-comment",
            "--pr-number",
            "12",
            "--repository",
            "owner/repo",
            "--commit-changes",
            "--create-pr",
            "--branch",
            "review-fixes",
        ],
    );
    assert!(out.status.success(), "{}", stderr(&out));
    assert_eq!(
        String::from_utf8_lossy(&out.stdout).trim(),
        "https://github.com/owner/repo/pull/0"
    );
    assert!(git(path, &["status", "--porcelain"]).is_empty());
    assert_eq!(git(path, &["branch", "--show-current"]).trim(), "main");

    // A stale fix is caught even in a dry run.
    let stale = fixture("conflicting_fixes.json");
    let out = run(
        path,
        &[
            "-i",
            stale.to_str().unwrap(),
            "--dry-run",
            "--commit-changes",
        ],
    );
    assert_eq!(out.status.code(), Some(1));
}

#[test]
fn invalid_branch_name_is_rejected() {
    let repo = repo();
    let input = fixture("envelope_with_fixes.json");
    let out = run(
        repo.path(),
        &[
            "-i",
            input.to_str().unwrap(),
            "--create-pr",
            "--repository",
            "o/r",
            "--branch",
            "bad..name",
        ],
    );
    assert_eq!(out.status.code(), Some(1));
    assert!(stderr(&out).contains("Invalid branch name"));
    assert_eq!(
        git(repo.path(), &["branch", "--show-current"]).trim(),
        "main"
    );
}

#[test]
fn push_after_commit_updates_remote() {
    let repo = repo();
    let path = repo.path();
    let remote = tempfile::tempdir().unwrap();
    git(remote.path(), &["init", "-q", "--bare"]);
    git(
        path,
        &["remote", "add", "origin", remote.path().to_str().unwrap()],
    );

    let input = fixture("envelope_with_fixes.json");
    let out = run(
        path,
        &[
            "-i",
            input.to_str().unwrap(),
            "--commit-changes",
            "--push",
            "--output-format",
            "json",
        ],
    );
    assert!(out.status.success(), "{}", stderr(&out));
    let summary = stdout_json(&out);
    assert_eq!(summary["pushed"], true);
    assert_eq!(summary["branch"], "main");
    let remote_head = git(remote.path(), &["rev-parse", "refs/heads/main"]);
    assert_eq!(remote_head.trim(), summary["commit_sha"].as_str().unwrap());
}
