//! GitHub operations using gh CLI.

use anyhow::{bail, Context, Result};
use tokio::process::Command;
use tracing::{debug, info};

/// GitHub client using gh CLI.
pub struct GitHubClient {
    dry_run: bool,
}

impl GitHubClient {
    /// Create a new GitHub client.
    pub fn new(dry_run: bool) -> Self {
        Self { dry_run }
    }

    /// Run a gh command and return output.
    async fn run_gh(&self, args: &[&str]) -> Result<String> {
        if self.dry_run {
            info!("[DRY RUN] Would run: gh {}", args.join(" "));
            return Ok(String::new());
        }

        debug!("Running: gh {}", args.join(" "));

        let output = Command::new("gh")
            .args(args)
            .output()
            .await
            .context("Failed to execute gh command")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            bail!("gh command failed: {}", stderr);
        }

        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }

    /// Post a comment on a PR.
    pub async fn post_pr_comment(&self, repository: &str, pr_number: u64, body: &str) -> Result<()> {
        if self.dry_run {
            info!("[DRY RUN] Would post comment to {repository} PR #{pr_number}");
            return Ok(());
        }

        // Write body to temp file to avoid shell escaping issues
        let temp_dir = std::env::temp_dir();
        let body_file = temp_dir.join(format!("pr-comment-{}.md", std::process::id()));
        std::fs::write(&body_file, body).context("Failed to write comment body")?;

        let body_file_str = body_file
            .to_str()
            .context("Temp file path contains invalid UTF-8")?;

        let result = self
            .run_gh(&[
                "pr",
                "comment",
                &pr_number.to_string(),
                "--repo",
                repository,
                "--body-file",
                body_file_str,
            ])
            .await;

        // Clean up
        let _ = std::fs::remove_file(&body_file);

        result?;
        Ok(())
    }

    /// Create a pull request.
    pub async fn create_pr(
        &self,
        repository: &str,
        title: &str,
        body: &str,
        head: &str,
        base: &str,
    ) -> Result<(u64, String)> {
        if self.dry_run {
            info!("[DRY RUN] Would create PR: {title}");
            info!("  Head: {head}, Base: {base}");
            return Ok((0, format!("https://github.com/{repository}/pull/0")));
        }

        // Write body to temp file
        let temp_dir = std::env::temp_dir();
        let body_file = temp_dir.join(format!("pr-body-{}.md", std::process::id()));
        std::fs::write(&body_file, body).context("Failed to write PR body")?;

        let body_file_str = body_file
            .to_str()
            .context("Temp file path contains invalid UTF-8")?;

        let output = self
            .run_gh(&[
                "pr",
                "create",
                "--repo",
                repository,
                "--title",
                title,
                "--body-file",
                body_file_str,
                "--head",
                head,
                "--base",
                base,
            ])
            .await;

        // Clean up
        let _ = std::fs::remove_file(&body_file);

        let output = output?;
        let url = output.trim();

        // Extract PR number from URL (default to 0 if parsing fails)
        let pr_number = url.rsplit('/').next().and_then(|s| s.parse().ok()).unwrap_or(0);

        Ok((pr_number, url.to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_dry_run_comment() {
        let client = GitHubClient::new(true);
        let result = client
            .post_pr_comment("owner/repo", 123, "Test comment")
            .await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_dry_run_pr() {
        let client = GitHubClient::new(true);
        let result = client
            .create_pr("owner/repo", "Title", "Body", "feature", "main")
            .await;
        assert!(result.is_ok());
    }
}
