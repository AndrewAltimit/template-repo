"""Tests for scenario engine."""

import pytest
from economic_agents.scenarios import (
    COMPANY_FORMATION_SCENARIO,
    INVESTMENT_SEEKING_SCENARIO,
    MULTI_DAY_SCENARIO,
    SURVIVAL_MODE_SCENARIO,
    Scenario,
    ScenarioConfig,
    ScenarioEngine,
)


@pytest.fixture
def scenario_engine(tmp_path):
    """Create scenario engine with temp directory."""
    return ScenarioEngine(scenarios_dir=str(tmp_path))


@pytest.fixture
def custom_scenario_config():
    """Create custom scenario configuration."""
    return ScenarioConfig(
        name="test_scenario",
        description="Test scenario",
        duration_minutes=10,
        initial_balance=100.0,
        initial_compute_hours=24.0,
        mode="survival",
        company_building_enabled=False,
        investment_enabled=False,
        expected_outcomes=["Test outcome 1", "Test outcome 2"],
        success_criteria={"minimum_balance": 80.0, "positive_balance": True},
    )


# Scenario Config Tests


def test_scenario_config_creation(custom_scenario_config):
    """Test scenario configuration creation."""
    assert custom_scenario_config.name == "test_scenario"
    assert custom_scenario_config.duration_minutes == 10
    assert custom_scenario_config.initial_balance == 100.0
    assert custom_scenario_config.mode == "survival"


# Scenario Tests


def test_scenario_creation(custom_scenario_config):
    """Test scenario creation from config."""
    scenario = Scenario(custom_scenario_config)

    assert scenario.config == custom_scenario_config
    assert scenario.start_time is None
    assert scenario.end_time is None


def test_scenario_setup(custom_scenario_config):
    """Test scenario environment setup."""
    scenario = Scenario(custom_scenario_config)
    env = scenario.setup()

    assert "agent_id" in env
    assert env["initial_balance"] == 100.0
    assert env["initial_compute_hours"] == 24.0
    assert env["mode"] == "survival"
    assert env["company_building_enabled"] is False


def test_scenario_validate_outcome_success(custom_scenario_config):
    """Test scenario outcome validation - success case."""
    scenario = Scenario(custom_scenario_config)

    agent_data = {"balance": 120.0, "tasks_completed": 5}

    success, achieved, missed = scenario.validate_outcome(agent_data)

    assert success is True
    assert len(achieved) > 0
    assert len(missed) == 0
    assert any("balance" in a.lower() for a in achieved)


def test_scenario_validate_outcome_failure(custom_scenario_config):
    """Test scenario outcome validation - failure case."""
    scenario = Scenario(custom_scenario_config)

    agent_data = {"balance": 50.0, "tasks_completed": 5}  # Below minimum balance

    success, achieved, missed = scenario.validate_outcome(agent_data)

    assert success is False
    assert len(missed) > 0
    assert any("minimum balance" in m.lower() for m in missed)


def test_scenario_validate_company_formation():
    """Test scenario validation for company formation."""
    config = ScenarioConfig(
        name="test",
        description="Test",
        duration_minutes=10,
        initial_balance=100.0,
        initial_compute_hours=24.0,
        mode="entrepreneur",
        company_building_enabled=True,
        investment_enabled=False,
        success_criteria={"company_formed": True},
    )

    scenario = Scenario(config)

    # Test success
    agent_data = {"company_exists": True, "balance": 100.0}
    success, achieved, missed = scenario.validate_outcome(agent_data)
    assert success is True
    assert any("formed company" in a.lower() for a in achieved)

    # Test failure
    agent_data = {"company_exists": False, "balance": 100.0}
    success, achieved, missed = scenario.validate_outcome(agent_data)
    assert success is False
    assert any("failed to form company" in m.lower() for m in missed)


# Scenario Engine Tests


def test_scenario_engine_initialization(scenario_engine):
    """Test scenario engine initialization."""
    assert scenario_engine.scenarios_dir.exists()
    assert len(scenario_engine.scenarios) == 4  # 4 predefined scenarios


def test_scenario_engine_list_scenarios(scenario_engine):
    """Test listing available scenarios."""
    scenarios = scenario_engine.list_scenarios()

    assert "survival" in scenarios
    assert "company_formation" in scenarios
    assert "investment_seeking" in scenarios
    assert "multi_day" in scenarios


def test_scenario_engine_load_scenario(scenario_engine):
    """Test loading a predefined scenario."""
    scenario = scenario_engine.load_scenario("survival")

    assert isinstance(scenario, Scenario)
    assert scenario.config.name == "survival"
    assert scenario.config.initial_balance == 50.0


def test_scenario_engine_load_invalid_scenario(scenario_engine):
    """Test loading non-existent scenario raises error."""
    with pytest.raises(ValueError) as exc_info:
        scenario_engine.load_scenario("nonexistent")

    assert "not found" in str(exc_info.value)


def test_scenario_engine_register_custom_scenario(scenario_engine, custom_scenario_config):
    """Test registering a custom scenario."""
    scenario_engine.register_scenario(custom_scenario_config)

    assert "test_scenario" in scenario_engine.scenarios
    scenario = scenario_engine.load_scenario("test_scenario")
    assert scenario.config.name == "test_scenario"


def test_scenario_engine_get_scenario_config(scenario_engine):
    """Test getting scenario configuration."""
    config = scenario_engine.get_scenario_config("survival")

    assert isinstance(config, ScenarioConfig)
    assert config.name == "survival"
    assert config.duration_minutes == 15


def test_scenario_engine_get_invalid_config(scenario_engine):
    """Test getting config for non-existent scenario."""
    with pytest.raises(ValueError):
        scenario_engine.get_scenario_config("nonexistent")


def test_scenario_engine_run_scenario(scenario_engine):
    """Test running a scenario."""
    result = scenario_engine.run_scenario("survival")

    assert result.scenario_name == "survival"
    assert result.duration_minutes >= 0
    assert result.success in [True, False]
    assert "final_balance" in result.metrics
    assert "tasks_completed" in result.metrics


def test_scenario_engine_run_with_custom_runner(scenario_engine):
    """Test running scenario with custom runner function."""

    def custom_runner(env_config, scenario_config):
        """Custom runner that returns specific outcomes."""
        return {
            "agent_id": env_config["agent_id"],
            "balance": 120.0,  # Above minimum
            "tasks_completed": 5,
            "tasks_failed": 0,
            "success_rate": 100.0,
            "total_earnings": 70.0,
            "total_expenses": 0.0,
            "net_profit": 70.0,
            "company_exists": False,
            "decisions": [],
            "transactions": [],
            "sub_agents": [],
        }

    result = scenario_engine.run_scenario("survival", agent_runner_func=custom_runner)

    assert result.success is True
    assert result.metrics["final_balance"] == 120.0


# Predefined Scenarios Tests


def test_survival_mode_scenario():
    """Test survival mode scenario configuration."""
    assert SURVIVAL_MODE_SCENARIO.name == "survival"
    assert SURVIVAL_MODE_SCENARIO.duration_minutes == 15
    assert SURVIVAL_MODE_SCENARIO.initial_balance == 50.0
    assert SURVIVAL_MODE_SCENARIO.company_building_enabled is False


def test_company_formation_scenario():
    """Test company formation scenario configuration."""
    assert COMPANY_FORMATION_SCENARIO.name == "company_formation"
    assert COMPANY_FORMATION_SCENARIO.duration_minutes == 45
    assert COMPANY_FORMATION_SCENARIO.initial_balance == 150.0
    assert COMPANY_FORMATION_SCENARIO.company_building_enabled is True


def test_investment_seeking_scenario():
    """Test investment seeking scenario configuration."""
    assert INVESTMENT_SEEKING_SCENARIO.name == "investment_seeking"
    assert INVESTMENT_SEEKING_SCENARIO.duration_minutes == 120
    assert INVESTMENT_SEEKING_SCENARIO.investment_enabled is True


def test_multi_day_scenario():
    """Test multi-day scenario configuration."""
    assert MULTI_DAY_SCENARIO.name == "multi_day"
    assert MULTI_DAY_SCENARIO.duration_minutes == 4320  # 3 days
    assert MULTI_DAY_SCENARIO.initial_compute_hours == 168.0  # 7 days


# Scenario Result Tests


def test_scenario_result_to_dict(scenario_engine):
    """Test converting scenario result to dictionary."""
    result = scenario_engine.run_scenario("survival")
    result_dict = result.to_dict()

    assert "scenario_name" in result_dict
    assert "start_time" in result_dict
    assert "end_time" in result_dict
    assert "success" in result_dict
    assert "metrics" in result_dict
    assert result_dict["scenario_name"] == "survival"


def test_scenario_result_saved_to_file(scenario_engine):
    """Test that scenario results are saved to file."""
    _ = scenario_engine.run_scenario("survival")

    # Check that file was created
    files = list(scenario_engine.scenarios_dir.glob("*.json"))
    assert len(files) >= 1

    # Verify filename format
    saved_file = files[0]
    assert "survival" in saved_file.name
    assert ".json" in saved_file.name


# Integration Tests


def test_full_scenario_workflow(scenario_engine, custom_scenario_config):
    """Test complete workflow: register, load, run, validate."""
    # Register custom scenario
    scenario_engine.register_scenario(custom_scenario_config)

    # Load scenario
    scenario = scenario_engine.load_scenario("test_scenario")
    assert scenario.config.name == "test_scenario"

    # Run scenario
    result = scenario_engine.run_scenario("test_scenario")

    # Validate result
    assert result.scenario_name == "test_scenario"
    assert "final_balance" in result.metrics
    assert result.duration_minutes >= 0


def test_all_predefined_scenarios_loadable(scenario_engine):
    """Test that all predefined scenarios can be loaded."""
    for scenario_name in ["survival", "company_formation", "investment_seeking", "multi_day"]:
        scenario = scenario_engine.load_scenario(scenario_name)
        assert scenario.config.name == scenario_name
