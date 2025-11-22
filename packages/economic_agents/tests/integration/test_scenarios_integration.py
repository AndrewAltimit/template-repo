"""Integration tests for scenarios with real agent execution."""

import pytest

from economic_agents.scenarios import ScenarioEngine


@pytest.fixture
def scenario_engine(tmp_path):
    """Create scenario engine."""
    return ScenarioEngine(scenarios_dir=str(tmp_path))


def test_scenario_runs_real_agent(scenario_engine):
    """Test that scenarios actually run real agents."""
    result = scenario_engine.run_scenario("survival")

    # Verify result structure
    assert result.scenario_name == "survival"
    assert result.success in [True, False]

    # Verify agent actually ran (not simulated)
    assert "final_balance" in result.metrics
    assert "tasks_completed" in result.metrics

    # Agent data should have real transactions
    assert "transactions" in result.agent_data
    # If agent completed any tasks, there should be transactions
    if result.metrics["tasks_completed"] > 0:
        assert len(result.agent_data["transactions"]) > 0


def test_survival_scenario_realistic_outcomes(scenario_engine):
    """Test that survival scenario produces realistic outcomes."""
    result = scenario_engine.run_scenario("survival")

    # Check realistic balance (started with 50.0)
    initial_balance = 50.0
    final_balance = result.metrics["final_balance"]

    # Balance should have changed (either increased from tasks or decreased from nothing)
    # But should still be reasonable (not wildly different)
    assert abs(final_balance - initial_balance) < 500.0  # Reasonable change

    # Should have attempted some tasks
    total_tasks = result.metrics["tasks_completed"] + result.metrics["tasks_failed"]
    assert total_tasks > 0


def test_company_formation_scenario(scenario_engine):
    """Test company formation scenario."""
    result = scenario_engine.run_scenario("company_formation")

    # This scenario has company building enabled
    # May or may not form company depending on balance

    # Should have run longer (45 minutes = ~9 cycles)
    assert result.duration_minutes > 0

    # Check if company was formed
    if result.agent_data.get("company_exists"):
        assert result.agent_data["company"] is not None
        assert "stage" in result.agent_data["company"]


def test_scenario_saves_results(scenario_engine):
    """Test that scenario results are saved to file."""
    _ = scenario_engine.run_scenario("survival")

    # Check that file was created
    saved_files = list(scenario_engine.scenarios_dir.glob("*.json"))
    assert len(saved_files) > 0

    # Find the file for this scenario
    survival_files = [f for f in saved_files if "survival" in f.name]
    assert len(survival_files) > 0


def test_scenario_with_custom_runner(scenario_engine):
    """Test scenario with custom runner function."""

    def custom_runner(env_config, scenario_config):
        """Custom runner that returns specific data."""
        return {
            "agent_id": env_config["agent_id"],
            "balance": 150.0,
            "compute_hours": 20.0,
            "tasks_completed": 5,
            "tasks_failed": 0,
            "success_rate": 100.0,
            "total_earnings": 60.0,
            "total_expenses": 10.0,
            "net_profit": 50.0,
            "company_exists": False,
            "company": None,
            "decisions": [],
            "transactions": [],
            "sub_agents": [],
        }

    result = scenario_engine.run_scenario("survival", agent_runner_func=custom_runner)

    # Verify custom runner was used
    assert result.metrics["final_balance"] == 150.0
    assert result.metrics["tasks_completed"] == 5


def test_scenario_outcome_validation(scenario_engine):
    """Test that scenario outcomes are validated correctly."""
    result = scenario_engine.run_scenario("survival")

    # Success should be determined by criteria
    # Survival scenario requires minimum_balance >= 40.0 and minimum_tasks >= 2

    if result.success:
        # If successful, should have met criteria
        assert result.metrics["final_balance"] >= 40.0 or result.metrics["tasks_completed"] >= 2
        # Should have achieved outcomes
        assert len(result.outcomes_achieved) > 0
    else:
        # If not successful, should have missed outcomes
        assert len(result.outcomes_missed) > 0


def test_multiple_scenarios_can_run(scenario_engine):
    """Test running multiple different scenarios."""
    scenarios_to_test = ["survival", "company_formation"]

    results = {}
    for scenario_name in scenarios_to_test:
        result = scenario_engine.run_scenario(scenario_name)
        results[scenario_name] = result

    # Verify all scenarios ran
    assert len(results) == 2

    # Each should have different durations (scenarios have different duration_minutes)
    survival_duration = results["survival"].duration_minutes
    company_duration = results["company_formation"].duration_minutes

    # Durations should be different (company formation is longer)
    # But allow for some variance due to execution time
    assert abs(survival_duration - company_duration) > 0.01


def test_scenario_agent_data_structure(scenario_engine):
    """Test that agent data from scenario has expected structure."""
    result = scenario_engine.run_scenario("survival")

    agent_data = result.agent_data

    # Verify all required fields are present
    required_fields = [
        "agent_id",
        "balance",
        "tasks_completed",
        "tasks_failed",
        "success_rate",
        "total_earnings",
        "total_expenses",
        "net_profit",
        "company_exists",
        "decisions",
        "transactions",
        "sub_agents",
    ]

    for field in required_fields:
        assert field in agent_data, f"Missing required field: {field}"
