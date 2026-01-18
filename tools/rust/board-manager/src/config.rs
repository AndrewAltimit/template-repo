//! Configuration loading for board manager.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::error::{BoardError, Result};
use crate::models::BoardConfig;

/// Configuration file structure matching ai-agents-board.yml.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ConfigFile {
    #[serde(default)]
    pub project: ProjectConfig,
    #[serde(default)]
    pub repository: String,
    #[serde(default)]
    pub fields: HashMap<String, String>,
    #[serde(default)]
    pub agents: AgentsConfig,
    #[serde(default)]
    pub work_queue: WorkQueueConfig,
    #[serde(default)]
    pub work_claims: ClaimsConfig,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ProjectConfig {
    #[serde(default)]
    pub number: u64,
    #[serde(default)]
    pub owner: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AgentsConfig {
    #[serde(default)]
    pub enabled_agents: Vec<String>,
    #[serde(default = "default_true")]
    pub auto_discover: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WorkQueueConfig {
    #[serde(default)]
    pub exclude_labels: Vec<String>,
    #[serde(default)]
    pub priority_labels: HashMap<String, Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimsConfig {
    #[serde(default = "default_claim_timeout")]
    pub timeout: i64,
    #[serde(default = "default_renewal_interval")]
    pub renewal_interval: i64,
}

impl Default for ClaimsConfig {
    fn default() -> Self {
        Self {
            timeout: default_claim_timeout(),
            renewal_interval: default_renewal_interval(),
        }
    }
}

fn default_true() -> bool {
    true
}

fn default_claim_timeout() -> i64 {
    86400 // 24 hours
}

fn default_renewal_interval() -> i64 {
    3600 // 1 hour
}


impl From<ConfigFile> for BoardConfig {
    fn from(cfg: ConfigFile) -> Self {
        let mut field_mappings = BoardConfig::default_field_mappings();
        field_mappings.extend(cfg.fields);

        BoardConfig {
            project_number: cfg.project.number,
            owner: cfg.project.owner,
            repository: cfg.repository,
            field_mappings,
            claim_timeout: cfg.work_claims.timeout,
            claim_renewal_interval: cfg.work_claims.renewal_interval,
            enabled_agents: cfg.agents.enabled_agents,
            auto_discover: cfg.agents.auto_discover,
            exclude_labels: cfg.work_queue.exclude_labels,
            priority_labels: cfg.work_queue.priority_labels,
        }
    }
}

/// Load configuration from file or environment.
pub fn load_config() -> Result<BoardConfig> {
    // Try config file first
    let config_paths = [
        "ai-agents-board.yml",
        "ai-agents-board.yaml",
        ".ai-agents-board.yml",
        ".ai-agents-board.yaml",
    ];

    for path in &config_paths {
        if Path::new(path).exists() {
            return load_config_file(path);
        }
    }

    // Fall back to environment variables
    load_config_from_env()
}

/// Load configuration from a YAML file.
pub fn load_config_file(path: &str) -> Result<BoardConfig> {
    let content = fs::read_to_string(path)
        .map_err(|e| BoardError::Config(format!("Failed to read config file '{}': {}", path, e)))?;

    let config: ConfigFile = serde_yaml::from_str(&content)
        .map_err(|e| BoardError::Config(format!("Failed to parse config file '{}': {}", path, e)))?;

    Ok(config.into())
}

/// Load configuration from environment variables.
pub fn load_config_from_env() -> Result<BoardConfig> {
    let project_number = std::env::var("BOARD_PROJECT_NUMBER")
        .map_err(|_| BoardError::Config("BOARD_PROJECT_NUMBER not set".to_string()))?
        .parse()
        .map_err(|_| BoardError::Config("Invalid BOARD_PROJECT_NUMBER".to_string()))?;

    let owner = std::env::var("BOARD_OWNER")
        .map_err(|_| BoardError::Config("BOARD_OWNER not set".to_string()))?;

    let repository = std::env::var("BOARD_REPOSITORY")
        .map_err(|_| BoardError::Config("BOARD_REPOSITORY not set".to_string()))?;

    Ok(BoardConfig {
        project_number,
        owner,
        repository,
        ..Default::default()
    })
}

/// Get GitHub token from environment.
pub fn get_github_token() -> Result<String> {
    // Prefer GITHUB_PROJECTS_TOKEN (classic token for Projects v2)
    if let Ok(token) = std::env::var("GITHUB_PROJECTS_TOKEN") {
        return Ok(token);
    }

    // Fall back to GITHUB_TOKEN
    std::env::var("GITHUB_TOKEN")
        .map_err(|_| BoardError::Auth(
            "GitHub token required. Set GITHUB_PROJECTS_TOKEN or GITHUB_TOKEN environment variable".to_string()
        ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_file_default() {
        let config = ConfigFile::default();
        assert_eq!(config.work_claims.timeout, 86400);
    }

    #[test]
    fn test_config_conversion() {
        let file_config = ConfigFile {
            project: ProjectConfig {
                number: 1,
                owner: "test".to_string(),
            },
            repository: "test/repo".to_string(),
            ..Default::default()
        };

        let board_config: BoardConfig = file_config.into();
        assert_eq!(board_config.project_number, 1);
        assert_eq!(board_config.owner, "test");
        assert_eq!(board_config.repository, "test/repo");
    }
}
