//! Git operations for applying changes.

use anyhow::{bail, Context, Result};
use tokio::process::Command;
use tracing::{debug, info};

/// Git operations wrapper.
pub struct GitOperations {
    dry_run: bool,
}

impl GitOperations {
    /// Create a new git operations instance.
    pub fn new(dry_run: bool) -> Self {
        Self { dry_run }
    }

    /// Run a git command.
    async fn run_git(&self, args: &[&str]) -> Result<String> {
        if self.dry_run {
            info!("[DRY RUN] Would run: git {}", args.join(" "));
            return Ok(String::new());
        }

        debug!("Running: git {}", args.join(" "));

        let output = Command::new("git")
            .args(args)
            .output()
            .await
            .context("Failed to execute git command")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            bail!("Git command failed: {}", stderr);
        }

        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }

    /// Create and checkout a new branch.
    pub async fn create_branch(&self, name: &str) -> Result<()> {
        self.run_git(&["checkout", "-b", name]).await?;
        Ok(())
    }

    /// Commit staged changes.
    pub async fn commit(&self, message: &str) -> Result<()> {
        // Stage all changes
        self.run_git(&["add", "-A"]).await?;

        // Check if there are changes to commit
        let status = self.run_git(&["status", "--porcelain"]).await?;
        if status.trim().is_empty() && !self.dry_run {
            info!("No changes to commit");
            return Ok(());
        }

        // Commit
        self.run_git(&["commit", "-m", message]).await?;
        Ok(())
    }

    /// Push to remote.
    pub async fn push(&self, branch: &str) -> Result<()> {
        self.run_git(&["push", "-u", "origin", branch]).await?;
        Ok(())
    }

    /// Apply a diff to a file using patch.
    pub async fn apply_diff(&self, _path: &str, diff: &str) -> Result<()> {
        if self.dry_run {
            info!("[DRY RUN] Would apply diff");
            return Ok(());
        }

        // Write diff to temp file
        let temp_dir = std::env::temp_dir();
        let diff_file = temp_dir.join(format!("review-diff-{}.patch", std::process::id()));
        std::fs::write(&diff_file, diff).context("Failed to write diff file")?;

        // Convert path to string, handling non-UTF-8 paths
        let diff_file_str = diff_file
            .to_str()
            .context("Temp file path contains invalid UTF-8")?;

        // Apply with git apply
        let result = Command::new("git")
            .args(["apply", "--check", diff_file_str])
            .output()
            .await
            .context("Failed to check diff")?;

        if !result.status.success() {
            // Try with patch command as fallback
            debug!("git apply check failed, trying patch command");
            let result = Command::new("patch")
                .args(["-p1", "--dry-run", "-i", diff_file_str])
                .output()
                .await
                .context("Failed to dry-run patch")?;

            if !result.status.success() {
                let stderr = String::from_utf8_lossy(&result.stderr);
                // Clean up before returning error
                let _ = std::fs::remove_file(&diff_file);
                bail!("Failed to apply diff: {}", stderr);
            }

            // Apply for real
            Command::new("patch")
                .args(["-p1", "-i", diff_file_str])
                .output()
                .await
                .context("Failed to apply patch")?;
        } else {
            // Apply with git
            Command::new("git")
                .args(["apply", diff_file_str])
                .output()
                .await
                .context("Failed to apply git diff")?;
        }

        // Clean up
        let _ = std::fs::remove_file(&diff_file);

        Ok(())
    }
}
