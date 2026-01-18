//! PR diff fetching and manipulation.
//!
//! Handles fetching PR diffs from git and marking files for incremental reviews.

use std::collections::HashSet;
use std::process::Command;

use crate::error::{Error, Result};

/// Maximum diff size in characters (1.5M for Gemini's large context)
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

impl PRMetadata {
    /// Load PR metadata from environment variables (GitHub Actions context)
    pub fn from_env() -> Result<Self> {
        let number = std::env::var("PR_NUMBER")
            .or_else(|_| std::env::var("GITHUB_PR_NUMBER"))
            .map_err(|_| Error::EnvNotSet("PR_NUMBER".to_string()))?
            .parse::<u64>()
            .map_err(|e| Error::Config(format!("Invalid PR_NUMBER: {}", e)))?;

        Ok(Self {
            number,
            title: std::env::var("PR_TITLE").unwrap_or_default(),
            body: std::env::var("PR_BODY").unwrap_or_default(),
            author: std::env::var("PR_AUTHOR").unwrap_or_else(|_| "unknown".to_string()),
            base_branch: std::env::var("BASE_BRANCH").unwrap_or_else(|_| "main".to_string()),
            head_branch: std::env::var("HEAD_BRANCH").unwrap_or_default(),
        })
    }

    /// Fetch PR metadata via gh CLI
    pub fn from_gh_cli(pr_number: u64) -> Result<Self> {
        let output = Command::new("gh")
            .args([
                "pr",
                "view",
                &pr_number.to_string(),
                "--json",
                "number,title,body,author,baseRefName,headRefName",
            ])
            .output()
            .map_err(|e| Error::Io(e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(Error::GhCommandFailed {
                exit_code: output.status.code().unwrap_or(-1),
                stdout: String::from_utf8_lossy(&output.stdout).to_string(),
                stderr: stderr.to_string(),
            });
        }

        let json: serde_json::Value = serde_json::from_slice(&output.stdout)?;

        Ok(Self {
            number: json["number"].as_u64().unwrap_or(pr_number),
            title: json["title"].as_str().unwrap_or("").to_string(),
            body: json["body"].as_str().unwrap_or("").to_string(),
            author: json["author"]["login"]
                .as_str()
                .unwrap_or("unknown")
                .to_string(),
            base_branch: json["baseRefName"].as_str().unwrap_or("main").to_string(),
            head_branch: json["headRefName"].as_str().unwrap_or("").to_string(),
        })
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
    /// Parse file stats from git diff --stat output
    pub fn from_git_diff(base_branch: &str) -> Result<Self> {
        let output = Command::new("git")
            .args(["diff", "--stat", &format!("origin/{}...HEAD", base_branch)])
            .output()
            .map_err(|e| Error::Io(e))?;

        if !output.status.success() {
            return Ok(Self::default());
        }

        let stat_output = String::from_utf8_lossy(&output.stdout);
        let mut stats = Self::default();

        // Parse the summary line: "X files changed, Y insertions(+), Z deletions(-)"
        for line in stat_output.lines() {
            if line.contains("files changed") || line.contains("file changed") {
                // Extract numbers using simple parsing
                let parts: Vec<&str> = line.split_whitespace().collect();
                for (i, part) in parts.iter().enumerate() {
                    if *part == "file" || *part == "files" {
                        if i > 0 {
                            stats.files_changed = parts[i - 1].parse().unwrap_or(0);
                        }
                    } else if part.contains("insertion") {
                        if i > 0 {
                            stats.lines_added = parts[i - 1].parse().unwrap_or(0);
                        }
                    } else if part.contains("deletion") {
                        if i > 0 {
                            stats.lines_deleted = parts[i - 1].parse().unwrap_or(0);
                        }
                    }
                }
            }
        }

        Ok(stats)
    }
}

/// Get the current commit SHA
pub fn get_current_commit_sha() -> Result<String> {
    let output = Command::new("git")
        .args(["rev-parse", "HEAD"])
        .output()
        .map_err(|e| Error::Io(e))?;

    if !output.status.success() {
        return Err(Error::GitCommandFailed {
            exit_code: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
        });
    }

    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

/// Get the full PR diff
pub fn get_pr_diff(base_branch: &str) -> Result<String> {
    let output = Command::new("git")
        .args(["diff", &format!("origin/{}...HEAD", base_branch)])
        .output()
        .map_err(|e| Error::Io(e))?;

    if !output.status.success() {
        return Err(Error::GitCommandFailed {
            exit_code: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
        });
    }

    let diff = String::from_utf8_lossy(&output.stdout).to_string();

    // Truncate if too large
    if diff.len() > MAX_DIFF_CHARS {
        let truncated = &diff[..MAX_DIFF_CHARS];
        // Find last newline to avoid splitting mid-line
        if let Some(pos) = truncated.rfind('\n') {
            return Ok(format!(
                "{}\n\n[DIFF TRUNCATED - {} chars exceeded {} limit]",
                &truncated[..pos],
                diff.len(),
                MAX_DIFF_CHARS
            ));
        }
    }

    Ok(diff)
}

/// Get list of changed files
pub fn get_changed_files(base_branch: &str) -> Result<Vec<String>> {
    let output = Command::new("git")
        .args([
            "diff",
            "--name-only",
            &format!("origin/{}...HEAD", base_branch),
        ])
        .output()
        .map_err(|e| Error::Io(e))?;

    if !output.status.success() {
        return Ok(Vec::new());
    }

    Ok(String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(|s| s.to_string())
        .collect())
}

/// Get files changed since a specific commit
pub fn get_files_changed_since_commit(since_commit: &str) -> Result<Vec<String>> {
    let output = Command::new("git")
        .args(["diff", "--name-only", &format!("{}...HEAD", since_commit)])
        .output()
        .map_err(|e| Error::Io(e))?;

    if !output.status.success() {
        // May fail for shallow clones or if commit doesn't exist
        return Ok(Vec::new());
    }

    Ok(String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(|s| s.to_string())
        .collect())
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

        // Check if this is a diff header: "diff --git a/path b/path"
        if line.starts_with("diff --git a/") {
            // Extract the file path from the header
            // Format: "diff --git a/path b/path" or "diff --git a/old b/new"
            if let Some(b_pos) = line.rfind(" b/") {
                let file_path = &line[b_pos + 3..];
                if new_files.contains(file_path) {
                    result.push_str("[NEW SINCE LAST REVIEW]\n");
                }
            }
        }
    }

    result
}

/// Read file content (for verification)
pub fn read_file_content(filepath: &str, max_chars: usize) -> Result<String> {
    let content = std::fs::read_to_string(filepath).map_err(|e| Error::Io(e))?;

    if content.len() > max_chars {
        Ok(content[..max_chars].to_string())
    } else {
        Ok(content)
    }
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
        assert!(marked.contains("[NEW SINCE LAST REVIEW]"));
        // Should only mark main.rs, not lib.rs
        assert_eq!(marked.matches("[NEW SINCE LAST REVIEW]").count(), 1);
    }
}
