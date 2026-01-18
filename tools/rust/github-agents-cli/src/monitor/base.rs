//! Base monitor trait and common functionality.
//!
//! Provides the core monitoring infrastructure used by issue and PR monitors.

use std::env;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use tokio::time::sleep;
use tracing::{info, warn};

use crate::error::Error;
use crate::security::SecurityManager;
use crate::utils::{check_gh_available, run_gh_command};

/// Base trait for monitors.
///
/// Monitors watch GitHub issues or PRs for triggers and process them accordingly.
#[async_trait::async_trait]
pub trait Monitor: Send + Sync {
    /// Process items once.
    async fn process_items(&self) -> Result<(), Error>;

    /// Run continuously with the given interval.
    async fn run_continuous(&self, interval_secs: u64) -> Result<(), Error>;

    /// Get the monitor name for logging.
    fn name(&self) -> &str;
}

/// Common configuration for monitors.
#[derive(Debug, Clone)]
pub struct MonitorConfig {
    /// Repository in format "owner/repo"
    pub repository: String,
    /// Whether to run in review-only mode
    pub review_only_mode: bool,
    /// Review depth ("standard", "detailed", etc.)
    pub review_depth: String,
    /// Comment style ("individual", "consolidated", "summary")
    pub comment_style: String,
    /// Target issue numbers (empty = all)
    pub target_issue_numbers: Vec<i64>,
    /// Target PR numbers (empty = all)
    pub target_pr_numbers: Vec<i64>,
}

impl Default for MonitorConfig {
    fn default() -> Self {
        Self {
            repository: env::var("GITHUB_REPOSITORY").unwrap_or_default(),
            review_only_mode: env::var("REVIEW_ONLY_MODE")
                .map(|v| v.to_lowercase() == "true")
                .unwrap_or(false),
            review_depth: env::var("REVIEW_DEPTH").unwrap_or_else(|_| "standard".to_string()),
            comment_style: env::var("COMMENT_STYLE").unwrap_or_else(|_| "consolidated".to_string()),
            target_issue_numbers: parse_target_numbers(
                &env::var("TARGET_ISSUE_NUMBERS").unwrap_or_default(),
            ),
            target_pr_numbers: parse_target_numbers(
                &env::var("TARGET_PR_NUMBERS").unwrap_or_default(),
            ),
        }
    }
}

/// Parse comma-separated numbers from a string.
fn parse_target_numbers(s: &str) -> Vec<i64> {
    s.split(',').filter_map(|n| n.trim().parse().ok()).collect()
}

/// Base monitor implementation providing common functionality.
pub struct BaseMonitor {
    /// Configuration
    pub config: MonitorConfig,
    /// Security manager
    pub security_manager: SecurityManager,
    /// Running flag for graceful shutdown
    pub running: Arc<AtomicBool>,
    /// Agent tag for comments
    pub agent_tag: String,
}

impl BaseMonitor {
    /// Create a new base monitor.
    pub fn new(running: Arc<AtomicBool>) -> Result<Self, Error> {
        let config = MonitorConfig::default();

        if config.repository.is_empty() {
            return Err(Error::EnvNotSet("GITHUB_REPOSITORY".to_string()));
        }

        Ok(Self {
            config,
            security_manager: SecurityManager::new(),
            running,
            agent_tag: "[AI Agent]".to_string(),
        })
    }

    /// Check if the monitor should continue running.
    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }

    /// Check if an item should be processed based on target filters.
    pub fn should_process_item(&self, item_number: i64, item_type: &str) -> bool {
        match item_type {
            "issue" => {
                self.config.target_issue_numbers.is_empty()
                    || self.config.target_issue_numbers.contains(&item_number)
            }
            "pr" => {
                self.config.target_pr_numbers.is_empty()
                    || self.config.target_pr_numbers.contains(&item_number)
            }
            _ => true,
        }
    }

    /// Post a comment to an issue or PR.
    pub async fn post_comment(
        &self,
        item_number: i64,
        comment: &str,
        item_type: &str,
    ) -> Result<(), Error> {
        run_gh_command(
            &[
                item_type,
                "comment",
                &item_number.to_string(),
                "--repo",
                &self.config.repository,
                "--body",
                comment,
            ],
            true,
        )
        .await?;
        Ok(())
    }

    /// Post a security rejection comment.
    pub async fn post_security_rejection(
        &self,
        item_number: i64,
        reason: &str,
        item_type: &str,
    ) -> Result<(), Error> {
        let comment = format!(
            "{} Security Notice\n\n\
            This request was blocked: {}\n\n\
            {}\n\n\
            *This is an automated security measure.*",
            self.agent_tag,
            reason,
            self.security_manager.reject_message()
        );
        self.post_comment(item_number, &comment, item_type).await
    }

    /// Post an error comment.
    pub async fn post_error_comment(
        &self,
        item_number: i64,
        error: &str,
        item_type: &str,
    ) -> Result<(), Error> {
        let comment = format!(
            "{} Error\n\n\
            An error occurred: {}\n\n\
            *This comment was generated by the AI agent automation system.*",
            self.agent_tag, error
        );
        self.post_comment(item_number, &comment, item_type).await
    }

    /// Run continuous monitoring with the given process function.
    pub async fn run_continuous_impl<F, Fut>(
        &self,
        process_fn: F,
        interval_secs: u64,
        monitor_name: &str,
    ) -> Result<(), Error>
    where
        F: Fn() -> Fut,
        Fut: std::future::Future<Output = Result<(), Error>>,
    {
        let interval = Duration::from_secs(interval_secs);

        while self.is_running() {
            match process_fn().await {
                Ok(()) => {
                    info!(
                        "{} cycle completed, sleeping for {}s",
                        monitor_name, interval_secs
                    );
                }
                Err(Error::Interrupted) => {
                    info!("{} interrupted", monitor_name);
                    return Ok(());
                }
                Err(e) => {
                    warn!("{} error (will retry): {}", monitor_name, e);
                }
            }

            // Sleep in small increments to check for interruption
            let mut remaining = interval;
            while remaining > Duration::ZERO && self.is_running() {
                let sleep_time = remaining.min(Duration::from_secs(1));
                sleep(sleep_time).await;
                remaining = remaining.saturating_sub(Duration::from_secs(1));
            }
        }

        info!("{} stopped", monitor_name);
        Ok(())
    }

    /// Ensure GitHub CLI is available.
    pub async fn ensure_gh_available(&self) -> Result<(), Error> {
        check_gh_available().await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_target_numbers() {
        assert_eq!(parse_target_numbers("1,2,3"), vec![1, 2, 3]);
        assert_eq!(parse_target_numbers("1, 2, 3"), vec![1, 2, 3]);
        assert_eq!(parse_target_numbers(""), Vec::<i64>::new());
        assert_eq!(parse_target_numbers("invalid"), Vec::<i64>::new());
        assert_eq!(parse_target_numbers("1,invalid,3"), vec![1, 3]);
    }

    #[test]
    fn test_monitor_config_default() {
        // Clear env vars for predictable test
        // SAFETY: Tests run serially and don't access these vars concurrently
        unsafe {
            env::remove_var("REVIEW_ONLY_MODE");
            env::remove_var("REVIEW_DEPTH");
            env::remove_var("COMMENT_STYLE");
        }

        let config = MonitorConfig::default();
        assert!(!config.review_only_mode);
        assert_eq!(config.review_depth, "standard");
        assert_eq!(config.comment_style, "consolidated");
    }
}
