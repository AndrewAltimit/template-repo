//! Security manager for GitHub AI Agents.
//!
//! Manages authorization, rate limiting, and security checks for agent operations.

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::env;
use std::path::Path;
use std::sync::Mutex;
use tracing::{debug, info, warn};

use super::trigger::{is_agent_generated, is_bot_login, is_trigger_response, parse_trigger};
use crate::error::Error;

/// Built-in fallback admin, used when neither a config file nor the
/// `AI_AGENT_DEFAULT_ADMIN` environment variable supplies one.
const BUILTIN_DEFAULT_ADMIN: &str = "AndrewAltimit";

/// Environment variable overriding the built-in default admin(s).
/// Accepts a comma-separated list of usernames.
const DEFAULT_ADMIN_ENV: &str = "AI_AGENT_DEFAULT_ADMIN";

/// Environment variable adding extra allowed users (comma-separated).
const ALLOWED_USERS_ENV: &str = "AI_AGENT_ALLOWED_USERS";

/// Security configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityConfig {
    /// Whether security checks are enabled
    #[serde(default = "default_enabled")]
    pub enabled: bool,

    /// Users with admin privileges
    #[serde(default = "default_agent_admins")]
    pub agent_admins: Vec<String>,

    /// Rate limit window in minutes
    #[serde(default = "default_rate_limit_window")]
    pub rate_limit_window_minutes: u64,

    /// Maximum requests per window
    #[serde(default = "default_rate_limit_max")]
    pub rate_limit_max_requests: usize,

    /// Allowed repositories (empty = all allowed)
    #[serde(default)]
    pub allowed_repositories: Vec<String>,

    /// Message shown when request is rejected
    #[serde(default = "default_reject_message")]
    pub reject_message: String,

    /// Allowed actions
    #[serde(default = "default_allowed_actions")]
    pub allowed_actions: Vec<String>,
}

fn default_enabled() -> bool {
    true
}

/// Resolve the default admin list from an optional env value.
///
/// Split out as a pure function so it can be tested without mutating global
/// process environment (which would race with parallel tests).
fn parse_default_admins(env_value: Option<&str>) -> Vec<String> {
    let admins: Vec<String> = match env_value {
        Some(val) => val
            .split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect(),
        None => Vec::new(),
    };

    // Fall back to the built-in admin if the env var is unset, empty, or
    // contains only separators/whitespace (e.g. ",,," or "   "). An empty
    // admin list must never be returned: depending on downstream allow-list
    // checks it could lock out every user or allow everyone.
    if admins.is_empty() {
        vec![BUILTIN_DEFAULT_ADMIN.to_string()]
    } else {
        admins
    }
}

fn default_agent_admins() -> Vec<String> {
    parse_default_admins(env::var(DEFAULT_ADMIN_ENV).ok().as_deref())
}

fn default_rate_limit_window() -> u64 {
    60
}

fn default_rate_limit_max() -> usize {
    10
}

fn default_reject_message() -> String {
    "This AI agent only processes requests from authorized users.".to_string()
}

fn default_allowed_actions() -> Vec<String> {
    vec![
        "issue_approved".to_string(),
        "issue_close".to_string(),
        "pr_approved".to_string(),
        "issue_review".to_string(),
        "pr_review".to_string(),
        "issue_summarize".to_string(),
        "pr_summarize".to_string(),
        "issue_debug".to_string(),
        "pr_debug".to_string(),
        "pr_close".to_string(),
    ]
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            enabled: default_enabled(),
            agent_admins: default_agent_admins(),
            rate_limit_window_minutes: default_rate_limit_window(),
            rate_limit_max_requests: default_rate_limit_max(),
            allowed_repositories: Vec::new(),
            reject_message: default_reject_message(),
            allowed_actions: default_allowed_actions(),
        }
    }
}

/// Where a trigger was found.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TriggerSource {
    /// The issue/PR body
    Body,
    /// The comment at this index (chronological order)
    Comment(usize),
}

/// Trigger information parsed from a comment.
#[derive(Debug, Clone)]
pub struct TriggerInfo {
    /// The action (e.g., "approved", "review")
    pub action: String,
    /// The agent name (optional, may be resolved from board)
    pub agent: Option<String>,
    /// The user who triggered the action
    pub username: String,
    /// Where the trigger was found
    pub source: TriggerSource,
    /// When the triggering comment/body was created (if known)
    pub created_at: Option<DateTime<Utc>>,
}

/// A read-only view of an issue/PR comment used for trigger detection.
///
/// `comments` slices passed to the manager must be in chronological order
/// (the order returned by `gh issue/pr view --json comments`).
#[derive(Debug, Clone, Default)]
pub struct CommentView {
    pub body: String,
    pub author: String,
    pub created_at: Option<DateTime<Utc>>,
}

/// Security manager for AI agent operations.
///
/// Uses interior mutability for the rate limiter so security checks can be
/// performed from `&self` contexts (e.g., async monitor methods).
pub struct SecurityManager {
    config: SecurityConfig,
    allowed_users: HashSet<String>,
    rate_limit_tracker: Mutex<HashMap<String, Vec<DateTime<Utc>>>>,
}

impl SecurityManager {
    /// Create a new security manager with default configuration.
    pub fn new() -> Self {
        let config = SecurityConfig::default();
        let allowed_users = Self::init_allowed_users(&config);

        Self {
            config,
            allowed_users,
            rate_limit_tracker: Mutex::new(HashMap::new()),
        }
    }

    /// Create a security manager from a configuration file.
    ///
    /// Supports two formats:
    /// - Flat `SecurityConfig` (standalone security config file)
    /// - Nested `.agents.yaml` format where security lives under `security:` key
    ///
    /// The file is read through [`super::trust::read_trusted_file`]: in a
    /// PR-triggered run where the PR modifies it, the base-branch version is
    /// used, so a PR cannot add itself to the allow-list.
    pub fn from_config_path(path: &Path) -> Result<Self, Error> {
        let content = super::trust::read_trusted_file(path)?;
        Self::from_yaml_str(&content)
    }

    /// Create a security manager from YAML text (flat or nested format).
    pub fn from_yaml_str(content: &str) -> Result<Self, Error> {
        // A top-level `security` key means the nested `.agents.yaml` format;
        // errors inside it propagate (no silent fallback to defaults).
        let value: serde_yaml::Value = serde_yaml::from_str(content)?;
        let config = match value.get("security") {
            Some(section) if !section.is_null() => {
                info!("Loaded security config from agents YAML (nested format)");
                serde_yaml::from_value::<SecurityConfig>(section.clone())?
            },
            // `security:` present but empty
            Some(_) => SecurityConfig::default(),
            None if value.is_null() => SecurityConfig::default(),
            None => serde_yaml::from_value::<SecurityConfig>(value)?,
        };

        let allowed_users = Self::init_allowed_users(&config);

        Ok(Self {
            config,
            allowed_users,
            rate_limit_tracker: Mutex::new(HashMap::new()),
        })
    }

    /// Create a security manager from a configuration struct.
    #[cfg(test)]
    pub fn from_config(config: SecurityConfig) -> Self {
        let allowed_users = Self::init_allowed_users(&config);
        Self {
            config,
            allowed_users,
            rate_limit_tracker: Mutex::new(HashMap::new()),
        }
    }

    /// Initialize allowed users from config and environment.
    fn init_allowed_users(config: &SecurityConfig) -> HashSet<String> {
        // Case-insensitive comparison: store lowercase
        let mut users: HashSet<String> = config
            .agent_admins
            .iter()
            .map(|u| u.to_lowercase())
            .collect();

        // Add users from environment variable
        if let Ok(env_users) = env::var(ALLOWED_USERS_ENV) {
            for user in env_users.split(',') {
                let user = user.trim();
                if !user.is_empty() {
                    users.insert(user.to_lowercase());
                }
            }
        }

        // Add repository owner (a personal account; for organizations this is
        // the org login, which can never author a comment)
        if let Ok(github_repo) = env::var("GITHUB_REPOSITORY")
            && let Some(owner) = github_repo.split('/').next().filter(|o| !o.is_empty())
        {
            users.insert(owner.to_lowercase());
        }

        // Never allow-list bot accounts or the anonymous/empty login
        users.retain(|u| !u.is_empty() && !is_bot_login(u));

        if !config.enabled {
            warn!("Security checks are DISABLED by configuration (security.enabled: false)");
        }

        debug!("Initialized allowed users: {:?}", users);
        users
    }

    /// Get the rejection message.
    pub fn reject_message(&self) -> &str {
        &self.config.reject_message
    }

    /// Check if a user is authorized.
    ///
    /// Bot accounts and empty logins are never authorized, even when security
    /// checks are otherwise disabled.
    pub fn is_user_allowed(&self, username: &str) -> bool {
        if username.trim().is_empty() || is_bot_login(username) {
            return false;
        }
        if !self.config.enabled {
            return true;
        }
        self.allowed_users.contains(&username.to_lowercase())
    }

    /// Whether `login` may author agent responses that mark a trigger as
    /// handled: allow-listed users, bot accounts, or the account the agent
    /// itself is authenticated as.
    pub fn is_trusted_responder(&self, login: &str, agent_login: Option<&str>) -> bool {
        is_bot_login(login)
            || self.allowed_users.contains(&login.to_lowercase())
            || agent_login.is_some_and(|a| a.eq_ignore_ascii_case(login))
    }

    /// Check if an action is allowed.
    pub fn is_action_allowed(&self, action: &str) -> bool {
        if !self.config.enabled {
            return true;
        }
        self.config.allowed_actions.contains(&action.to_string())
    }

    /// Check if a repository is allowed.
    pub fn is_repository_allowed(&self, repository: &str) -> bool {
        if !self.config.enabled {
            return true;
        }
        // Empty list means all repositories are allowed
        if self.config.allowed_repositories.is_empty() {
            return true;
        }
        self.config
            .allowed_repositories
            .iter()
            .any(|r| r.eq_ignore_ascii_case(repository))
    }

    /// Check and update rate limit for a user/action combination.
    pub fn check_rate_limit(&self, username: &str, action: &str) -> bool {
        if !self.config.enabled {
            return true;
        }

        let key = format!("{}:{}", username.to_lowercase(), action);
        let now = Utc::now();
        let window = Duration::minutes(self.config.rate_limit_window_minutes as i64);
        let cutoff = now - window;

        let mut tracker = self
            .rate_limit_tracker
            .lock()
            .unwrap_or_else(|e| e.into_inner());

        // Clean old entries
        let requests = tracker.entry(key.clone()).or_default();
        requests.retain(|t| *t > cutoff);

        // Check limit
        if requests.len() >= self.config.rate_limit_max_requests {
            warn!(
                "Rate limit exceeded for {}:{} ({} requests in {} minutes)",
                username,
                action,
                requests.len(),
                self.config.rate_limit_window_minutes
            );
            return false;
        }

        // Record request
        requests.push(now);
        true
    }

    /// Check for a valid trigger in issue/PR data.
    ///
    /// Iterates comments in reverse order so the **latest** matching trigger
    /// from an authorized user wins, allowing newer directives to supersede
    /// older ones. Falls back to the issue/PR body only if no comment
    /// triggers exist. Comments and bodies generated by this tool are never
    /// considered, which prevents prompt-injected agent output from
    /// self-authorizing when the agent posts under an allow-listed account.
    pub fn check_trigger_comment(
        &self,
        body: &str,
        author: &str,
        body_created_at: Option<DateTime<Utc>>,
        comments: &[CommentView],
    ) -> Option<TriggerInfo> {
        for (index, comment) in comments.iter().enumerate().rev() {
            if is_agent_generated(&comment.body) || !self.is_user_allowed(&comment.author) {
                continue;
            }
            if let Some(trigger) = parse_trigger(&comment.body) {
                return Some(TriggerInfo {
                    action: trigger.action,
                    agent: trigger.agent,
                    username: comment.author.clone(),
                    source: TriggerSource::Comment(index),
                    created_at: comment.created_at,
                });
            }
        }

        if !is_agent_generated(body)
            && self.is_user_allowed(author)
            && let Some(trigger) = parse_trigger(body)
        {
            return Some(TriggerInfo {
                action: trigger.action,
                agent: trigger.agent,
                username: author.to_string(),
                source: TriggerSource::Body,
                created_at: body_created_at,
            });
        }

        None
    }

    /// Whether the agent already responded to `trigger`.
    ///
    /// A trigger is handled once a monitor reply (see
    /// [`super::trigger::TRIGGER_RESPONSE_MARKER`]) from a trusted responder
    /// appears after it. This makes monitor runs idempotent: the same
    /// `[Approved]` comment is never acted on twice, and security rejections
    /// are not re-posted on every polling cycle.
    pub fn is_trigger_handled(
        &self,
        trigger: &TriggerInfo,
        comments: &[CommentView],
        agent_login: Option<&str>,
    ) -> bool {
        let start = match trigger.source {
            TriggerSource::Body => 0,
            TriggerSource::Comment(index) => index + 1,
        };
        comments.iter().skip(start).any(|c| {
            is_trigger_response(&c.body) && self.is_trusted_responder(&c.author, agent_login)
        })
    }

    /// Perform a comprehensive security check.
    ///
    /// Returns (allowed, rejection_reason).
    pub fn perform_full_security_check(
        &self,
        username: &str,
        action: &str,
        repository: &str,
    ) -> (bool, String) {
        if !self.config.enabled {
            return (true, String::new());
        }

        // Check user authorization
        if !self.is_user_allowed(username) {
            return (false, format!("User '{}' is not authorized", username));
        }

        // Check action authorization
        if !self.is_action_allowed(action) {
            return (
                false,
                format!("Action '{}' is not an allowed action", action),
            );
        }

        // Check repository
        if !self.is_repository_allowed(repository) {
            return (
                false,
                format!("Repository '{}' is not authorized", repository),
            );
        }

        // Check rate limit
        if !self.check_rate_limit(username, action) {
            return (false, "Rate limit exceeded".to_string());
        }

        (true, String::new())
    }

    /// Get list of allowed users (for debugging/info).
    pub fn allowed_users(&self) -> Vec<String> {
        self.allowed_users.iter().cloned().collect()
    }
}

impl Default for SecurityManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_user_allowed_case_insensitive() {
        let manager = SecurityManager::new();
        assert!(manager.is_user_allowed("AndrewAltimit"));
        assert!(manager.is_user_allowed("andrewaltimit"));
        assert!(manager.is_user_allowed("ANDREWALTIMIT"));
    }

    #[test]
    fn test_rate_limit() {
        let manager = SecurityManager::from_config(SecurityConfig {
            rate_limit_max_requests: 2,
            ..Default::default()
        });

        assert!(manager.check_rate_limit("user", "action"));
        assert!(manager.check_rate_limit("user", "action"));
        assert!(!manager.check_rate_limit("user", "action"));
    }

    #[test]
    fn test_full_security_check() {
        let manager = SecurityManager::new();
        let (allowed, reason) = manager.perform_full_security_check(
            "AndrewAltimit",
            "issue_approved",
            "AndrewAltimit/repo",
        );
        assert!(allowed);
        assert!(reason.is_empty());
    }

    #[test]
    fn test_parse_default_admins() {
        // Unset / empty -> built-in fallback
        assert_eq!(parse_default_admins(None), vec![BUILTIN_DEFAULT_ADMIN]);
        assert_eq!(parse_default_admins(Some("")), vec![BUILTIN_DEFAULT_ADMIN]);
        assert_eq!(
            parse_default_admins(Some("   ")),
            vec![BUILTIN_DEFAULT_ADMIN]
        );

        // Only separators / whitespace -> built-in fallback (never an empty list)
        assert_eq!(parse_default_admins(Some(",")), vec![BUILTIN_DEFAULT_ADMIN]);
        assert_eq!(
            parse_default_admins(Some(",,,")),
            vec![BUILTIN_DEFAULT_ADMIN]
        );
        assert_eq!(
            parse_default_admins(Some(" , , ")),
            vec![BUILTIN_DEFAULT_ADMIN]
        );

        // Single override
        assert_eq!(parse_default_admins(Some("Alice")), vec!["Alice"]);

        // Comma-separated list with surrounding whitespace and empties
        assert_eq!(
            parse_default_admins(Some(" Alice , Bob ,, ")),
            vec!["Alice", "Bob"]
        );
    }

    #[test]
    fn test_unauthorized_user() {
        let manager = SecurityManager::new();
        let (allowed, reason) =
            manager.perform_full_security_check("unknown_user", "issue_approved", "owner/repo");
        assert!(!allowed);
        assert!(reason.contains("not authorized"));
    }

    #[test]
    fn test_agents_yaml_nested_parsing() {
        let yaml = r#"
enabled_agents:
  - claude
security:
  agent_admins:
    - TestAdmin
  rate_limit_window_minutes: 30
"#;
        let m = SecurityManager::from_yaml_str(yaml).unwrap();
        assert_eq!(m.config.agent_admins, vec!["TestAdmin"]);
        assert_eq!(m.config.rate_limit_window_minutes, 30);
        assert!(m.is_user_allowed("testadmin"));
    }

    #[test]
    fn test_agents_yaml_without_security_key_uses_flat_defaults() {
        let yaml = r#"
enabled_agents:
  - claude
"#;
        let m = SecurityManager::from_yaml_str(yaml).unwrap();
        assert_eq!(m.config.rate_limit_window_minutes, 60);
    }

    #[test]
    fn test_flat_config_format() {
        let yaml = r#"
agent_admins:
  - FlatAdmin
rate_limit_window_minutes: 15
"#;
        let m = SecurityManager::from_yaml_str(yaml).unwrap();
        assert_eq!(m.config.agent_admins, vec!["FlatAdmin"]);
        assert_eq!(m.config.rate_limit_window_minutes, 15);
    }

    #[test]
    fn test_empty_security_section_uses_defaults() {
        let m = SecurityManager::from_yaml_str("security:\n").unwrap();
        assert!(m.config.enabled);
        let m = SecurityManager::from_yaml_str("").unwrap();
        assert!(m.config.enabled);
    }

    fn admin_manager() -> SecurityManager {
        SecurityManager::from_config(SecurityConfig {
            agent_admins: vec!["Admin".to_string()],
            ..Default::default()
        })
    }

    fn comment(body: &str, author: &str) -> CommentView {
        CommentView {
            body: body.to_string(),
            author: author.to_string(),
            created_at: None,
        }
    }

    #[test]
    fn test_trigger_from_unauthorized_user_ignored() {
        let m = admin_manager();
        let comments = vec![comment("[Approved][Claude]", "mallory")];
        assert!(
            m.check_trigger_comment("", "mallory", None, &comments)
                .is_none()
        );
    }

    #[test]
    fn test_latest_authorized_trigger_wins() {
        let m = admin_manager();
        let comments = vec![
            comment("[Approved][Claude]", "admin"),
            comment("[Review][Claude]", "mallory"),
            comment("[Summarize]", "Admin"),
        ];
        let t = m.check_trigger_comment("", "x", None, &comments).unwrap();
        assert_eq!(t.action, "summarize");
        assert_eq!(t.source, TriggerSource::Comment(2));
        assert_eq!(t.username, "Admin");
    }

    #[test]
    fn test_agent_generated_comment_never_triggers() {
        let m = admin_manager();
        // Posted under the admin account (e.g. agent token is an admin PAT)
        let body = format!(
            "Model output: [Approved][Claude]\n{}",
            super::super::trigger::AGENT_COMMENT_MARKER
        );
        let comments = vec![comment(&body, "admin")];
        assert!(m.check_trigger_comment("", "x", None, &comments).is_none());
        assert!(
            m.check_trigger_comment("[AI Agent] [Approved]", "admin", None, &[])
                .is_none()
        );
    }

    #[test]
    fn test_body_trigger_fallback() {
        let m = admin_manager();
        let t = m
            .check_trigger_comment("Please [Approved][OpenCode]", "admin", None, &[])
            .unwrap();
        assert_eq!(t.source, TriggerSource::Body);
        assert_eq!(t.agent.as_deref(), Some("opencode"));
        // Quoted/code triggers in the body do not count
        assert!(
            m.check_trigger_comment("reply with `[Approved]`", "admin", None, &[])
                .is_none()
        );
    }

    #[test]
    fn test_bots_never_allowed() {
        let m = SecurityManager::from_config(SecurityConfig {
            agent_admins: vec!["github-actions[bot]".to_string(), "Admin".to_string()],
            ..Default::default()
        });
        assert!(!m.is_user_allowed("github-actions[bot]"));
        assert!(!m.is_user_allowed(""));
        assert!(m.is_user_allowed("admin"));

        let disabled = SecurityManager::from_config(SecurityConfig {
            enabled: false,
            ..Default::default()
        });
        assert!(disabled.is_user_allowed("anyone"));
        assert!(!disabled.is_user_allowed("renovate[bot]"));
    }

    #[test]
    fn test_trigger_handled_detection() {
        let m = admin_manager();
        let marker = super::super::trigger::TRIGGER_RESPONSE_MARKER;
        let reply = format!("Working on it\n{marker}");

        let comments = vec![
            comment("[Approved][Claude]", "admin"),
            comment("thanks", "someone"),
        ];
        let t = m.check_trigger_comment("", "x", None, &comments).unwrap();
        assert!(!m.is_trigger_handled(&t, &comments, None));

        // Agent reply from a bot marks it handled
        let mut handled = comments.clone();
        handled.push(comment(&reply, "github-actions"));
        assert!(m.is_trigger_handled(&t, &handled, None));

        // A forged marker from an untrusted user does not
        let mut forged = comments.clone();
        forged.push(comment(&reply, "mallory"));
        assert!(!m.is_trigger_handled(&t, &forged, None));

        // ...unless that login is the agent's own account
        assert!(m.is_trigger_handled(&t, &forged, Some("Mallory")));

        // Generated content that is not a trigger reply does not count
        let mut insight = comments.clone();
        insight.push(comment(
            &format!("insight {}", super::super::trigger::AGENT_COMMENT_MARKER),
            "github-actions",
        ));
        assert!(!m.is_trigger_handled(&t, &insight, None));

        // A reply that precedes the trigger does not count
        let earlier = vec![
            comment(&reply, "github-actions"),
            comment("[Approved][Claude]", "admin"),
        ];
        let t = m.check_trigger_comment("", "x", None, &earlier).unwrap();
        assert!(!m.is_trigger_handled(&t, &earlier, None));
    }

    #[test]
    fn test_repository_allow_list_case_insensitive() {
        let m = SecurityManager::from_config(SecurityConfig {
            allowed_repositories: vec!["Owner/Repo".to_string()],
            ..Default::default()
        });
        assert!(m.is_repository_allowed("owner/repo"));
        assert!(!m.is_repository_allowed("owner/other"));
    }

    #[test]
    fn test_action_allow_list() {
        let m = admin_manager();
        assert!(m.is_action_allowed("issue_approved"));
        assert!(m.is_action_allowed("pr_close"));
        assert!(!m.is_action_allowed("issue_delete"));
    }

    #[test]
    fn test_invalid_nested_security_does_not_silently_fallback() {
        // If YAML has `security:` key with invalid shape, from_config_path
        // should propagate the error, not silently fall back to defaults
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("invalid_nested.yaml");
        std::fs::write(
            &path,
            r#"
security:
  agent_admins: "not_a_list"
"#,
        )
        .unwrap();
        let result = SecurityManager::from_config_path(&path);
        assert!(
            result.is_err(),
            "invalid nested security config should return error, not silent defaults"
        );
    }
}
