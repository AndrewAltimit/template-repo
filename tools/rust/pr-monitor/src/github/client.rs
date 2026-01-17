//! GitHub API client using `gh` CLI

use chrono::{DateTime, Utc};
use std::process::Command;

use crate::error::{Error, Result};
use crate::github::types::{Comment, PrCommentsResponse};

/// GitHub client using the `gh` CLI for API access
pub struct GhClient;

impl GhClient {
    /// Get all comments for a PR
    pub fn get_pr_comments(pr_number: u32) -> Result<Vec<Comment>> {
        let output = Command::new("gh")
            .args(["pr", "view", &pr_number.to_string()])
            .args(["--json", "comments"])
            .output()?;

        if !output.status.success() {
            return Err(Error::GhFailed {
                code: output.status.code().unwrap_or(-1),
                stderr: String::from_utf8_lossy(&output.stderr).trim().to_string(),
            });
        }

        let response: PrCommentsResponse = serde_json::from_slice(&output.stdout)?;
        Ok(response.comments)
    }

    /// Get comment count for a PR (more efficient than getting all comments)
    pub fn get_comment_count(pr_number: u32) -> Result<usize> {
        let output = Command::new("gh")
            .args(["pr", "view", &pr_number.to_string()])
            .args(["--json", "comments"])
            .args(["--jq", ".comments | length"])
            .output()?;

        if !output.status.success() {
            return Err(Error::GhFailed {
                code: output.status.code().unwrap_or(-1),
                stderr: String::from_utf8_lossy(&output.stderr).trim().to_string(),
            });
        }

        let count_str = String::from_utf8_lossy(&output.stdout);
        count_str.trim().parse::<usize>().map_err(|e| {
            Error::JsonParse(serde_json::Error::io(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                format!("Failed to parse comment count: {}", e),
            )))
        })
    }

    /// Check if gh CLI is available and authenticated
    pub fn check_available() -> Result<()> {
        let output = Command::new("gh").args(["auth", "status"]).output()?;

        if !output.status.success() {
            return Err(Error::GhFailed {
                code: output.status.code().unwrap_or(-1),
                stderr: String::from_utf8_lossy(&output.stderr).trim().to_string(),
            });
        }
        Ok(())
    }

    /// Get commit timestamp for filtering
    pub fn get_commit_time(sha: &str) -> Result<DateTime<Utc>> {
        let output = Command::new("gh")
            .args(["api", &format!("repos/:owner/:repo/commits/{}", sha)])
            .args(["--jq", ".commit.committer.date"])
            .output()?;

        if !output.status.success() {
            return Err(Error::CommitLookup {
                sha: sha.to_string(),
                reason: String::from_utf8_lossy(&output.stderr).trim().to_string(),
            });
        }

        let time_str = String::from_utf8_lossy(&output.stdout);
        let time_str = time_str.trim().trim_matches('"');

        DateTime::parse_from_rfc3339(time_str)
            .map(|dt| dt.with_timezone(&Utc))
            .map_err(|e| Error::TimestampParse {
                timestamp: time_str.to_string(),
                reason: e.to_string(),
            })
    }
}
