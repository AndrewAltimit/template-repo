//! Main autonomous agent implementation.

use crate::config::AgentConfig;
use crate::state::AgentState;

/// The main autonomous agent orchestrator.
///
/// Manages the agent lifecycle, decision cycles, resource allocation,
/// and interactions with backend services.
pub struct AutonomousAgent {
    /// Agent configuration.
    pub config: AgentConfig,
    /// Current agent state.
    pub state: AgentState,
    /// Agent identifier.
    pub id: String,
}

impl AutonomousAgent {
    /// Create a new agent with the given configuration.
    pub fn new(config: AgentConfig) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            config,
            state: AgentState::default(),
        }
    }

    /// Run a single decision cycle.
    pub async fn run_cycle(&mut self) -> economic_agents_interfaces::Result<()> {
        // TODO: Implement decision cycle
        tracing::info!(agent_id = %self.id, "Running decision cycle");
        Ok(())
    }

    /// Run the agent for a specified number of cycles.
    pub async fn run(&mut self, max_cycles: Option<u32>) -> economic_agents_interfaces::Result<()> {
        let max = max_cycles.unwrap_or(u32::MAX);
        for cycle in 0..max {
            tracing::info!(agent_id = %self.id, cycle, "Starting cycle");
            self.run_cycle().await?;
        }
        Ok(())
    }
}
