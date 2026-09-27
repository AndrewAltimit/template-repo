//! Integration tests for the economic-agents-core crate.
//!
//! These tests verify the agent's behavior with mock backends.

use std::sync::Arc;

use chrono::Utc;
use economic_agents_core::{
    AgentConfig, AutonomousAgent, Backends, EngineType, OperatingMode, Personality,
    TaskSelectionStrategy,
};
use economic_agents_interfaces::{Task, TaskCategory, TaskStatus};
use economic_agents_mock::{MockBackendConfig, MockBackendFactory};
use uuid::Uuid;

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
        assert!(
            result.decision.is_some(),
            "Each cycle should have a decision"
        );
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

    // With balance well above the threshold and compute above the survival
    // buffer, the rule-based engine deterministically chooses WorkOnCompany
    // on the first cycle, so exactly one successful formation must occur.
    let formations: Vec<_> = results
        .iter()
        .filter_map(|r| r.company_formation.as_ref())
        .collect();
    assert_eq!(
        formations.len(),
        1,
        "company should be formed exactly once, got {formations:?}"
    );
    let formation = formations[0];
    assert!(
        formation.success,
        "formation failed: {:?}",
        formation.failure_reason
    );
    assert!(
        results[0].company_formation.is_some(),
        "formation should happen on the first cycle"
    );

    assert!(agent.state.has_company);
    assert_eq!(agent.state.company_id, formation.company_id);
    assert!(formation.initial_capital > 0.0);
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

    // The rule-based engine maps personality to decision confidence
    // (risk-averse is more certain, aggressive less). Every recorded
    // decision must reflect the agent's own personality, and the two
    // personalities must produce different decisions on every cycle.
    for (ra, ag) in risk_averse_results.iter().zip(&aggressive_results) {
        let ra_decision = ra
            .decision
            .as_ref()
            .expect("cycle should record a decision");
        let ag_decision = ag
            .decision
            .as_ref()
            .expect("cycle should record a decision");
        assert!((ra_decision.confidence - 0.9).abs() < f64::EPSILON);
        assert!((ag_decision.confidence - 0.6).abs() < f64::EPSILON);
        assert!(ra_decision.confidence > ag_decision.confidence);
    }
}

#[tokio::test]
async fn test_agent_state_updates() {
    // A single known task (and no random ones) makes the cycle deterministic:
    // compute is above the survival buffer and balance is below the company
    // threshold, so the rule-based engine must choose WorkOnTasks and pick
    // this task.
    let mock = MockBackendFactory::create_with_config(MockBackendConfig {
        initial_balance: 100.0,
        initial_compute_hours: 48.0,
        compute_cost_per_hour: 0.10,
        initial_tasks: 0,
    })
    .await;
    let task_id = Uuid::new_v4();
    mock.marketplace
        .add_task(Task {
            id: task_id,
            title: "Known task".to_string(),
            description: "Deterministic test task".to_string(),
            category: TaskCategory::Coding,
            reward: 50.0,
            estimated_hours: 2.0,
            difficulty: 0.1,
            required_skills: Vec::new(),
            deadline: None,
            status: TaskStatus::Available,
            posted_by: "test".to_string(),
            posted_at: Utc::now(),
            claimed_by: None,
            claimed_at: None,
        })
        .await;
    let backends = Backends::new(
        Arc::new(mock.wallet),
        Arc::new(mock.marketplace),
        Arc::new(mock.compute),
    );
    let agent_config = AgentConfig {
        survival_buffer_hours: 8.0,
        company_threshold: 1_000.0,
        ..Default::default()
    };
    let mut agent = AutonomousAgent::with_backends(agent_config, backends);

    agent.initialize().await.unwrap();
    let initial_balance = agent.state.balance;
    let initial_compute = agent.state.compute_hours;

    let result = agent.run_cycle().await.unwrap();

    // The result snapshots the state before and after the cycle.
    assert_eq!(result.initial_state.balance, initial_balance);
    assert_eq!(result.initial_state.compute_hours, initial_compute);
    assert_eq!(result.final_state.balance, agent.state.balance);
    assert_eq!(result.final_state.compute_hours, agent.state.compute_hours);

    let task_result = result
        .task_result
        .expect("agent should have done task work");
    assert!(task_result.success, "{:?}", task_result.failure_reason);
    assert_eq!(task_result.task_id, Some(task_id));
    assert_eq!(task_result.hours_spent, 2.0);

    // Compute is consumed and the (simulated) reward is paid out.
    assert!((initial_compute - agent.state.compute_hours - 2.0).abs() < 1e-9);
    let reward = task_result
        .reward_earned
        .expect("approved task pays a reward");
    assert!(
        (35.0..=50.0).contains(&reward),
        "reward {reward} out of range"
    );
    assert!((agent.state.balance - initial_balance - reward).abs() < 1e-9);
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
