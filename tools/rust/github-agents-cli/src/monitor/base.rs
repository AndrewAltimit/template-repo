//! Base monitor trait and common functionality.
//!
//! Provides the shared trigger pipeline used by the issue and PR monitors:
//!
//! 1. Find the latest trigger from an allow-listed user (ignoring quoted,
//!    code and tool-generated content).
//! 2. Skip it if a monitor reply already follows it (idempotency).
//! 3. Run the full security check (action allow-list, repository, rate limit).
//! 4. Dispatch to the monitor-specific handler, which replies with a comment
//!    carrying [`TRIGGER_RESPONSE_MARKER`].

use std::env;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use chrono::{DateTime, Utc};
use serde::Deserialize;
use tokio::sync::OnceCell;
use tokio::time::sleep;
use tracing::{info, warn};

use crate::agents::AgentRegistry;
use crate::error::Error;
use crate::security::{
    AGENT_COMMENT_MARKER, CommentView, SecurityManager, TRIGGER_RESPONSE_MARKER, TriggerInfo,
    neutralize_triggers,
};
use crate::utils::text::truncate_with_suffix;
use crate::utils::{authenticated_login, check_gh_available, post_comment};

/// Maximum bytes of agent output posted in a single comment (GitHub's limit
/// is 65536 characters; leave room for the wrapper text).
pub const MAX_AGENT_OUTPUT_BYTES: usize = 60_000;

/// How far back (by last update) monitors look for triggers.
pub const LOOKBACK_HOURS: i64 = 24;

/// Base trait for monitors.
#[async_trait::async_trait]
pub trait Monitor: Send + Sync {
    /// Process items once.
    async fn process_items(&self) -> Result<(), Error>;

    /// Run continuously with the given interval.
    async fn run_continuous(&self, interval_secs: u64) -> Result<(), Error>;
}

/// Kind of GitHub item being monitored.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ItemKind {
    Issue,
    Pr,
}

impl ItemKind {
    /// `gh` subcommand for this kind.
    pub fn gh(self) -> &'static str {
        match self {
            ItemKind::Issue => "issue",
            ItemKind::Pr => "pr",
        }
    }

    /// Display label.
    pub fn label(self) -> &'static str {
        match self {
            ItemKind::Issue => "Issue",
            ItemKind::Pr => "PR",
        }
    }
}

/// Author information from `gh --json`.
#[derive(Debug, Clone, Deserialize)]
pub struct Author {
    pub login: String,
}

/// Label information from `gh --json`.
#[derive(Debug, Clone, Deserialize)]
pub struct Label {
    pub name: String,
}

/// Comment information from `gh --json comments`.
#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GhComment {
    #[serde(default)]
    pub body: String,
    pub author: Option<Author>,
    pub created_at: Option<String>,
}

/// Parse an RFC 3339 timestamp; malformed values are `None`.
pub fn parse_time(s: Option<&str>) -> Option<DateTime<Utc>> {
    s.and_then(|s| s.parse().ok())
}

/// Convert raw comments into views used by the security manager.
pub fn comment_views(comments: Option<&[GhComment]>) -> Vec<CommentView> {
    comments
        .unwrap_or_default()
        .iter()
        .map(|c| CommentView {
            body: c.body.clone(),
            author: c
                .author
                .as_ref()
                .map(|a| a.login.clone())
                .unwrap_or_default(),
            created_at: parse_time(c.created_at.as_deref()),
        })
        .collect()
}

/// Whether an item's last activity falls within the lookback window.
/// Unparseable timestamps are treated as old, never as new.
pub fn is_recent(updated_at: Option<&str>, created_at: &str, now: DateTime<Utc>) -> bool {
    let ts = parse_time(updated_at).or_else(|| parse_time(Some(created_at)));
    ts.is_some_and(|t| t >= now - chrono::Duration::hours(LOOKBACK_HOURS))
}

/// Common configuration for monitors.
#[derive(Debug, Clone)]
pub struct MonitorConfig {
    /// Repository in format "owner/repo" (`GITHUB_REPOSITORY`)
    pub repository: String,
    /// Only reviews/summaries; implementation requests are refused (`REVIEW_ONLY_MODE`)
    pub review_only_mode: bool,
    /// Target issue numbers, empty = all (`TARGET_ISSUE_NUMBERS`)
    pub target_issue_numbers: Vec<u64>,
    /// Target PR numbers, empty = all (`TARGET_PR_NUMBERS`)
    pub target_pr_numbers: Vec<u64>,
}

impl MonitorConfig {
    /// Load from environment variables.
    pub fn from_env() -> Self {
        Self {
            repository: env::var("GITHUB_REPOSITORY").unwrap_or_default(),
            review_only_mode: env::var("REVIEW_ONLY_MODE")
                .map(|v| v.eq_ignore_ascii_case("true"))
                .unwrap_or(false),
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
fn parse_target_numbers(s: &str) -> Vec<u64> {
    s.split(',').filter_map(|n| n.trim().parse().ok()).collect()
}

/// Base monitor implementation providing common functionality.
pub struct BaseMonitor {
    pub config: MonitorConfig,
    pub security_manager: SecurityManager,
    pub running: Arc<AtomicBool>,
    pub agent_registry: AgentRegistry,
    /// Visible prefix for monitor replies
    pub agent_tag: String,
    /// Login `gh` is authenticated as (resolved lazily, once)
    agent_login: OnceCell<Option<String>>,
}

impl BaseMonitor {
    /// Create a new base monitor.
    ///
    /// Loads the security configuration from `AGENTS_CONFIG_PATH` or
    /// `.agents.yaml`. A config file that exists but cannot be parsed is a
    /// hard error (fail secure) rather than a silent fallback to defaults.
    pub fn new(running: Arc<AtomicBool>) -> Result<Self, Error> {
        let config = MonitorConfig::from_env();
        if config.repository.is_empty() {
            return Err(Error::EnvNotSet("GITHUB_REPOSITORY".to_string()));
        }

        Ok(Self {
            config,
            security_manager: load_security_manager()?,
            running,
            agent_registry: AgentRegistry::new(),
            agent_tag: crate::security::trigger::LEGACY_AGENT_PREFIX.to_string(),
            agent_login: OnceCell::new(),
        })
    }

    /// Check if the monitor should continue running.
    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }

    /// Check if an item should be processed based on target filters.
    pub fn should_process_item(&self, number: u64, kind: ItemKind) -> bool {
        let targets = match kind {
            ItemKind::Issue => &self.config.target_issue_numbers,
            ItemKind::Pr => &self.config.target_pr_numbers,
        };
        targets.is_empty() || targets.contains(&number)
    }

    async fn agent_login(&self) -> Option<&str> {
        self.agent_login
            .get_or_init(authenticated_login)
            .await
            .as_deref()
    }

    /// Find an authorized, unhandled trigger and run the security checks.
    ///
    /// Returns `Ok(None)` when there is nothing to do (no trigger, already
    /// handled, or rejected - in which case a rejection reply was posted).
    pub async fn resolve_trigger(
        &self,
        kind: ItemKind,
        number: u64,
        body: &str,
        author: &str,
        created_at: Option<DateTime<Utc>>,
        comments: &[CommentView],
    ) -> Result<Option<TriggerInfo>, Error> {
        let Some(trigger) = self
            .security_manager
            .check_trigger_comment(body, author, created_at, comments)
        else {
            return Ok(None);
        };

        if self
            .security_manager
            .is_trigger_handled(&trigger, comments, self.agent_login().await)
        {
            tracing::debug!(
                "{} #{}: [{}] by {} already handled",
                kind.label(),
                number,
                trigger.action,
                trigger.username
            );
            return Ok(None);
        }

        info!(
            "{} #{}: [{}][{}] by {}",
            kind.label(),
            number,
            trigger.action,
            trigger.agent.as_deref().unwrap_or("auto"),
            trigger.username
        );

        let action = format!("{}_{}", kind.gh(), trigger.action);
        let (allowed, reason) = self.security_manager.perform_full_security_check(
            &trigger.username,
            &action,
            &self.config.repository,
        );
        if !allowed {
            warn!(
                "Security check failed for {} #{}: {}",
                kind.label(),
                number,
                reason
            );
            self.post_security_rejection(kind, number, &reason).await?;
            return Ok(None);
        }

        Ok(Some(trigger))
    }

    /// Post a monitor reply (tag prefix + hidden markers).
    pub async fn reply(&self, kind: ItemKind, number: u64, text: &str) -> Result<(), Error> {
        let body = format!(
            "{} {}\n\n*This comment was generated by the AI agent automation system.*\n{}\n{}",
            self.agent_tag, text, AGENT_COMMENT_MARKER, TRIGGER_RESPONSE_MARKER
        );
        post_comment(kind.gh(), number, &self.config.repository, &body).await
    }

    /// Post untrusted agent output: neutralized, truncated, clearly labeled.
    pub async fn post_agent_output(
        &self,
        kind: ItemKind,
        number: u64,
        heading: &str,
        output: &str,
    ) -> Result<(), Error> {
        let safe = neutralize_triggers(&truncate_with_suffix(
            output,
            MAX_AGENT_OUTPUT_BYTES,
            "...\n\n*Response truncated due to length.*",
        ));
        self.reply(kind, number, &format!("**{}**\n\n{}\n\n---", heading, safe))
            .await
    }

    /// Post a user-facing description of an agent failure.
    pub async fn post_agent_error(
        &self,
        kind: ItemKind,
        number: u64,
        agent_display: &str,
        error: &Error,
    ) -> Result<(), Error> {
        let detail = match error {
            Error::AgentTimeout { timeout, .. } => {
                format!("The agent timed out after {} seconds.", timeout)
            },
            Error::AgentExecutionFailed { stderr, .. } => format!(
                "Agent execution failed:\n```\n{}\n```",
                truncate_with_suffix(stderr, 500, "...")
            ),
            Error::AgentNotAvailable { reason, .. } => {
                format!("Agent is not available: {}", reason)
            },
            other => format!("An error occurred: {}", other),
        };
        self.reply(
            kind,
            number,
            &format!(
                "**Error from {}**\n\n{}\n\nPlease try again or use a different agent.",
                agent_display,
                neutralize_triggers(&detail)
            ),
        )
        .await
    }

    /// Post a security rejection reply.
    pub async fn post_security_rejection(
        &self,
        kind: ItemKind,
        number: u64,
        reason: &str,
    ) -> Result<(), Error> {
        self.reply(
            kind,
            number,
            &format!(
                "**Security Notice**\n\nThis request was blocked: {}\n\n{}",
                reason,
                self.security_manager.reject_message()
            ),
        )
        .await
    }

    /// Close an issue or PR.
    pub async fn close_item(
        &self,
        kind: ItemKind,
        number: u64,
        username: &str,
    ) -> Result<(), Error> {
        info!("Closing {} #{}", kind.label(), number);
        crate::utils::run_gh_command(
            &[
                kind.gh(),
                "close",
                &number.to_string(),
                "--repo",
                &self.config.repository,
            ],
            true,
        )
        .await?;
        self.reply(
            kind,
            number,
            &format!("{} closed as requested by {}.", kind.label(), username),
        )
        .await
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
        let interval = Duration::from_secs(interval_secs.max(1));

        while self.is_running() {
            match process_fn().await {
                Ok(()) => info!(
                    "{} cycle completed, sleeping for {}s",
                    monitor_name,
                    interval.as_secs()
                ),
                Err(Error::Interrupted) => {
                    info!("{} interrupted", monitor_name);
                    return Ok(());
                },
                Err(e) => warn!("{} error (will retry): {}", monitor_name, e),
            }

            // Sleep in small increments to react quickly to Ctrl+C
            let deadline = tokio::time::Instant::now() + interval;
            while self.is_running() && tokio::time::Instant::now() < deadline {
                sleep(Duration::from_millis(500)).await;
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

/// Load the security manager from `AGENTS_CONFIG_PATH` / `.agents.yaml`,
/// falling back to defaults only when no config file exists.
fn load_security_manager() -> Result<SecurityManager, Error> {
    let config_path = env::var("AGENTS_CONFIG_PATH")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| std::path::PathBuf::from(".agents.yaml"));

    if !config_path.exists() {
        info!(
            "No security config at {}, using defaults",
            config_path.display()
        );
        return Ok(SecurityManager::new());
    }

    let manager = SecurityManager::from_config_path(&config_path).map_err(|e| {
        Error::Config(format!(
            "Failed to load security config from {}: {}",
            config_path.display(),
            e
        ))
    })?;
    info!("Loaded security config from {}", config_path.display());
    Ok(manager)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_target_numbers() {
        assert_eq!(parse_target_numbers("1,2,3"), vec![1, 2, 3]);
        assert_eq!(parse_target_numbers("1, 2, 3"), vec![1, 2, 3]);
        assert_eq!(parse_target_numbers(""), Vec::<u64>::new());
        assert_eq!(parse_target_numbers("invalid"), Vec::<u64>::new());
        assert_eq!(parse_target_numbers("1,invalid,3,-4"), vec![1, 3]);
    }

    #[test]
    fn test_is_recent() {
        let now: DateTime<Utc> = "2026-01-10T00:00:00Z".parse().unwrap();
        assert!(is_recent(
            Some("2026-01-09T12:00:00Z"),
            "2020-01-01T00:00:00Z",
            now
        ));
        assert!(!is_recent(
            Some("2026-01-08T00:00:00Z"),
            "2026-01-08T00:00:00Z",
            now
        ));
        // Falls back to created_at when updated_at is missing
        assert!(is_recent(None, "2026-01-09T23:00:00Z", now));
        // Malformed timestamps are never "recent"
        assert!(!is_recent(Some("garbage"), "also garbage", now));
    }

    #[test]
    fn test_comment_views() {
        let raw = vec![GhComment {
            body: "[Approved]".to_string(),
            author: Some(Author {
                login: "admin".to_string(),
            }),
            created_at: Some("2026-01-01T00:00:00Z".to_string()),
        }];
        let views = comment_views(Some(&raw));
        assert_eq!(views[0].author, "admin");
        assert!(views[0].created_at.is_some());
        assert!(comment_views(None).is_empty());
    }

    #[test]
    fn test_comment_deserialization_tolerates_missing_fields() {
        let c: GhComment = serde_json::from_str(r#"{"author":null}"#).unwrap();
        assert!(c.body.is_empty());
        assert!(c.author.is_none());
    }
}
