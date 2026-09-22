//! Configuration for PR reviews.
//!
//! Loads configuration from `.agents.yaml` (the `pr_review` and `security`
//! sections) and review profiles from `review-profiles.yaml`. Both files are
//! read through [`crate::security::trust::read_trusted_file`], so a PR cannot rewrite
//! the reviewer's configuration or instructions for its own review.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};

use crate::error::{Error, Result};
use crate::security::trust::read_trusted_file;

const AGENTS_CONFIG_FILE: &str = ".agents.yaml";
const PROFILES_FILE: &str = "review-profiles.yaml";

/// PR Review configuration from .agents.yaml
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PRReviewConfig {
    /// Default agent for reviews (claude, openrouter, opencode, crush)
    #[serde(default = "default_agent")]
    pub default_agent: String,

    /// Maximum words in review
    #[serde(default = "default_max_words")]
    pub max_words: usize,

    /// Word count threshold to trigger condensation
    #[serde(default = "default_condensation_threshold")]
    pub condensation_threshold: usize,

    /// Enable incremental reviews
    #[serde(default = "default_true")]
    pub incremental_enabled: bool,

    /// Include comment context with trust bucketing
    #[serde(default = "default_true")]
    pub include_comment_context: bool,

    /// Verify claims against actual files (hallucination detection)
    #[serde(default = "default_true")]
    pub verify_claims: bool,

    /// URL for reaction image configuration
    #[serde(default = "default_reaction_url")]
    pub reaction_config_url: String,

    /// Enable editor pass to clean up review formatting (default: false)
    #[serde(default)]
    pub editor_enabled: bool,

    /// Agent to use for editor pass (default: claude)
    #[serde(default = "default_editor_agent")]
    pub editor_agent: String,
}

fn default_agent() -> String {
    "claude".to_string()
}

fn default_max_words() -> usize {
    500
}

fn default_condensation_threshold() -> usize {
    600
}

fn default_true() -> bool {
    true
}

fn default_reaction_url() -> String {
    "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml"
        .to_string()
}

fn default_editor_agent() -> String {
    "claude".to_string()
}

impl Default for PRReviewConfig {
    fn default() -> Self {
        Self {
            default_agent: default_agent(),
            max_words: default_max_words(),
            condensation_threshold: default_condensation_threshold(),
            incremental_enabled: default_true(),
            include_comment_context: default_true(),
            verify_claims: default_true(),
            reaction_config_url: default_reaction_url(),
            editor_enabled: false,
            editor_agent: default_editor_agent(),
        }
    }
}

impl PRReviewConfig {
    /// Load PR review configuration from .agents.yaml.
    ///
    /// A missing file yields defaults; a file that exists but cannot be
    /// parsed is an error (silently reviewing with defaults would hide
    /// misconfiguration).
    pub fn load() -> Result<Self> {
        Ok(FullConfig::load_or_default()?.pr_review)
    }
}

/// Security configuration (agent_admins, trusted_sources)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SecurityConfig {
    #[serde(default)]
    pub agent_admins: Vec<String>,
    #[serde(default)]
    pub trusted_sources: Vec<String>,
}

/// Root .agents.yaml structure (partial, for PR review needs)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
struct AgentsYaml {
    #[serde(default)]
    pr_review: Option<PRReviewConfig>,
    #[serde(default)]
    security: SecurityConfig,
}

/// Full configuration loaded from .agents.yaml
#[derive(Debug, Clone, Default)]
pub struct FullConfig {
    pub pr_review: PRReviewConfig,
    pub security: SecurityConfig,
}

impl FullConfig {
    /// Load `.agents.yaml` if present (current directory or a parent),
    /// otherwise return defaults.
    pub fn load_or_default() -> Result<Self> {
        match find_upwards(AGENTS_CONFIG_FILE) {
            Some(path) => Self::load_from_path(&path),
            None => {
                tracing::info!("No .agents.yaml found, using default PR review config");
                Ok(Self::default())
            },
        }
    }

    /// Load configuration from a specific path
    fn load_from_path(path: &Path) -> Result<Self> {
        let content = match read_trusted_file(path) {
            Ok(c) => c,
            Err(Error::Io(e)) if e.kind() == std::io::ErrorKind::NotFound => {
                return Ok(Self::default());
            },
            Err(e) => return Err(Error::Config(format!("Failed to read .agents.yaml: {}", e))),
        };
        Self::parse(&content)
    }

    fn parse(content: &str) -> Result<Self> {
        let yaml: AgentsYaml = serde_yaml::from_str(content)
            .map_err(|e| Error::Config(format!("Failed to parse .agents.yaml: {}", e)))?;
        Ok(Self {
            pr_review: yaml.pr_review.unwrap_or_default(),
            security: yaml.security,
        })
    }

    /// Accounts whose review markers and comments are trusted
    /// (`agent_admins` plus `trusted_sources`, lowercased).
    pub fn trusted_logins(&self) -> Vec<String> {
        self.security
            .agent_admins
            .iter()
            .chain(self.security.trusted_sources.iter())
            .map(|s| s.to_lowercase())
            .collect()
    }
}

/// Find `name` in the current directory (returned as a relative path, so
/// base-branch substitution applies) or in a parent directory.
fn find_upwards(name: &str) -> Option<PathBuf> {
    let local = PathBuf::from(name);
    if local.exists() {
        return Some(local);
    }
    let mut dir = std::env::current_dir().ok()?;
    while dir.pop() {
        let candidate = dir.join(name);
        if candidate.exists() {
            return Some(candidate);
        }
    }
    None
}

/// A review profile loaded from review-profiles.yaml
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReviewProfile {
    pub display_name: String,
    pub agent: String,
    #[serde(default)]
    pub model: Option<String>,
    pub focus: String,
    pub instructions: String,
}

/// Root structure of review-profiles.yaml
#[derive(Debug, Clone, Serialize, Deserialize)]
struct ReviewProfilesYaml {
    profiles: HashMap<String, ReviewProfile>,
}

impl ReviewProfile {
    /// Load a specific profile from review-profiles.yaml
    pub fn load(profile_name: &str) -> Result<Self> {
        let path = find_upwards(PROFILES_FILE).ok_or_else(|| {
            Error::Config(
                "No review-profiles.yaml found in current directory or parents".to_string(),
            )
        })?;
        let content = read_trusted_file(&path)
            .map_err(|e| Error::Config(format!("Failed to read review-profiles.yaml: {}", e)))?;
        Self::from_yaml(&content, profile_name)
    }

    fn from_yaml(content: &str, profile_name: &str) -> Result<Self> {
        let yaml: ReviewProfilesYaml = serde_yaml::from_str(content)
            .map_err(|e| Error::Config(format!("Failed to parse review-profiles.yaml: {}", e)))?;

        yaml.profiles.get(profile_name).cloned().ok_or_else(|| {
            let mut names: Vec<_> = yaml.profiles.keys().cloned().collect();
            names.sort();
            Error::Config(format!(
                "Profile '{}' not found in review-profiles.yaml. Available: {}",
                profile_name,
                names.join(", ")
            ))
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = PRReviewConfig::default();
        assert_eq!(config.default_agent, "claude");
        assert_eq!(config.max_words, 500);
        assert_eq!(config.condensation_threshold, 600);
        assert!(config.incremental_enabled);
        assert!(config.include_comment_context);
        assert!(config.verify_claims);
    }

    #[test]
    fn test_parse_pr_review_config() {
        let yaml = r#"
pr_review:
  default_agent: claude
  max_words: 300
  incremental_enabled: false
security:
  agent_admins: [Admin]
  trusted_sources: ["github-actions[bot]"]
"#;
        let config = FullConfig::parse(yaml).unwrap();
        assert_eq!(config.pr_review.default_agent, "claude");
        assert_eq!(config.pr_review.max_words, 300);
        assert!(!config.pr_review.incremental_enabled);
        assert_eq!(
            config.trusted_logins(),
            vec!["admin".to_string(), "github-actions[bot]".to_string()]
        );
    }

    #[test]
    fn test_invalid_config_is_error() {
        assert!(FullConfig::parse("pr_review: [not, a, map]").is_err());
    }

    #[test]
    fn test_profile_lookup() {
        let yaml = r#"
profiles:
  security:
    display_name: "Security"
    agent: claude
    model: sonnet
    focus: "sec"
    instructions: "be careful"
"#;
        let p = ReviewProfile::from_yaml(yaml, "security").unwrap();
        assert_eq!(p.agent, "claude");
        assert_eq!(p.model.as_deref(), Some("sonnet"));
        let err = ReviewProfile::from_yaml(yaml, "missing").unwrap_err();
        assert!(err.to_string().contains("Available: security"));
    }
}
