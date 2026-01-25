//! CLI configuration types.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

use economic_agents_core::{EngineType, OperatingMode, Personality, TaskSelectionStrategy};

/// Agent configuration loaded from file.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct AgentFileConfig {
    /// Agent name/ID.
    pub agent_id: Option<String>,
    /// Decision engine type.
    pub engine_type: EngineTypeConfig,
    /// Operating mode.
    pub mode: OperatingModeConfig,
    /// Personality type.
    pub personality: PersonalityConfig,
    /// Task selection strategy.
    pub task_selection_strategy: TaskStrategyConfig,
    /// Hours of compute to keep as survival buffer.
    pub survival_buffer_hours: f64,
    /// Capital threshold to consider company formation.
    pub company_threshold: f64,
    /// Maximum cycles to run.
    pub max_cycles: Option<u32>,
    /// Initial balance for mock backends.
    pub initial_balance: Option<f64>,
    /// Initial compute hours for mock backends.
    pub initial_compute_hours: Option<f64>,
}

impl Default for AgentFileConfig {
    fn default() -> Self {
        Self {
            agent_id: None,
            engine_type: EngineTypeConfig::RuleBased,
            mode: OperatingModeConfig::Survival,
            personality: PersonalityConfig::Balanced,
            task_selection_strategy: TaskStrategyConfig::HighestReward,
            survival_buffer_hours: 24.0,
            company_threshold: 100.0,
            max_cycles: None,
            initial_balance: None,
            initial_compute_hours: None,
        }
    }
}

impl AgentFileConfig {
    /// Load from a YAML file.
    pub fn from_file(path: &PathBuf) -> anyhow::Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: Self = serde_yaml::from_str(&content)?;
        Ok(config)
    }

    /// Convert to core AgentConfig.
    pub fn to_agent_config(&self) -> economic_agents_core::AgentConfig {
        economic_agents_core::AgentConfig {
            engine_type: self.engine_type.into(),
            mode: self.mode.into(),
            personality: self.personality.into(),
            task_selection_strategy: self.task_selection_strategy.into(),
            skills: Vec::new(),
            skill_levels: Vec::new(),
            survival_buffer_hours: self.survival_buffer_hours,
            company_threshold: self.company_threshold,
            max_cycles: self.max_cycles,
            llm_timeout_secs: 900,
            fallback_enabled: true,
        }
    }
}

/// Engine type for config file.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EngineTypeConfig {
    #[default]
    RuleBased,
    Llm,
}

impl From<EngineTypeConfig> for EngineType {
    fn from(c: EngineTypeConfig) -> Self {
        match c {
            EngineTypeConfig::RuleBased => EngineType::RuleBased,
            EngineTypeConfig::Llm => EngineType::Llm,
        }
    }
}

/// Operating mode for config file.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OperatingModeConfig {
    #[default]
    Survival,
    Company,
}

impl From<OperatingModeConfig> for OperatingMode {
    fn from(c: OperatingModeConfig) -> Self {
        match c {
            OperatingModeConfig::Survival => OperatingMode::Survival,
            OperatingModeConfig::Company => OperatingMode::Company,
        }
    }
}

/// Personality for config file.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PersonalityConfig {
    #[default]
    Balanced,
    Aggressive,
    RiskAverse,
}

impl From<PersonalityConfig> for Personality {
    fn from(c: PersonalityConfig) -> Self {
        match c {
            PersonalityConfig::Balanced => Personality::Balanced,
            PersonalityConfig::Aggressive => Personality::Aggressive,
            PersonalityConfig::RiskAverse => Personality::RiskAverse,
        }
    }
}

/// Task selection strategy for config file.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskStrategyConfig {
    FirstAvailable,
    #[default]
    HighestReward,
    BestRatio,
    Balanced,
}

impl From<TaskStrategyConfig> for TaskSelectionStrategy {
    fn from(c: TaskStrategyConfig) -> Self {
        match c {
            TaskStrategyConfig::FirstAvailable => TaskSelectionStrategy::FirstAvailable,
            TaskStrategyConfig::HighestReward => TaskSelectionStrategy::HighestReward,
            TaskStrategyConfig::BestRatio => TaskSelectionStrategy::BestRatio,
            TaskStrategyConfig::Balanced => TaskSelectionStrategy::Balanced,
        }
    }
}

/// Dashboard server configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct DashboardFileConfig {
    /// Port to listen on.
    pub port: u16,
    /// Host to bind to.
    pub host: String,
    /// Enable CORS.
    pub enable_cors: bool,
    /// Enable request tracing.
    pub enable_tracing: bool,
}

impl Default for DashboardFileConfig {
    fn default() -> Self {
        Self {
            port: 8000,
            host: "0.0.0.0".to_string(),
            enable_cors: true,
            enable_tracing: true,
        }
    }
}
