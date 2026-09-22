//! PR diff fetching and manipulation.
//!
//! Handles fetching PR diffs from git and marking files for incremental reviews.

use std::collections::HashSet;
use std::process::Command;

use crate::error::{Error, Result};
use crate::security::commit::is_valid_sha;
use crate::utils::text::truncate_at_line_boundary;

/// Maximum diff size in bytes kept in memory before prompt-level truncation.
const MAX_DIFF_CHARS: usize = 1_500_000;

/// PR metadata
#[derive(Debug, Clone)]
pub struct PRMetadata {
    pub number: u64,
    pub title: String,
    pub body: String,
    pub author: String,
    pub base_branch: String,
    pub head_branch: String,
}

/// Validate a branch name before interpolating it into a git revision range.
fn validate_branch(branch: &str) -> Result<&str> {
    let ok = !branch.is_empty()
        && !branch.starts_with('-')
        && !branch.contains("..")
        && !branch.chars().any(|c| c.is_whitespace() || c.is_control());
    if ok {
        Ok(branch)
    } else {
        Err(Error::Config(format!(
            "Refusing unsafe branch name: {:?}",
            branch
        )))
    }
}

/// Run `git args...`, returning stdout or a `GitCommandFailed` error.
fn git(args: &[&str]) -> Result<String> {
    let output = Command::new("git").args(args).output().map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            Error::GitNotFound
        } else {
            Error::Io(e)
        }
    })?;
    if !output.status.success() {
        return Err(Error::GitCommandFailed {
            exit_code: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
            stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
        });
    }
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}

impl PRMetadata {
    /// Fetch PR metadata via gh CLI
    pub fn from_gh_cli(pr_number: u64) -> Result<Self> {
        let mut args = vec![
            "pr".to_string(),
            "view".to_string(),
            pr_number.to_string(),
            "--json".to_string(),
            "number,title,body,author,baseRefName,headRefName".to_string(),
        ];
        if let Ok(repo) = std::env::var("GITHUB_REPOSITORY")
            && !repo.is_empty()
        {
            args.push("--repo".to_string());
            args.push(repo);
        }

        let output = Command::new("gh").args(&args).output().map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                Error::GhNotFound
            } else {
                Error::Io(e)
            }
        })?;

        if !output.status.success() {
            return Err(Error::GhCommandFailed {
                exit_code: output.status.code().unwrap_or(-1),
                stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
                stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
            });
        }

        let json: serde_json::Value = serde_json::from_slice(&output.stdout)?;
        Ok(Self::from_json(&json, pr_number))
    }

    fn from_json(json: &serde_json::Value, pr_number: u64) -> Self {
        let s = |v: &serde_json::Value, d: &str| v.as_str().unwrap_or(d).to_string();
        Self {
            number: json["number"].as_u64().unwrap_or(pr_number),
            title: s(&json["title"], ""),
            body: s(&json["body"], ""),
            author: s(&json["author"]["login"], "unknown"),
            base_branch: s(&json["baseRefName"], "main"),
            head_branch: s(&json["headRefName"], ""),
        }
    }
}

/// File statistics for a PR
#[derive(Debug, Clone, Default)]
pub struct FileStats {
    pub files_changed: usize,
    pub lines_added: usize,
    pub lines_deleted: usize,
}

impl FileStats {
    /// Compute file stats with `git diff --shortstat` against the base branch.
    pub fn from_git_diff(base_branch: &str) -> Result<Self> {
        let range = format!("origin/{}...HEAD", validate_branch(base_branch)?);
        match git(&["diff", "--shortstat", &range]) {
            Ok(out) => Ok(Self::parse_shortstat(&out)),
            Err(e) => {
                tracing::warn!("Could not compute diff stats: {}", e);
                Ok(Self::default())
            },
        }
    }

    /// Parse "X files changed, Y insertions(+), Z deletions(-)".
    fn parse_shortstat(output: &str) -> Self {
        let mut stats = Self::default();
        for part in output.split(',') {
            let mut words = part.split_whitespace();
            let (Some(num), Some(label)) = (words.next(), words.next()) else {
                continue;
            };
            let Ok(n) = num.parse::<usize>() else {
                continue;
            };
            if label.starts_with("file") {
                stats.files_changed = n;
            } else if label.starts_with("insertion") {
                stats.lines_added = n;
            } else if label.starts_with("deletion") {
                stats.lines_deleted = n;
            }
        }
        stats
    }
}

/// Get the current commit SHA
pub fn get_current_commit_sha() -> Result<String> {
    Ok(git(&["rev-parse", "HEAD"])?.trim().to_string())
}

/// Get the full PR diff (truncated at a line boundary if enormous)
pub fn get_pr_diff(base_branch: &str) -> Result<String> {
    let range = format!("origin/{}...HEAD", validate_branch(base_branch)?);
    let diff = git(&["diff", &range])?;

    if diff.len() > MAX_DIFF_CHARS {
        return Ok(format!(
            "{}\n\n[DIFF TRUNCATED - {} chars exceeded {} limit]",
            truncate_at_line_boundary(&diff, MAX_DIFF_CHARS),
            diff.len(),
            MAX_DIFF_CHARS
        ));
    }
    Ok(diff)
}

/// Get list of changed files (empty on failure)
pub fn get_changed_files(base_branch: &str) -> Result<Vec<String>> {
    let range = format!("origin/{}...HEAD", validate_branch(base_branch)?);
    Ok(git(&["diff", "--name-only", &range])
        .map(|out| out.lines().map(str::to_string).collect())
        .unwrap_or_default())
}

/// Get files changed since a specific commit.
///
/// `since_commit` must be a hex SHA; anything else (including option-like
/// strings such as `--output=...`) is rejected before reaching git.
pub fn get_files_changed_since_commit(since_commit: &str) -> Result<Vec<String>> {
    if !is_valid_sha(since_commit) {
        return Err(Error::Config(format!(
            "Refusing invalid commit reference: {:?}",
            since_commit
        )));
    }
    let range = format!("{}...HEAD", since_commit);
    // May fail for shallow clones or unknown commits: treat as "no info"
    Ok(git(&["diff", "--name-only", &range])
        .map(|out| out.lines().map(str::to_string).collect())
        .unwrap_or_default())
}

/// Mark new files in a diff for incremental review
pub fn mark_new_changes_in_diff(full_diff: &str, new_files: &HashSet<String>) -> String {
    if new_files.is_empty() {
        return full_diff.to_string();
    }

    let mut result = String::with_capacity(full_diff.len() + new_files.len() * 50);

    for line in full_diff.lines() {
        result.push_str(line);
        result.push('\n');

        // Diff header: "diff --git a/path b/path"
        if line.starts_with("diff --git a/")
            && let Some(b_pos) = line.rfind(" b/")
            && new_files.contains(&line[b_pos + 3..])
        {
            result.push_str("[NEW SINCE LAST REVIEW]\n");
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mark_new_changes() {
        let diff = r#"diff --git a/src/main.rs b/src/main.rs
index abc..def 100644
--- a/src/main.rs
+++ b/src/main.rs
@@ -1,3 +1,4 @@
+// New line
 fn main() {
diff --git a/src/lib.rs b/src/lib.rs
index 123..456 100644
--- a/src/lib.rs
+++ b/src/lib.rs
"#;

        let mut new_files = HashSet::new();
        new_files.insert("src/main.rs".to_string());

        let marked = mark_new_changes_in_diff(diff, &new_files);
        assert_eq!(marked.matches("[NEW SINCE LAST REVIEW]").count(), 1);
    }

    #[test]
    fn test_parse_shortstat() {
        let s = FileStats::parse_shortstat(" 3 files changed, 10 insertions(+), 2 deletions(-)\n");
        assert_eq!(
            (s.files_changed, s.lines_added, s.lines_deleted),
            (3, 10, 2)
        );
        let s = FileStats::parse_shortstat(" 1 file changed, 1 deletion(-)");
        assert_eq!((s.files_changed, s.lines_added, s.lines_deleted), (1, 0, 1));
        let s = FileStats::parse_shortstat("");
        assert_eq!(s.files_changed, 0);
    }

    #[test]
    fn test_rejects_option_injection() {
        assert!(get_files_changed_since_commit("--output=/tmp/pwned").is_err());
        assert!(validate_branch("--output=x").is_err());
        assert!(validate_branch("main..x").is_err());
        assert!(validate_branch("feature/abc-1").is_ok());
    }

    #[test]
    fn test_metadata_from_json() {
        let json = serde_json::json!({
            "number": 7,
            "title": "T",
            "author": {"login": "u"},
            "baseRefName": "develop"
        });
        let m = PRMetadata::from_json(&json, 1);
        assert_eq!(m.number, 7);
        assert_eq!(m.author, "u");
        assert_eq!(m.base_branch, "develop");
        assert_eq!(m.body, "");
    }
}
