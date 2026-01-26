//! Agent runner for executing simulations.

use std::sync::Arc;
use std::time::Instant;

use tokio::sync::Mutex;
use tracing::{error, info, warn};

use economic_agents_core::{AutonomousAgent, Backends, CycleResult};
use economic_agents_mock::{MockBackendConfig, MockBackendFactory};
use economic_agents_monitoring::EventBus;
use economic_agents_simulation::MarketDynamics;

use crate::config::AgentFileConfig;
use crate::scenarios::Scenario;

/// Result from running an agent.
#[derive(Debug, Clone)]
pub struct AgentRunResult {
    /// Agent ID.
    pub agent_id: String,
    /// Final balance.
    pub final_balance: f64,
    /// Total earnings.
    pub total_earnings: f64,
    /// Total expenses.
    pub total_expenses: f64,
    /// Tasks completed.
    pub tasks_completed: u32,
    /// Tasks failed.
    pub tasks_failed: u32,
    /// Cycles executed.
    pub cycles_executed: u32,
    /// Has company.
    pub has_company: bool,
    /// Run duration in ms.
    pub duration_ms: u64,
    /// Cycle results (optional, may be empty to save memory).
    pub cycles: Vec<CycleResult>,
}

impl AgentRunResult {
    /// Calculate success rate.
    pub fn success_rate(&self) -> f64 {
        let total = self.tasks_completed + self.tasks_failed;
        if total == 0 {
            0.0
        } else {
            self.tasks_completed as f64 / total as f64
        }
    }

    /// Calculate net profit.
    pub fn net_profit(&self) -> f64 {
        self.total_earnings - self.total_expenses
    }
}

/// Result from running a scenario.
#[derive(Debug)]
pub struct ScenarioResult {
    /// Scenario name.
    pub name: String,
    /// Results per agent.
    pub agent_results: Vec<AgentRunResult>,
    /// Total duration in ms.
    pub duration_ms: u64,
}

impl ScenarioResult {
    /// Get the best performing agent by net profit.
    pub fn best_performer(&self) -> Option<&AgentRunResult> {
        self.agent_results
            .iter()
            .max_by(|a, b| a.net_profit().partial_cmp(&b.net_profit()).unwrap())
    }

    /// Print a summary to stdout.
    pub fn print_summary(&self) {
        println!("\n=== Scenario Results: {} ===", self.name);
        println!("Total duration: {}ms", self.duration_ms);
        println!("Agents: {}", self.agent_results.len());
        println!();

        for result in &self.agent_results {
            println!("Agent: {}", result.agent_id);
            println!("  Cycles: {}", result.cycles_executed);
            println!(
                "  Tasks: {} completed, {} failed",
                result.tasks_completed, result.tasks_failed
            );
            println!("  Success rate: {:.1}%", result.success_rate() * 100.0);
            println!("  Final balance: ${:.2}", result.final_balance);
            println!("  Net profit: ${:.2}", result.net_profit());
            println!("  Has company: {}", result.has_company);
            println!();
        }

        if let Some(best) = self.best_performer() {
            println!(
                "Best performer: {} (${:.2} profit)",
                best.agent_id,
                best.net_profit()
            );
        }
    }
}

/// Run a single agent with mock backends.
pub async fn run_agent(
    config: AgentFileConfig,
    _event_bus: Option<Arc<EventBus>>,
    keep_cycles: bool,
) -> anyhow::Result<AgentRunResult> {
    let start = Instant::now();

    // Create mock backend config
    let mock_config = MockBackendConfig {
        initial_balance: config.initial_balance.unwrap_or(10.0),
        initial_compute_hours: config.initial_compute_hours.unwrap_or(100.0),
        compute_cost_per_hour: 0.1,
        initial_tasks: 20,
    };

    // Create mock backends
    let mock_backends = MockBackendFactory::create_with_config(mock_config).await;
    let backends = Backends::new(
        Arc::new(mock_backends.wallet),
        Arc::new(mock_backends.marketplace),
        Arc::new(mock_backends.compute),
    );

    // Create agent
    let agent_config = config.to_agent_config();
    let mut agent = AutonomousAgent::with_backends(agent_config, backends);

    // Override agent ID if specified
    if let Some(id) = &config.agent_id {
        // Note: We can't easily change the ID after creation, so this is informational
        info!(agent_id = %agent.id, requested_id = %id, "Created agent");
    }

    // Initialize state from backends
    if let Err(e) = agent.initialize().await {
        warn!(error = %e, "Failed to initialize agent state");
    }

    // Run cycles
    let max_cycles = config.max_cycles;
    let results = agent.run(max_cycles).await?;

    // Build result
    let result = AgentRunResult {
        agent_id: config.agent_id.unwrap_or_else(|| agent.id.clone()),
        final_balance: agent.state.balance,
        total_earnings: agent.state.total_earnings,
        total_expenses: agent.state.total_expenses,
        tasks_completed: agent.state.tasks_completed,
        tasks_failed: agent.state.tasks_failed,
        cycles_executed: agent.state.current_cycle,
        has_company: agent.state.has_company,
        duration_ms: start.elapsed().as_millis() as u64,
        cycles: if keep_cycles { results } else { Vec::new() },
    };

    // TODO: Emit event if event bus provided

    Ok(result)
}

/// Run a scenario.
pub async fn run_scenario(scenario: Scenario, keep_cycles: bool) -> anyhow::Result<ScenarioResult> {
    let start = Instant::now();

    info!(
        name = %scenario.name,
        agents = %scenario.agents.len(),
        parallel = %scenario.parallel,
        "Running scenario"
    );

    let event_bus = Arc::new(EventBus::default());
    let market = Arc::new(Mutex::new(MarketDynamics::new()));

    // Note: Parallel execution is disabled due to thread_rng not being Send-safe.
    // All agents run sequentially, which is actually more realistic for simulation.
    let mut agent_results = Vec::new();

    for agent_config in scenario.agents {
        match run_agent(agent_config, Some(Arc::clone(&event_bus)), keep_cycles).await {
            Ok(result) => agent_results.push(result),
            Err(e) => error!(error = %e, "Agent failed"),
        }

        // Tick market between agents
        let mut mkt = market.lock().await;
        mkt.tick();
    }

    Ok(ScenarioResult {
        name: scenario.name,
        agent_results,
        duration_ms: start.elapsed().as_millis() as u64,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_run_agent() {
        let config = AgentFileConfig {
            agent_id: Some("test-agent".to_string()),
            max_cycles: Some(3),
            initial_balance: Some(50.0),
            initial_compute_hours: Some(100.0),
            ..Default::default()
        };

        let result = run_agent(config, None, false).await.unwrap();

        assert_eq!(result.agent_id, "test-agent");
        assert!(result.cycles_executed <= 3);
        // Duration may be 0 on fast systems
    }

    #[tokio::test]
    async fn test_run_scenario_survival() {
        let mut scenario = Scenario::survival_mode();
        scenario.agents[0].max_cycles = Some(2); // Limit for faster test

        let result = run_scenario(scenario, false).await.unwrap();

        assert_eq!(result.name, "survival_mode");
        assert_eq!(result.agent_results.len(), 1);
        // Duration may be 0 on fast systems
    }

    #[tokio::test]
    async fn test_run_scenario_multi_agent() {
        let mut scenario = Scenario::multi_agent();
        for agent in &mut scenario.agents {
            agent.max_cycles = Some(2); // Limit for faster test
        }

        let result = run_scenario(scenario, false).await.unwrap();

        assert_eq!(result.name, "multi_agent");
        assert_eq!(result.agent_results.len(), 3);
    }

    #[test]
    fn test_agent_run_result_metrics() {
        let result = AgentRunResult {
            agent_id: "test".to_string(),
            final_balance: 100.0,
            total_earnings: 80.0,
            total_expenses: 30.0,
            tasks_completed: 8,
            tasks_failed: 2,
            cycles_executed: 10,
            has_company: false,
            duration_ms: 1000,
            cycles: Vec::new(),
        };

        assert_eq!(result.success_rate(), 0.8);
        assert_eq!(result.net_profit(), 50.0);
    }
}
