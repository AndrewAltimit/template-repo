//! Configuration loading for board manager.
//!
//! Resolution order for the board config file:
//! 1. `--config <PATH>` (must exist)
//! 2. `BOARD_CONFIG_PATH` env var (used if the file exists, otherwise a
//!    warning is logged and discovery continues)
//! 3. `ai-agents-board.yml` (and `.yaml` / dot-prefixed variants) in the
//!    current directory or any parent directory
//! 4. Environment variables (`BOARD_PROJECT_NUMBER`, `BOARD_OWNER`,
//!    `BOARD_REPOSITORY` / `GITHUB_REPOSITORY`)

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use tracing::{debug, warn};

use crate::error::{BoardError, Result};
use crate::models::BoardConfig;

/// Config file names searched for, in priority order.
const CONFIG_FILE_NAMES: &[&str] = &[
    "ai-agents-board.yml",
    "ai-agents-board.yaml",
    ".ai-agents-board.yml",
    ".ai-agents-board.yaml",
];

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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentsConfig {
    #[serde(default)]
    pub enabled_agents: Vec<String>,
    #[serde(default = "default_true")]
    pub auto_discover: bool,
}

impl Default for AgentsConfig {
    fn default() -> Self {
        Self {
            enabled_agents: Vec::new(),
            auto_discover: true,
        }
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WorkQueueConfig {
    #[serde(default)]
    pub exclude_labels: Vec<String>,
    #[serde(default)]
    pub priority_labels: HashMap<String, Vec<String>>,
    #[serde(default)]
    pub type_labels: HashMap<String, Vec<String>>,
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
            type_labels: cfg.work_queue.type_labels,
        }
    }
}

/// Load and validate the board configuration.
pub fn load_config(explicit_path: Option<&Path>) -> Result<BoardConfig> {
    let config = match resolve_config_path(explicit_path)? {
        Some(path) => {
            debug!("Loading board config from {}", path.display());
            load_config_file(&path)?
        },
        None => {
            debug!("No board config file found, using environment variables");
            load_config_from_env()?
        },
    };
    validate_config(&config)?;
    Ok(config)
}

/// Determine which config file (if any) to load.
fn resolve_config_path(explicit_path: Option<&Path>) -> Result<Option<PathBuf>> {
    if let Some(path) = explicit_path {
        return if path.is_file() {
            Ok(Some(path.to_path_buf()))
        } else {
            Err(BoardError::Config(format!(
                "Config file not found: {}",
                path.display()
            )))
        };
    }

    if let Some(env_path) = env_non_empty("BOARD_CONFIG_PATH") {
        let path = PathBuf::from(&env_path);
        if path.is_file() {
            return Ok(Some(path));
        }
        warn!(
            "BOARD_CONFIG_PATH={} does not exist; falling back to discovery",
            env_path
        );
    }

    let cwd = std::env::current_dir()?;
    Ok(find_config_upwards(&cwd))
}

/// Search `start` and its ancestors for a known config file name.
pub fn find_config_upwards(start: &Path) -> Option<PathBuf> {
    start.ancestors().find_map(|dir| {
        CONFIG_FILE_NAMES
            .iter()
            .map(|name| dir.join(name))
            .find(|p| p.is_file())
    })
}

/// Load configuration from a YAML file.
pub fn load_config_file(path: &Path) -> Result<BoardConfig> {
    let content = fs::read_to_string(path).map_err(|e| {
        BoardError::Config(format!(
            "Failed to read config file '{}': {}",
            path.display(),
            e
        ))
    })?;
    parse_config_str(&content)
        .map_err(|e| BoardError::Config(format!("Failed to parse '{}': {}", path.display(), e)))
}

/// Parse configuration from YAML text.
pub fn parse_config_str(content: &str) -> std::result::Result<BoardConfig, serde_yaml::Error> {
    serde_yaml::from_str::<ConfigFile>(content).map(Into::into)
}

/// Load configuration from environment variables.
pub fn load_config_from_env() -> Result<BoardConfig> {
    let number = env_non_empty("BOARD_PROJECT_NUMBER").ok_or_else(|| {
        BoardError::Config(
            "No ai-agents-board.yml found and BOARD_PROJECT_NUMBER is not set".to_string(),
        )
    })?;
    let project_number = number
        .trim()
        .parse()
        .map_err(|_| BoardError::Config(format!("Invalid BOARD_PROJECT_NUMBER '{}'", number)))?;

    let repository = env_non_empty("BOARD_REPOSITORY")
        .or_else(|| env_non_empty("GITHUB_REPOSITORY"))
        .ok_or_else(|| {
            BoardError::Config("BOARD_REPOSITORY or GITHUB_REPOSITORY must be set".to_string())
        })?;

    let owner = env_non_empty("BOARD_OWNER")
        .or_else(|| repository.split_once('/').map(|(o, _)| o.to_string()))
        .ok_or_else(|| BoardError::Config("BOARD_OWNER not set".to_string()))?;

    Ok(BoardConfig {
        project_number,
        owner,
        repository,
        ..Default::default()
    })
}

/// Reject configurations that cannot possibly work.
pub fn validate_config(config: &BoardConfig) -> Result<()> {
    if config.project_number == 0 {
        return Err(BoardError::Config(
            "project.number must be set to a positive project number".to_string(),
        ));
    }
    if config.owner.trim().is_empty() {
        return Err(BoardError::Config("project.owner must be set".to_string()));
    }
    if config.repo_parts().is_none() {
        return Err(BoardError::Config(format!(
            "repository must be in 'owner/repo' format (got '{}')",
            config.repository
        )));
    }
    if config.claim_timeout <= 0 {
        return Err(BoardError::Config(
            "work_claims.timeout must be positive".to_string(),
        ));
    }
    Ok(())
}

/// Get the GitHub token from the environment.
///
/// Prefers `GITHUB_PROJECTS_TOKEN` (a classic token with project scope),
/// then `GITHUB_TOKEN`, then `GH_TOKEN`. Empty values are ignored, which
/// matters in Actions where an unset secret expands to an empty string.
pub fn get_github_token() -> Result<String> {
    ["GITHUB_PROJECTS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"]
        .iter()
        .find_map(|name| env_non_empty(name))
        .ok_or_else(|| {
            BoardError::Auth(
                "GitHub token required. Set GITHUB_PROJECTS_TOKEN, GITHUB_TOKEN or GH_TOKEN"
                    .to_string(),
            )
        })
}

fn env_non_empty(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn config_file_default() {
        let config = ConfigFile::default();
        assert_eq!(config.work_claims.timeout, 86400);
        assert!(config.agents.auto_discover);
    }

    #[test]
    fn config_conversion() {
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
        assert!(validate_config(&board_config).is_ok());
    }

    #[test]
    fn parses_repo_config_shape() {
        let yaml = r#"
project:
  number: 2
  owner: "AndrewAltimit"
repository: "AndrewAltimit/template-repo"
fields:
  status: "Board Status"
agents:
  enabled_agents: ["claude", "crush"]
work_claims:
  timeout: 7200
  notify_expired: false
work_queue:
  exclude_labels: ["wontfix"]
  priority_labels:
    high: ["bug"]
  type_labels:
    tech_debt: ["refactor"]
integration:
  auto_add_issues: true
"#;
        let c = parse_config_str(yaml).unwrap();
        assert_eq!(c.project_number, 2);
        assert_eq!(c.get_field_name("status"), "Board Status");
        assert_eq!(c.get_field_name("priority"), "Priority");
        assert_eq!(c.claim_timeout, 7200);
        assert_eq!(c.enabled_agents, vec!["claude", "crush"]);
        assert_eq!(c.exclude_labels, vec!["wontfix"]);
        assert_eq!(c.type_labels["tech_debt"], vec!["refactor"]);
        assert!(validate_config(&c).is_ok());
    }

    #[test]
    fn validation_rejects_bad_configs() {
        let good = BoardConfig {
            project_number: 1,
            owner: "o".into(),
            repository: "o/r".into(),
            ..Default::default()
        };
        assert!(validate_config(&good).is_ok());

        let cases = [
            BoardConfig {
                project_number: 0,
                ..good.clone()
            },
            BoardConfig {
                owner: " ".into(),
                ..good.clone()
            },
            BoardConfig {
                repository: "norepo".into(),
                ..good.clone()
            },
            BoardConfig {
                claim_timeout: 0,
                ..good.clone()
            },
        ];
        for c in cases {
            assert!(matches!(validate_config(&c), Err(BoardError::Config(_))));
        }
    }

    #[test]
    fn finds_config_in_parent_directory() {
        let base = std::env::temp_dir().join(format!("bm-cfg-{}", uuid::Uuid::new_v4()));
        let nested = base.join("a").join("b");
        fs::create_dir_all(&nested).unwrap();
        fs::write(base.join("ai-agents-board.yml"), "project:\n  number: 1\n").unwrap();

        let found = find_config_upwards(&nested).unwrap();
        assert_eq!(found, base.join("ai-agents-board.yml"));

        fs::remove_dir_all(&base).unwrap();
    }

    #[test]
    fn explicit_missing_path_is_error() {
        let missing = Path::new("/definitely/not/here/board.yml");
        assert!(matches!(
            resolve_config_path(Some(missing)),
            Err(BoardError::Config(_))
        ));
    }
}
