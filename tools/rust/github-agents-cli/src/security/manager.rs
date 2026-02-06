//! Security manager for GitHub AI Agents.
//!
//! Manages authorization, rate limiting, and security checks for agent operations.

use chrono::{DateTime, Duration, Utc};
use lazy_static::lazy_static;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::env;
use std::path::Path;
use std::sync::Mutex;
use tracing::{debug, info, warn};

use crate::error::Error;

lazy_static! {
    /// Pattern for trigger comments: [Action] with optional [Agent]
    static ref TRIGGER_PATTERN: Regex =
        Regex::new(r"(?i)\[(Approved|Review|Close|Summarize|Debug)\](?:\[([A-Za-z]+)\])?").unwrap();
}

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

fn default_agent_admins() -> Vec<String> {
    vec!["AndrewAltimit".to_string()]
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

/// Top-level structure of `.agents.yaml` for extracting the nested `security` section.
///
/// The `.agents.yaml` file stores security config under `security:`, not at the top level.
/// Uses `Option` instead of `#[serde(default)]` so we can distinguish "no security key"
/// (flat format) from "has security key" (nested format).
#[derive(Debug, Deserialize)]
struct AgentsYamlConfig {
    security: Option<SecurityConfig>,
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
    pub fn from_config_path(path: &Path) -> Result<Self, Error> {
        let content = std::fs::read_to_string(path).map_err(Error::Io)?;

        // Check if the YAML has a top-level `security` key to determine format.
        // If it does, parse as nested `.agents.yaml` and propagate errors
        // (don't silently fall back to flat format with defaults).
        let has_security_key = serde_yaml::from_str::<serde_yaml::Value>(&content)
            .ok()
            .and_then(|v| v.as_mapping().cloned())
            .map(|m| m.contains_key(serde_yaml::Value::String("security".to_string())))
            .unwrap_or(false);

        let config = if has_security_key {
            let agents_config = serde_yaml::from_str::<AgentsYamlConfig>(&content)?;
            if let Some(security) = agents_config.security {
                info!("Loaded security config from agents YAML (nested format)");
                security
            } else {
                // `security` key present but null/empty - use defaults
                SecurityConfig::default()
            }
        } else {
            serde_yaml::from_str::<SecurityConfig>(&content)?
        };

        let allowed_users = Self::init_allowed_users(&config);

        Ok(Self {
            config,
            allowed_users,
            rate_limit_tracker: Mutex::new(HashMap::new()),
        })
    }

    /// Create a security manager from a configuration struct.
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
        if let Ok(env_users) = env::var("AI_AGENT_ALLOWED_USERS") {
            for user in env_users.split(',') {
                let user = user.trim();
                if !user.is_empty() {
                    users.insert(user.to_lowercase());
                }
            }
        }

        // Add repository owner
        if let Ok(github_repo) = env::var("GITHUB_REPOSITORY") {
            if let Some(owner) = github_repo.split('/').next() {
                users.insert(owner.to_lowercase());
            }
        }

        debug!("Initialized allowed users: {:?}", users);
        users
    }

    /// Get the rejection message.
    pub fn reject_message(&self) -> &str {
        &self.config.reject_message
    }

    /// Parse a trigger comment and extract action and optional agent.
    ///
    /// Returns (action, agent) tuple where agent may be None.
    pub fn parse_trigger_comment(&self, text: &str) -> Option<(String, Option<String>)> {
        if text.is_empty() {
            return None;
        }

        let captures = TRIGGER_PATTERN.captures(text)?;
        let action = captures.get(1)?.as_str().to_lowercase();
        let agent = captures.get(2).map(|m| m.as_str().to_lowercase());

        Some((action, agent))
    }

    /// Check if a user is authorized.
    pub fn is_user_allowed(&self, username: &str) -> bool {
        if !self.config.enabled {
            return true;
        }
        self.allowed_users.contains(&username.to_lowercase())
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
            .contains(&repository.to_string())
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
    /// wins, allowing newer directives to supersede older ones.
    /// Falls back to checking the issue/PR body only if no comment triggers exist.
    pub fn check_trigger_comment(
        &self,
        body: &str,
        author: &str,
        comments: &[(String, String)], // (body, author) pairs
    ) -> Option<TriggerInfo> {
        // Check comments in reverse (latest first) so newer directives supersede older ones
        for (comment_body, comment_author) in comments.iter().rev() {
            if let Some((action, agent)) = self.parse_trigger_comment(comment_body) {
                if self.is_user_allowed(comment_author) {
                    return Some(TriggerInfo {
                        action,
                        agent,
                        username: comment_author.to_string(),
                    });
                }
            }
        }

        // Fall back to issue/PR body if no comment triggers found
        if let Some((action, agent)) = self.parse_trigger_comment(body) {
            if self.is_user_allowed(author) {
                return Some(TriggerInfo {
                    action,
                    agent,
                    username: author.to_string(),
                });
            }
        }

        None
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
    fn test_parse_trigger_simple() {
        let manager = SecurityManager::new();
        let result = manager.parse_trigger_comment("[Approved]");
        assert!(result.is_some());
        let (action, agent) = result.unwrap();
        assert_eq!(action, "approved");
        assert!(agent.is_none());
    }

    #[test]
    fn test_parse_trigger_with_agent() {
        let manager = SecurityManager::new();
        let result = manager.parse_trigger_comment("[Approved][Claude]");
        assert!(result.is_some());
        let (action, agent) = result.unwrap();
        assert_eq!(action, "approved");
        assert_eq!(agent, Some("claude".to_string()));
    }

    #[test]
    fn test_parse_trigger_case_insensitive() {
        let manager = SecurityManager::new();
        let result = manager.parse_trigger_comment("[APPROVED][CLAUDE]");
        assert!(result.is_some());
        let (action, agent) = result.unwrap();
        assert_eq!(action, "approved");
        assert_eq!(agent, Some("claude".to_string()));
    }

    #[test]
    fn test_parse_trigger_invalid() {
        let manager = SecurityManager::new();
        let result = manager.parse_trigger_comment("[InvalidAction]");
        assert!(result.is_none());
    }

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
        let agents_config: AgentsYamlConfig = serde_yaml::from_str(yaml).unwrap();
        let security = agents_config
            .security
            .expect("security key should be present");
        assert_eq!(security.agent_admins, vec!["TestAdmin"]);
        assert_eq!(security.rate_limit_window_minutes, 30);
    }

    #[test]
    fn test_agents_yaml_without_security_key() {
        // A YAML without `security:` key should parse but have security = None
        let yaml = r#"
enabled_agents:
  - claude
"#;
        let agents_config: AgentsYamlConfig = serde_yaml::from_str(yaml).unwrap();
        assert!(
            agents_config.security.is_none(),
            "security should be None when key is absent"
        );
    }

    #[test]
    fn test_flat_config_not_treated_as_nested() {
        // A flat SecurityConfig should not be silently consumed as nested format
        let yaml = r#"
agent_admins:
  - FlatAdmin
rate_limit_window_minutes: 15
"#;
        let agents_config: AgentsYamlConfig = serde_yaml::from_str(yaml).unwrap();
        assert!(
            agents_config.security.is_none(),
            "flat config should not populate nested security field"
        );
    }

    #[test]
    fn test_invalid_nested_security_does_not_silently_fallback() {
        // If YAML has `security:` key with invalid shape, from_config_path
        // should propagate the error, not silently fall back to defaults
        let dir = std::env::temp_dir().join("test_invalid_nested");
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("invalid_nested.yaml");
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
        std::fs::remove_dir_all(&dir).ok();
    }
}
