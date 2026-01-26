//! Decision engine implementations.

use async_trait::async_trait;
use economic_agents_interfaces::Result;

use crate::config::{AgentConfig, Personality};
use crate::state::AgentState;

/// A decision made by the agent.
#[derive(Debug, Clone)]
pub struct Decision {
    /// Type of decision.
    pub decision_type: DecisionType,
    /// Reasoning behind the decision.
    pub reasoning: String,
    /// Confidence level (0.0-1.0).
    pub confidence: f64,
}

/// Types of decisions an agent can make.
#[derive(Debug, Clone, PartialEq)]
pub enum DecisionType {
    /// Work on marketplace tasks.
    WorkOnTasks,
    /// Purchase more compute time.
    PurchaseCompute { hours: f64 },
    /// Work on company formation.
    WorkOnCompany,
    /// Seek investment.
    SeekInvestment,
    /// Wait/idle.
    Wait,
}

/// Allocation of resources between activities.
#[derive(Debug, Clone)]
pub struct ResourceAllocation {
    /// Percentage of time for task work.
    pub task_work: f64,
    /// Percentage of time for company work.
    pub company_work: f64,
    /// Percentage of time for other activities.
    pub other: f64,
}

impl Default for ResourceAllocation {
    fn default() -> Self {
        Self {
            task_work: 1.0,
            company_work: 0.0,
            other: 0.0,
        }
    }
}

/// Trait for decision engines.
#[async_trait]
pub trait DecisionEngine: Send + Sync {
    /// Make a decision based on current state.
    async fn decide(&self, state: &AgentState, config: &AgentConfig) -> Result<Decision>;

    /// Determine resource allocation.
    async fn allocate_resources(
        &self,
        state: &AgentState,
        config: &AgentConfig,
    ) -> Result<ResourceAllocation>;
}

/// Rule-based decision engine.
pub struct RuleBasedEngine;

impl RuleBasedEngine {
    pub fn new() -> Self {
        Self
    }
}

impl Default for RuleBasedEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl DecisionEngine for RuleBasedEngine {
    async fn decide(&self, state: &AgentState, config: &AgentConfig) -> Result<Decision> {
        // Simple rule-based logic
        let decision_type = if state.compute_hours < config.survival_buffer_hours {
            // Need more compute
            if state.balance > 10.0 {
                DecisionType::PurchaseCompute {
                    hours: config.survival_buffer_hours - state.compute_hours,
                }
            } else {
                DecisionType::WorkOnTasks
            }
        } else if state.has_company {
            // Already has a company, work on it
            DecisionType::WorkOnCompany
        } else if state.balance >= config.company_threshold {
            // Enough capital to form company
            DecisionType::WorkOnCompany
        } else {
            // Default: work on tasks
            DecisionType::WorkOnTasks
        };

        let confidence = match config.personality {
            Personality::RiskAverse => 0.9,
            Personality::Balanced => 0.75,
            Personality::Aggressive => 0.6,
        };

        Ok(Decision {
            decision_type,
            reasoning: "Rule-based decision".to_string(),
            confidence,
        })
    }

    async fn allocate_resources(
        &self,
        state: &AgentState,
        config: &AgentConfig,
    ) -> Result<ResourceAllocation> {
        if state.has_company {
            Ok(ResourceAllocation {
                task_work: 0.4,
                company_work: 0.5,
                other: 0.1,
            })
        } else if state.balance >= config.company_threshold * 0.8 {
            Ok(ResourceAllocation {
                task_work: 0.6,
                company_work: 0.3,
                other: 0.1,
            })
        } else {
            Ok(ResourceAllocation::default())
        }
    }
}
