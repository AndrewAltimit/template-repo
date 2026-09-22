//! Helpers shared by `review respond` and `review failure`: temp files, PR
//! comments, git identity, verified pushes, and Claude CLI discovery.

use std::io::Write;
use std::time::Duration;

use anyhow::{Context, Result, anyhow, bail};
use tempfile::NamedTempFile;

use crate::shared::{output, process, project};

/// Timeout for a single Claude CLI invocation.
pub const CLAUDE_TIMEOUT: Duration = Duration::from_secs(20 * 60);

/// Write `content` to a temp file that is deleted when the handle is dropped
/// (including on early `?` returns).
pub fn write_temp(content: &str) -> Result<NamedTempFile> {
    let mut file = tempfile::Builder::new()
        .prefix("automation-cli-")
        .tempfile()
        .context("failed to create temp file")?;
    file.write_all(content.as_bytes())
        .context("failed to write temp file")?;
    file.flush()?;
    Ok(file)
}

/// Path of a temp file as a `&str` argument for child processes.
pub fn temp_path(file: &NamedTempFile) -> Result<&str> {
    file.path()
        .to_str()
        .ok_or_else(|| anyhow!("temp file path is not valid UTF-8"))
}

/// Post a PR comment via `gh pr comment --body-file` (retried).
/// Missing `gh` is an error in CI and a warning locally.
pub fn post_comment(pr_number: u64, body: &str) -> Result<()> {
    if !process::command_exists("gh") {
        if project::is_ci() {
            bail!("gh CLI not found in CI -- cannot post PR comment");
        }
        output::warn("gh CLI not found, skipping PR comment");
        return Ok(());
    }
    let temp = write_temp(body)?;
    let pr = pr_number.to_string();
    process::run_with_retries(
        "gh",
        &["pr", "comment", &pr, "--body-file", temp_path(&temp)?],
        3,
        2,
    )
}

/// In GitHub Actions (token + repository present), point `origin` at an
/// authenticated URL and set the commit identity.
pub fn configure_git(user_name: &str, user_email: &str) -> Result<()> {
    let token = std::env::var("GITHUB_TOKEN").unwrap_or_default();
    let repo = std::env::var("GITHUB_REPOSITORY").unwrap_or_default();
    if token.is_empty() || repo.is_empty() {
        return Ok(());
    }
    output::step("Configuring git authentication...");
    let url = format!("https://x-access-token:{token}@github.com/{repo}.git");
    process::run("git", &["remote", "set-url", "origin", &url])
        .context("failed to set authenticated origin URL")?;
    process::run("git", &["config", "user.name", user_name])?;
    process::run("git", &["config", "user.email", user_email])?;
    Ok(())
}

/// Fetch (best effort) and check out the PR branch.
pub fn checkout_branch(branch: &str) -> Result<()> {
    output::step(&format!("Checking out branch: {branch}"));
    if let Err(e) = process::run("git", &["fetch", "origin", branch]) {
        output::warn(&format!("git fetch failed, using local state: {e}"));
    }
    process::run("git", &["checkout", branch])
        .with_context(|| format!("failed to check out branch {branch}"))
}

/// Stage modifications to tracked files and report whether anything is staged.
pub fn stage_tracked_changes() -> Result<bool> {
    process::run("git", &["add", "-u"])?;
    Ok(!process::run_check(
        "git",
        &["diff", "--cached", "--quiet"],
    )?)
}

/// Commit staged changes with `message` (via `-F`, so no shell quoting issues).
pub fn commit(message: &str) -> Result<()> {
    let msg = write_temp(message)?;
    process::run("git", &["commit", "-F", temp_path(&msg)?])
}

/// Current HEAD as (full, short) SHA.
pub fn head_sha() -> Result<(String, String)> {
    let full = process::run_capture("git", &["rev-parse", "HEAD"])?
        .trim()
        .to_string();
    let short = process::run_capture("git", &["rev-parse", "--short", "HEAD"])?
        .trim()
        .to_string();
    Ok((full, short))
}

/// Locate the Claude CLI (`claude`, falling back to `claude-code`).
pub fn find_claude_cli() -> Option<&'static str> {
    ["claude", "claude-code"]
        .into_iter()
        .find(|c| process::command_exists(c))
}

/// Push `branch` and verify via `git ls-remote` that the remote ref matches.
///
/// Handles silent push failures (exit 0 but remote unchanged) and
/// non-fast-forward rejections (fetch + rebase + recompute expected SHA).
/// `--no-verify` skips local pre-push hooks, which would otherwise re-run the
/// full CI suite inside the agent job. Returns the SHA that landed.
pub fn push_and_verify(branch: &str, initial_sha: &str) -> Result<String> {
    const MAX_ATTEMPTS: u32 = 5;
    let mut last_err: Option<anyhow::Error> = None;
    let mut current_sha = initial_sha.to_string();

    for attempt in 1..=MAX_ATTEMPTS {
        output::info(&format!(
            "Push attempt {attempt}/{MAX_ATTEMPTS} (expected sha: {current_sha})"
        ));

        match push_once(branch) {
            Ok(()) => match verify_remote_head(branch, &current_sha) {
                Ok(true) => return Ok(current_sha),
                Ok(false) => {
                    output::warn("Push reported success but remote ref is stale -- retrying");
                    last_err = Some(anyhow!(
                        "push verification failed: origin/{branch} does not match {current_sha}"
                    ));
                },
                Err(e) => {
                    output::warn(&format!("Could not verify remote ref: {e}"));
                    last_err = Some(e);
                },
            },
            Err(e) => {
                let msg = format!("{e:#}");
                output::warn(&format!("Push failed: {msg}"));
                if looks_like_non_fast_forward(&msg)
                    && let Some(new_sha) = rebase_onto_remote(branch)
                {
                    current_sha = new_sha;
                    output::info(&format!("Rebased; new local HEAD = {current_sha}"));
                }
                last_err = Some(e);
            },
        }

        if attempt < MAX_ATTEMPTS {
            std::thread::sleep(Duration::from_secs(process::backoff_secs(1, attempt)));
        }
    }

    Err(last_err.unwrap_or_else(|| anyhow!("push failed: exhausted retries")))
}

/// One `git push`, echoing git's output and returning its stderr in the error
/// so the caller can classify the rejection.
fn push_once(branch: &str) -> Result<()> {
    let out = process::run_output("git", &["push", "--no-verify", "origin", branch])?;
    let stderr = String::from_utf8_lossy(&out.stderr);
    eprint!("{}", String::from_utf8_lossy(&out.stdout));
    eprint!("{stderr}");
    if out.status.success() {
        Ok(())
    } else {
        bail!("git push exited with {}: {}", out.status, stderr.trim())
    }
}

pub fn looks_like_non_fast_forward(msg: &str) -> bool {
    let lower = msg.to_lowercase();
    lower.contains("non-fast-forward")
        || lower.contains("fetch first")
        || lower.contains("updates were rejected")
}

/// Fetch the branch and rebase local onto it. Returns the new HEAD SHA on
/// success; aborts any in-progress rebase and returns None on failure so the
/// caller can retry the bare push.
fn rebase_onto_remote(branch: &str) -> Option<String> {
    output::info("Non-fast-forward detected -- fetching and rebasing");
    if process::run("git", &["fetch", "origin", branch]).is_err() {
        return None;
    }
    let remote_ref = format!("origin/{branch}");
    if process::run("git", &["rebase", &remote_ref]).is_err() {
        let _ = process::run("git", &["rebase", "--abort"]);
        output::warn("Rebase failed -- aborted, will retry bare push");
        return None;
    }
    process::run_capture("git", &["rev-parse", "HEAD"])
        .ok()
        .map(|s| s.trim().to_string())
}

fn verify_remote_head(branch: &str, expected_sha: &str) -> Result<bool> {
    let full_ref = format!("refs/heads/{branch}");
    let out = process::run_capture("git", &["ls-remote", "origin", &full_ref])?;
    let remote_sha = parse_ls_remote_sha(&out)
        .ok_or_else(|| anyhow!("ls-remote returned no ref for {branch}"))?;
    output::info(&format!("Remote origin/{branch} = {remote_sha}"));
    Ok(remote_sha == expected_sha)
}

/// Extract the branch SHA from `git ls-remote` output, preferring `refs/heads/`.
pub fn parse_ls_remote_sha(output: &str) -> Option<String> {
    output
        .lines()
        .find(|line| line.contains("refs/heads/"))
        .and_then(|line| line.split_whitespace().next())
        .map(str::to_string)
}

/// Truncate to at most `max` bytes (on a char boundary, preferring the last
/// newline) and append a marker noting the original size.
pub fn truncate_in_place(s: &mut String, max: usize) {
    if s.len() <= max {
        return;
    }
    let original_len = s.len();
    let safe_max = s.floor_char_boundary(max);
    let cut = s[..safe_max].rfind('\n').unwrap_or(safe_max);
    s.truncate(cut);
    let kept = s.len();
    s.push_str(&format!(
        "\n\n[... truncated from {original_len} to {kept} chars ...]"
    ));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_ls_remote_sha_basic() {
        let out = "abc123def456abc123def456abc123def456abcd\trefs/heads/main\n";
        assert_eq!(
            parse_ls_remote_sha(out).as_deref(),
            Some("abc123def456abc123def456abc123def456abcd")
        );
    }

    #[test]
    fn parse_ls_remote_sha_empty() {
        assert_eq!(parse_ls_remote_sha(""), None);
        assert_eq!(parse_ls_remote_sha("   \n"), None);
    }

    #[test]
    fn parse_ls_remote_sha_first_branch_line() {
        let out = "aaa\trefs/heads/feature\nbbb\trefs/heads/main\n";
        assert_eq!(parse_ls_remote_sha(out).as_deref(), Some("aaa"));
    }

    #[test]
    fn parse_ls_remote_sha_ignores_tags() {
        assert_eq!(parse_ls_remote_sha("abc123\trefs/tags/v1.0\n"), None);
    }

    #[test]
    fn non_fast_forward_detection() {
        assert!(looks_like_non_fast_forward(
            "! [rejected]        main -> main (non-fast-forward)"
        ));
        assert!(looks_like_non_fast_forward(
            "error: failed to push some refs; updates were rejected"
        ));
        assert!(looks_like_non_fast_forward(
            "hint: Updates were rejected because the tip of your current branch is behind -- fetch first"
        ));
        assert!(!looks_like_non_fast_forward(
            "fatal: unable to access: could not resolve host"
        ));
    }

    #[test]
    fn truncate_prefers_newline_and_reports_sizes() {
        let mut s = "line one\nline two\nline three".to_string();
        truncate_in_place(&mut s, 12);
        assert!(s.starts_with("line one\n\n[... truncated from 28 to 8 chars"));
    }

    #[test]
    fn truncate_noop_when_short() {
        let mut s = "short".to_string();
        truncate_in_place(&mut s, 100);
        assert_eq!(s, "short");
    }

    #[test]
    fn truncate_respects_char_boundaries() {
        let mut s = "aé".repeat(10);
        truncate_in_place(&mut s, 4);
        assert!(s.starts_with("a\u{e9}a"));
    }

    #[test]
    fn temp_file_roundtrip_and_cleanup() {
        let f = write_temp("hello").unwrap();
        let path = f.path().to_path_buf();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "hello");
        drop(f);
        assert!(!path.exists());
    }
}
