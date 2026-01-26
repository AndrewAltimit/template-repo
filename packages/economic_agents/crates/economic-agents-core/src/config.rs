//! Agent configuration.

use economic_agents_interfaces::Skill;
use serde::{Deserialize, Serialize};

/// Decision engine type.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum EngineType {
    /// Rule-based decision making.
    #[default]
    RuleBased,
    /// LLM-powered decision making.
    Llm,
}

/// Agent operating mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum OperatingMode {
    /// Survival mode: focus on maintaining compute resources.
    #[default]
    Survival,
    /// Company mode: work toward company formation.
    Company,
}

/// Agent personality affecting risk tolerance.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum Personality {
    /// Conservative, low-risk decisions.
    RiskAverse,
    /// Balanced approach.
    #[default]
    Balanced,
    /// Aggressive, high-risk/reward decisions.
    Aggressive,
}

/// Task selection strategy.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum TaskSelectionStrategy {
    /// Take the first available task.
    #[default]
    FirstAvailable,
    /// Select the task with highest reward.
    HighestReward,
    /// Select the task with best reward/hour ratio.
    BestRatio,
    /// Balance reward, difficulty, and time.
    Balanced,
    /// Prefer tasks matching agent skills.
    SkillMatch,
}

/// Agent configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    /// Decision engine type.
    #[serde(default)]
    pub engine_type: EngineType,

    /// Operating mode.
    #[serde(default)]
    pub mode: OperatingMode,

    /// Agent personality.
    #[serde(default)]
    pub personality: Personality,

    /// Task selection strategy.
    #[serde(default)]
    pub task_selection_strategy: TaskSelectionStrategy,

    /// Skills this agent possesses.
    #[serde(default)]
    pub skills: Vec<Skill>,

    /// Proficiency levels for each skill (0.0-1.0).
    /// Maps to skills vector by index.
    #[serde(default)]
    pub skill_levels: Vec<f64>,

    /// Minimum hours to keep in reserve.
    #[serde(default = "default_survival_buffer")]
    pub survival_buffer_hours: f64,

    /// Balance threshold for company formation.
    #[serde(default = "default_company_threshold")]
    pub company_threshold: f64,

    /// LLM timeout in seconds.
    #[serde(default = "default_llm_timeout")]
    pub llm_timeout_secs: u64,

    /// Whether to fall back to rule-based when LLM fails.
    #[serde(default = "default_true")]
    pub fallback_enabled: bool,

    /// Maximum cycles to run (None = unlimited).
    pub max_cycles: Option<u32>,
}

fn default_survival_buffer() -> f64 {
    24.0
}

fn default_company_threshold() -> f64 {
    100.0
}

fn default_llm_timeout() -> u64 {
    900
}

fn default_true() -> bool {
    true
}

impl Default for AgentConfig {
    fn default() -> Self {
        Self {
            engine_type: EngineType::default(),
            mode: OperatingMode::default(),
            personality: Personality::default(),
            task_selection_strategy: TaskSelectionStrategy::default(),
            skills: Vec::new(),
            skill_levels: Vec::new(),
            survival_buffer_hours: default_survival_buffer(),
            company_threshold: default_company_threshold(),
            llm_timeout_secs: default_llm_timeout(),
            fallback_enabled: true,
            max_cycles: None,
        }
    }
}

impl AgentConfig {
    /// Get the proficiency level for a skill (0.0 if not possessed).
    pub fn skill_proficiency(&self, skill: Skill) -> f64 {
        self.skills
            .iter()
            .position(|s| *s == skill)
            .and_then(|idx| self.skill_levels.get(idx).copied())
            .unwrap_or(0.0)
    }

    /// Check if agent has a skill at any level.
    pub fn has_skill(&self, skill: Skill) -> bool {
        self.skills.contains(&skill)
    }

    /// Add a skill with proficiency level.
    pub fn add_skill(&mut self, skill: Skill, level: f64) {
        if let Some(idx) = self.skills.iter().position(|s| *s == skill) {
            // Update existing skill level
            if idx < self.skill_levels.len() {
                self.skill_levels[idx] = level.clamp(0.0, 1.0);
            }
        } else {
            // Add new skill
            self.skills.push(skill);
            self.skill_levels.push(level.clamp(0.0, 1.0));
        }
    }
}
