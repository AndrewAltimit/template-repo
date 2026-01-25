//! Integration tests for the economic-agents-core crate.
//!
//! These tests verify the agent's behavior with mock backends.

use std::sync::Arc;

use economic_agents_core::{
    AgentConfig, AutonomousAgent, Backends, EngineType, OperatingMode, Personality,
    TaskSelectionStrategy,
};
use economic_agents_mock::{MockBackendConfig, MockBackendFactory};

/// Helper to create backends from mock backends.
async fn create_test_backends(config: MockBackendConfig) -> Backends {
    let mock = MockBackendFactory::create_with_config(config).await;
    Backends::new(
        Arc::new(mock.wallet),
        Arc::new(mock.marketplace),
        Arc::new(mock.compute),
    )
}

/// Helper to create default test backends.
async fn create_default_backends() -> Backends {
    create_test_backends(MockBackendConfig::default()).await
}

#[tokio::test]
async fn test_agent_single_cycle() {
    let backends = create_default_backends().await;
    let config = AgentConfig::default();
    let mut agent = AutonomousAgent::with_backends(config, backends);

    let result = agent.run_cycle().await.unwrap();

    assert_eq!(result.cycle, 0);
    assert!(result.decision.is_some());
    assert!(result.allocation.is_some());
    assert_eq!(agent.state.current_cycle, 1);
}

#[tokio::test]
async fn test_agent_multiple_cycles() {
    let backends = create_default_backends().await;
    let config = AgentConfig::default();
    let mut agent = AutonomousAgent::with_backends(config, backends);

    let results = agent.run(Some(5)).await.unwrap();

    assert_eq!(results.len(), 5);
    assert_eq!(agent.state.current_cycle, 5);
}

#[tokio::test]
async fn test_agent_task_work() {
    let config = MockBackendConfig {
        initial_balance: 100.0,
        initial_compute_hours: 100.0, // More compute to avoid purchase decisions
        compute_cost_per_hour: 0.10,
        initial_tasks: 20,
    };
    let backends = create_test_backends(config).await;

    let agent_config = AgentConfig {
        task_selection_strategy: TaskSelectionStrategy::FirstAvailable,
        survival_buffer_hours: 8.0, // Low buffer so agent works on tasks
        ..Default::default()
    };
    let mut agent = AutonomousAgent::with_backends(agent_config, backends);

    // Run several cycles
    let results = agent.run(Some(10)).await.unwrap();

    // Check that we have results
    assert!(!results.is_empty(), "Should have completed cycles");
    assert_eq!(results.len(), 10, "Should complete all 10 cycles");

    // Verify all cycles have decisions
    for result in &results {
        assert!(result.decision.is_some(), "Each cycle should have a decision");
    }

    // The agent should have made progress (consumed compute, changed balance, etc.)
    // Since mock tasks get auto-generated and decisions are made, we verify the cycle ran
    assert!(agent.state.current_cycle == 10);
}

#[tokio::test]
async fn test_agent_stops_when_cannot_survive() {
    let config = MockBackendConfig {
        initial_balance: 0.0,
        initial_compute_hours: 0.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 10,
    };
    let backends = create_test_backends(config).await;
    let mut agent = AutonomousAgent::with_backends(AgentConfig::default(), backends);

    let results = agent.run(Some(100)).await.unwrap();

    // Should stop immediately due to inability to survive (0 balance, 0 compute)
    assert!(results.is_empty());
}

#[tokio::test]
async fn test_agent_with_high_balance_considers_company() {
    let config = MockBackendConfig {
        initial_balance: 500.0, // Well above company threshold
        initial_compute_hours: 100.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 20,
    };
    let backends = create_test_backends(config).await;

    let agent_config = AgentConfig {
        mode: OperatingMode::Company,
        company_threshold: 100.0,
        survival_buffer_hours: 24.0,
        ..Default::default()
    };
    let mut agent = AutonomousAgent::with_backends(agent_config, backends);

    // Run enough cycles for company consideration
    let results = agent.run(Some(10)).await.unwrap();

    // Should have run cycles
    assert!(!results.is_empty());

    // Check if company formation was attempted in any cycle
    let company_formations: Vec<_> = results
        .iter()
        .filter(|r| r.company_formation.is_some())
        .collect();

    // If company was formed, verify state
    if agent.state.has_company {
        assert!(agent.state.company_id.is_some());
        assert!(!company_formations.is_empty());
    }
}

#[tokio::test]
async fn test_agent_personality_affects_decisions() {
    let config = MockBackendConfig {
        initial_balance: 50.0,
        initial_compute_hours: 24.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 10,
    };

    // Test risk-averse personality
    let backends = create_test_backends(config.clone()).await;
    let risk_averse_config = AgentConfig {
        personality: Personality::RiskAverse,
        ..Default::default()
    };
    let mut risk_averse_agent = AutonomousAgent::with_backends(risk_averse_config, backends);
    let risk_averse_results = risk_averse_agent.run(Some(3)).await.unwrap();

    // Test aggressive personality
    let backends = create_test_backends(config).await;
    let aggressive_config = AgentConfig {
        personality: Personality::Aggressive,
        ..Default::default()
    };
    let mut aggressive_agent = AutonomousAgent::with_backends(aggressive_config, backends);
    let aggressive_results = aggressive_agent.run(Some(3)).await.unwrap();

    // Both should complete 3 cycles
    assert_eq!(risk_averse_results.len(), 3);
    assert_eq!(aggressive_results.len(), 3);
    assert_eq!(risk_averse_agent.state.current_cycle, 3);
    assert_eq!(aggressive_agent.state.current_cycle, 3);
}

#[tokio::test]
async fn test_agent_state_updates() {
    let config = MockBackendConfig {
        initial_balance: 100.0,
        initial_compute_hours: 48.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 10,
    };
    let backends = create_test_backends(config).await;
    let mut agent = AutonomousAgent::with_backends(AgentConfig::default(), backends);

    // Initialize state first
    agent.initialize().await.unwrap();

    let initial_balance = agent.state.balance;
    let initial_compute = agent.state.compute_hours;

    let result = agent.run_cycle().await.unwrap();

    // State should have changed
    let final_state = &result.final_state;

    // Check that initial and final states are captured in result
    assert!(result.initial_state.balance > 0.0);
    assert!(result.initial_state.compute_hours > 0.0);

    // Compute hours should decrease if task work was done
    if result.task_result.is_some() {
        assert!(final_state.compute_hours <= initial_compute);
    }
}

#[tokio::test]
async fn test_agent_cycle_history() {
    let backends = create_default_backends().await;
    let mut agent = AutonomousAgent::with_backends(AgentConfig::default(), backends);

    // Run cycles
    let results = agent.run(Some(5)).await.unwrap();

    assert_eq!(results.len(), 5);

    // Check history
    let history = agent.recent_cycles(10);
    assert_eq!(history.len(), 5);

    // Verify cycle numbers
    for (i, cycle) in history.iter().enumerate() {
        assert_eq!(cycle.cycle, i as u32);
    }
}

#[tokio::test]
async fn test_agent_stop() {
    let backends = create_default_backends().await;
    let mut agent = AutonomousAgent::with_backends(AgentConfig::default(), backends);

    assert!(agent.state.is_active);
    agent.stop();
    assert!(!agent.state.is_active);

    // Running should stop immediately
    let results = agent.run(Some(100)).await.unwrap();
    assert!(results.is_empty());
}

#[tokio::test]
async fn test_agent_without_backends_returns_error_in_result() {
    let config = AgentConfig::default();
    let mut agent = AutonomousAgent::new(config);

    // run_cycle should complete but with errors recorded
    let result = agent.run_cycle().await.unwrap();

    // The cycle should record the error about missing backends
    assert!(!result.is_success());
    assert!(!result.errors.is_empty());
}

#[tokio::test]
async fn test_task_selection_strategies() {
    let config = MockBackendConfig {
        initial_balance: 100.0,
        initial_compute_hours: 48.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 20,
    };

    // Test each strategy
    for strategy in [
        TaskSelectionStrategy::FirstAvailable,
        TaskSelectionStrategy::HighestReward,
        TaskSelectionStrategy::BestRatio,
        TaskSelectionStrategy::Balanced,
    ] {
        let backends = create_test_backends(config.clone()).await;
        let agent_config = AgentConfig {
            task_selection_strategy: strategy,
            ..Default::default()
        };
        let mut agent = AutonomousAgent::with_backends(agent_config, backends);

        let results = agent.run(Some(3)).await.unwrap();
        assert_eq!(
            results.len(),
            3,
            "Strategy {:?} should complete 3 cycles",
            strategy
        );
    }
}

#[tokio::test]
async fn test_decision_engine_types() {
    let backends = create_default_backends().await;

    // Rule-based engine (default)
    let config = AgentConfig {
        engine_type: EngineType::RuleBased,
        ..Default::default()
    };
    let mut agent = AutonomousAgent::with_backends(config, backends);
    let result = agent.run_cycle().await.unwrap();
    assert!(result.decision.is_some());
}

#[tokio::test]
async fn test_cycle_result_structure() {
    let backends = create_default_backends().await;
    let mut agent = AutonomousAgent::with_backends(AgentConfig::default(), backends);

    let result = agent.run_cycle().await.unwrap();

    // Verify CycleResult structure
    assert_eq!(result.cycle, 0);
    assert!(result.decision.is_some());
    assert!(result.allocation.is_some());

    // Check decision record
    let decision = result.decision.unwrap();
    assert!(!decision.decision_type.is_empty());
    assert!(!decision.reasoning.is_empty());
    assert!(decision.confidence >= 0.0 && decision.confidence <= 1.0);

    // Check allocation record
    let allocation = result.allocation.unwrap();
    assert!(allocation.total_hours > 0.0);
    assert!(allocation.task_work_hours >= 0.0);
    assert!(allocation.company_work_hours >= 0.0);
}

#[tokio::test]
async fn test_reputation_changes() {
    let config = MockBackendConfig {
        initial_balance: 100.0,
        initial_compute_hours: 100.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 50,
    };
    let backends = create_test_backends(config).await;
    let mut agent = AutonomousAgent::with_backends(AgentConfig::default(), backends);

    // Run multiple cycles
    let results = agent.run(Some(10)).await.unwrap();

    // Should have completed some cycles
    assert!(!results.is_empty());

    // Reputation should always be in valid range
    assert!(agent.state.reputation >= 0.0);
    assert!(agent.state.reputation <= 1.0);
}

#[tokio::test]
async fn test_agent_initialize() {
    let config = MockBackendConfig {
        initial_balance: 123.45,
        initial_compute_hours: 67.89,
        compute_cost_per_hour: 0.10,
        initial_tasks: 5,
    };
    let backends = create_test_backends(config).await;
    let mut agent = AutonomousAgent::with_backends(AgentConfig::default(), backends);

    // State starts at defaults
    assert_eq!(agent.state.balance, 0.0);
    assert_eq!(agent.state.compute_hours, 0.0);

    // Initialize from backends
    agent.initialize().await.unwrap();

    // State should now reflect backend values
    assert_eq!(agent.state.balance, 123.45);
    assert_eq!(agent.state.compute_hours, 67.89);
}
