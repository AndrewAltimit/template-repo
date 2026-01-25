//! Predefined scenarios for agent simulations.

use serde::{Deserialize, Serialize};

use crate::config::{
    AgentFileConfig, EngineTypeConfig, OperatingModeConfig, PersonalityConfig, TaskStrategyConfig,
};

/// A predefined scenario configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Scenario {
    /// Scenario name.
    pub name: String,
    /// Description.
    pub description: String,
    /// Agent configurations.
    pub agents: Vec<AgentFileConfig>,
    /// Maximum cycles per agent.
    pub max_cycles: Option<u32>,
    /// Run agents in parallel.
    pub parallel: bool,
    /// Initial market phase.
    pub initial_market: Option<String>,
}

impl Scenario {
    /// Get a scenario by name.
    pub fn by_name(name: &str) -> Option<Self> {
        match name.to_lowercase().as_str() {
            "survival_mode" | "survival" => Some(Self::survival_mode()),
            "company_formation" | "company" => Some(Self::company_formation()),
            "multi_agent" | "multi" => Some(Self::multi_agent()),
            "competition" | "compete" => Some(Self::competition()),
            "market_crash" | "crash" => Some(Self::market_crash()),
            "investment_round" | "investment" => Some(Self::investment_round()),
            _ => None,
        }
    }

    /// List all available scenarios.
    pub fn list_all() -> Vec<(&'static str, &'static str)> {
        vec![
            ("survival_mode", "Single agent in survival mode, focused on task completion"),
            ("company_formation", "Agent progresses to company formation stage"),
            ("multi_agent", "Multiple agents running in parallel"),
            ("competition", "Agents competing for the same tasks"),
            ("market_crash", "Simulation with market crash event"),
            ("investment_round", "Company seeking and receiving investment"),
        ]
    }

    /// Survival mode scenario - single agent focused on survival.
    pub fn survival_mode() -> Self {
        Self {
            name: "survival_mode".to_string(),
            description: "Single agent in survival mode, focused on task completion".to_string(),
            agents: vec![AgentFileConfig {
                agent_id: Some("survivor-1".to_string()),
                engine_type: EngineTypeConfig::RuleBased,
                mode: OperatingModeConfig::Survival,
                personality: PersonalityConfig::Balanced,
                task_selection_strategy: TaskStrategyConfig::HighestReward,
                survival_buffer_hours: 24.0,
                company_threshold: 100.0,
                max_cycles: Some(50),
                initial_balance: Some(10.0),
                initial_compute_hours: Some(100.0),
            }],
            max_cycles: Some(50),
            parallel: false,
            initial_market: Some("stable".to_string()),
        }
    }

    /// Company formation scenario.
    pub fn company_formation() -> Self {
        Self {
            name: "company_formation".to_string(),
            description: "Agent progresses to company formation stage".to_string(),
            agents: vec![AgentFileConfig {
                agent_id: Some("entrepreneur-1".to_string()),
                engine_type: EngineTypeConfig::RuleBased,
                mode: OperatingModeConfig::Company,
                personality: PersonalityConfig::Aggressive,
                task_selection_strategy: TaskStrategyConfig::HighestReward,
                survival_buffer_hours: 24.0,
                company_threshold: 50.0, // Lower threshold for faster company formation
                max_cycles: Some(100),
                initial_balance: Some(25.0),
                initial_compute_hours: Some(200.0),
            }],
            max_cycles: Some(100),
            parallel: false,
            initial_market: Some("bull".to_string()),
        }
    }

    /// Multi-agent scenario.
    pub fn multi_agent() -> Self {
        Self {
            name: "multi_agent".to_string(),
            description: "Multiple agents running in parallel".to_string(),
            agents: vec![
                AgentFileConfig {
                    agent_id: Some("agent-alpha".to_string()),
                    personality: PersonalityConfig::Aggressive,
                    task_selection_strategy: TaskStrategyConfig::HighestReward,
                    initial_balance: Some(15.0),
                    initial_compute_hours: Some(100.0),
                    ..Default::default()
                },
                AgentFileConfig {
                    agent_id: Some("agent-beta".to_string()),
                    personality: PersonalityConfig::Balanced,
                    task_selection_strategy: TaskStrategyConfig::Balanced,
                    initial_balance: Some(15.0),
                    initial_compute_hours: Some(100.0),
                    ..Default::default()
                },
                AgentFileConfig {
                    agent_id: Some("agent-gamma".to_string()),
                    personality: PersonalityConfig::RiskAverse,
                    task_selection_strategy: TaskStrategyConfig::BestRatio,
                    initial_balance: Some(15.0),
                    initial_compute_hours: Some(100.0),
                    ..Default::default()
                },
            ],
            max_cycles: Some(30),
            parallel: true,
            initial_market: Some("stable".to_string()),
        }
    }

    /// Competition scenario.
    pub fn competition() -> Self {
        Self {
            name: "competition".to_string(),
            description: "Agents competing for the same tasks".to_string(),
            agents: vec![
                AgentFileConfig {
                    agent_id: Some("competitor-1".to_string()),
                    personality: PersonalityConfig::Aggressive,
                    task_selection_strategy: TaskStrategyConfig::HighestReward,
                    initial_balance: Some(10.0),
                    initial_compute_hours: Some(80.0),
                    ..Default::default()
                },
                AgentFileConfig {
                    agent_id: Some("competitor-2".to_string()),
                    personality: PersonalityConfig::Aggressive,
                    task_selection_strategy: TaskStrategyConfig::HighestReward,
                    initial_balance: Some(10.0),
                    initial_compute_hours: Some(80.0),
                    ..Default::default()
                },
                AgentFileConfig {
                    agent_id: Some("competitor-3".to_string()),
                    personality: PersonalityConfig::Aggressive,
                    task_selection_strategy: TaskStrategyConfig::FirstAvailable,
                    initial_balance: Some(10.0),
                    initial_compute_hours: Some(80.0),
                    ..Default::default()
                },
            ],
            max_cycles: Some(25),
            parallel: true,
            initial_market: Some("bear".to_string()),
        }
    }

    /// Market crash scenario.
    pub fn market_crash() -> Self {
        Self {
            name: "market_crash".to_string(),
            description: "Simulation with market crash event".to_string(),
            agents: vec![AgentFileConfig {
                agent_id: Some("crash-survivor".to_string()),
                personality: PersonalityConfig::RiskAverse,
                task_selection_strategy: TaskStrategyConfig::BestRatio,
                survival_buffer_hours: 48.0, // Larger buffer for crash
                initial_balance: Some(20.0),
                initial_compute_hours: Some(150.0),
                ..Default::default()
            }],
            max_cycles: Some(75),
            parallel: false,
            initial_market: Some("crash".to_string()),
        }
    }

    /// Investment round scenario.
    pub fn investment_round() -> Self {
        Self {
            name: "investment_round".to_string(),
            description: "Company seeking and receiving investment".to_string(),
            agents: vec![AgentFileConfig {
                agent_id: Some("startup-ceo".to_string()),
                mode: OperatingModeConfig::Company,
                personality: PersonalityConfig::Aggressive,
                task_selection_strategy: TaskStrategyConfig::HighestReward,
                company_threshold: 30.0,
                survival_buffer_hours: 16.0,
                initial_balance: Some(40.0),
                initial_compute_hours: Some(200.0),
                ..Default::default()
            }],
            max_cycles: Some(150),
            parallel: false,
            initial_market: Some("bull".to_string()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scenario_by_name() {
        assert!(Scenario::by_name("survival_mode").is_some());
        assert!(Scenario::by_name("company_formation").is_some());
        assert!(Scenario::by_name("multi_agent").is_some());
        assert!(Scenario::by_name("competition").is_some());
        assert!(Scenario::by_name("market_crash").is_some());
        assert!(Scenario::by_name("investment_round").is_some());
        assert!(Scenario::by_name("nonexistent").is_none());
    }

    #[test]
    fn test_scenario_list() {
        let list = Scenario::list_all();
        assert_eq!(list.len(), 6);
    }

    #[test]
    fn test_survival_scenario_config() {
        let scenario = Scenario::survival_mode();
        assert_eq!(scenario.agents.len(), 1);
        assert!(!scenario.parallel);
        assert_eq!(scenario.max_cycles, Some(50));
    }

    #[test]
    fn test_multi_agent_scenario_config() {
        let scenario = Scenario::multi_agent();
        assert_eq!(scenario.agents.len(), 3);
        assert!(scenario.parallel);
    }
}
