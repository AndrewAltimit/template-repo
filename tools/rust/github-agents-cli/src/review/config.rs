//! Configuration for PR reviews.
//!
//! Loads configuration from `.agents.yaml` under the `pr_review` section.

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

use crate::error::{Error, Result};

/// PR Review configuration from .agents.yaml
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PRReviewConfig {
    /// Default agent for reviews (gemini, claude, openrouter)
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
    "gemini".to_string()
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
    /// Load PR review configuration from .agents.yaml
    pub fn load() -> Result<Self> {
        match FullConfig::load(None) {
            Ok(full_config) => Ok(full_config.pr_review),
            Err(_) => {
                // If no config file found, use defaults
                tracing::info!("No .agents.yaml found, using default PR review config");
                Ok(Self::default())
            },
        }
    }
}

/// Model overrides for specific agents
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GeminiModelConfig {
    #[serde(default)]
    pub pro_model: Option<String>,
    #[serde(default)]
    pub flash_model: Option<String>,
    #[serde(default)]
    pub default_model: Option<String>,
}

/// Security configuration (agent_admins, trusted_sources)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SecurityConfig {
    #[serde(default)]
    pub agent_admins: Vec<String>,
    #[serde(default)]
    pub trusted_sources: Vec<String>,
    #[serde(default)]
    pub subprocess_timeout: Option<u64>,
}

/// Model overrides section
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ModelOverrides {
    #[serde(default)]
    pub gemini: GeminiModelConfig,
}

/// Root .agents.yaml structure (partial, for PR review needs)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
struct AgentsYaml {
    #[serde(default)]
    pr_review: Option<PRReviewConfig>,
    #[serde(default)]
    security: SecurityConfig,
    #[serde(default)]
    model_overrides: ModelOverrides,
}

/// Full configuration loaded from .agents.yaml
#[derive(Debug, Clone)]
pub struct FullConfig {
    pub pr_review: PRReviewConfig,
    pub security: SecurityConfig,
    pub model_overrides: ModelOverrides,
}

impl FullConfig {
    /// Load configuration from .agents.yaml
    pub fn load(config_path: Option<&Path>) -> Result<Self> {
        let path = if let Some(p) = config_path {
            if p.exists() {
                p.to_path_buf()
            } else {
                return Err(Error::Config(format!(
                    "Config file not found: {}",
                    p.display()
                )));
            }
        } else {
            Self::find_config_file().ok_or_else(|| {
                Error::Config("No .agents.yaml found in current directory or parents".to_string())
            })?
        };

        Self::load_from_path(&path)
    }

    /// Find .agents.yaml from current directory up
    fn find_config_file() -> Option<PathBuf> {
        let mut current_dir = std::env::current_dir().ok()?;

        loop {
            let potential_config = current_dir.join(".agents.yaml");
            if potential_config.exists() {
                return Some(potential_config);
            }

            if !current_dir.pop() {
                break;
            }
        }

        None
    }

    /// Load configuration from a specific path
    fn load_from_path(path: &Path) -> Result<Self> {
        let content = fs::read_to_string(path)
            .map_err(|e| Error::Config(format!("Failed to read .agents.yaml: {}", e)))?;

        let yaml: AgentsYaml = serde_yaml::from_str(&content)
            .map_err(|e| Error::Config(format!("Failed to parse .agents.yaml: {}", e)))?;

        Ok(Self {
            pr_review: yaml.pr_review.unwrap_or_default(),
            security: yaml.security,
            model_overrides: yaml.model_overrides,
        })
    }

    /// Get the Gemini model to use for reviews
    pub fn gemini_review_model(&self) -> String {
        self.model_overrides
            .gemini
            .default_model
            .clone()
            .or_else(|| self.model_overrides.gemini.pro_model.clone())
            .unwrap_or_else(|| "gemini-2.0-flash".to_string())
    }

    /// Get the Gemini model to use for condensation
    pub fn gemini_condenser_model(&self) -> String {
        self.model_overrides
            .gemini
            .flash_model
            .clone()
            .unwrap_or_else(|| "gemini-2.0-flash".to_string())
    }

    /// Get subprocess timeout in seconds
    pub fn subprocess_timeout(&self) -> u64 {
        self.security.subprocess_timeout.unwrap_or(600)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = PRReviewConfig::default();
        assert_eq!(config.default_agent, "gemini");
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
"#;
        let parsed: AgentsYaml = serde_yaml::from_str(yaml).unwrap();
        let config = parsed.pr_review.unwrap();
        assert_eq!(config.default_agent, "claude");
        assert_eq!(config.max_words, 300);
        assert!(!config.incremental_enabled);
    }
}
