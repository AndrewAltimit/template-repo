"""Tests for AutonomousAgent LLM decision engine integration and initialization."""

from unittest.mock import MagicMock, patch

import pytest

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.agent.core.decision_engine import DecisionEngine, ResourceAllocation
from economic_agents.exceptions import AgentNotInitializedError
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet


class TestAutonomousAgentEngineSelection:
    """Tests for decision engine selection in AutonomousAgent."""

    def test_default_engine_is_rule_based(self):
        """Test that default engine is rule-based DecisionEngine."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        agent = AutonomousAgent(wallet, compute, marketplace)

        assert isinstance(agent.decision_engine, DecisionEngine)
        assert agent.config.get("engine_type", "rule_based") == "rule_based"

    def test_explicit_rule_based_engine(self):
        """Test explicit rule_based engine configuration."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        config = {"engine_type": "rule_based"}
        agent = AutonomousAgent(wallet, compute, marketplace, config)

        assert isinstance(agent.decision_engine, DecisionEngine)

    @patch("economic_agents.agent.core.autonomous_agent.LLM_AVAILABLE", True)
    @patch("economic_agents.agent.core.autonomous_agent.LLMDecisionEngine")
    def test_llm_engine_configuration(self, mock_llm_class):
        """Test LLM engine configuration when available."""
        mock_llm_instance = MagicMock()
        mock_llm_class.return_value = mock_llm_instance

        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        config = {
            "engine_type": "llm",
            "llm_timeout": 900,
            "fallback_enabled": True,
        }
        agent = AutonomousAgent(wallet, compute, marketplace, config)

        # Verify LLMDecisionEngine was created with config containing expected values
        mock_llm_class.assert_called_once()
        actual_config = mock_llm_class.call_args[0][0]
        assert actual_config["engine_type"] == "llm"
        assert actual_config["llm_timeout"] == 900
        assert actual_config["fallback_enabled"] is True
        assert agent.decision_engine == mock_llm_instance

    @patch("economic_agents.agent.core.autonomous_agent.LLM_AVAILABLE", False)
    def test_llm_engine_not_available_raises_error(self):
        """Test that ValueError is raised when LLM engine requested but not available."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        config = {"engine_type": "llm"}

        with pytest.raises(ValueError) as exc_info:
            AutonomousAgent(wallet, compute, marketplace, config)

        assert "LLM decision engine not available" in str(exc_info.value)

    def test_invalid_engine_type_raises_error(self):
        """Test that ValueError is raised for invalid engine type."""
        from pydantic import ValidationError

        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        config = {"engine_type": "invalid_type"}

        # Pydantic ValidationError is raised during AgentConfig validation
        with pytest.raises(ValidationError) as exc_info:
            AutonomousAgent(wallet, compute, marketplace, config)

        # Pydantic's error message includes the field and invalid value
        error_str = str(exc_info.value)
        assert "engine_type" in error_str
        assert "invalid_type" in error_str

    @pytest.mark.asyncio
    @patch("economic_agents.agent.core.autonomous_agent.LLM_AVAILABLE", True)
    @patch("economic_agents.agent.core.autonomous_agent.LLMDecisionEngine")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_time_allocation")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_transaction")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_compute_usage")
    @patch("economic_agents.monitoring.metrics_collector.MetricsCollector._save_performance_snapshot")
    async def test_llm_engine_used_in_run_cycle(
        self, _mock_save_perf, _mock_save_compute, _mock_save_transaction, _mock_save_time, mock_llm_class
    ):
        """Test that LLM engine is actually used during agent run cycle."""
        # Setup mock LLM engine
        mock_llm_engine = MagicMock()
        mock_llm_engine.decide_allocation.return_value = ResourceAllocation(
            task_work_hours=1.0,
            company_work_hours=0.0,
            reasoning="LLM decision for testing",
            confidence=0.9,
        )
        mock_llm_engine.should_form_company.return_value = False
        mock_llm_class.return_value = mock_llm_engine

        # Create agent with LLM engine
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()  # Auto-generates tasks

        config = {"engine_type": "llm"}
        agent = AutonomousAgent(wallet, compute, marketplace, config)
        await agent.initialize()

        # Run one cycle
        result = await agent.run_cycle()

        # Verify LLM engine was called
        mock_llm_engine.decide_allocation.assert_called_once()
        mock_llm_engine.should_form_company.assert_called_once()

        # Verify decision was logged with LLM reasoning
        assert result["allocation"]["reasoning"] == "LLM decision for testing"
        assert result["allocation"]["confidence"] == 0.9

    def test_config_parameters_passed_to_engine(self):
        """Test that configuration parameters are passed to decision engine."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        config = {
            "engine_type": "rule_based",
            "survival_buffer_hours": 48.0,
            "company_threshold": 200.0,
        }
        agent = AutonomousAgent(wallet, compute, marketplace, config)

        # Verify config was passed to DecisionEngine
        assert agent.decision_engine.survival_buffer == 48.0
        assert agent.decision_engine.company_threshold == 200.0

    @patch("economic_agents.agent.core.autonomous_agent.LLM_AVAILABLE", True)
    @patch("economic_agents.agent.core.autonomous_agent.LLMDecisionEngine")
    def test_llm_config_parameters(self, mock_llm_class):
        """Test that LLM-specific config parameters are passed."""
        mock_llm_instance = MagicMock()
        mock_llm_class.return_value = mock_llm_instance

        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        config = {
            "engine_type": "llm",
            "llm_timeout": 600,  # 10 minutes
            "node_version": "20.0.0",
            "fallback_enabled": False,
        }
        AutonomousAgent(wallet, compute, marketplace, config)

        # Verify LLM-specific config was passed (config is now full AgentConfig dict)
        mock_llm_class.assert_called_once()
        actual_config = mock_llm_class.call_args[0][0]
        assert actual_config["engine_type"] == "llm"
        assert actual_config["llm_timeout"] == 600
        assert actual_config["node_version"] == "20.0.0"
        assert actual_config["fallback_enabled"] is False


class TestAutonomousAgentBackwardCompatibility:
    """Tests for backward compatibility with existing code."""

    def test_agents_without_engine_config_still_work(self):
        """Test that agents created without engine config use rule-based by default."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        # No config at all
        agent = AutonomousAgent(wallet, compute, marketplace)

        assert isinstance(agent.decision_engine, DecisionEngine)

    @pytest.mark.asyncio
    async def test_existing_config_without_engine_type_works(self):
        """Test that existing configs without engine_type still work."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        # Config with other parameters but no engine_type
        config = {
            "survival_buffer_hours": 20.0,
            "company_threshold": 150.0,
            "mode": "company",
        }
        agent = AutonomousAgent(wallet, compute, marketplace, config)
        await agent.initialize()

        assert isinstance(agent.decision_engine, DecisionEngine)
        assert agent.state.mode == "company"

    @pytest.mark.asyncio
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_time_allocation")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_transaction")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_compute_usage")
    @patch("economic_agents.monitoring.metrics_collector.MetricsCollector._save_performance_snapshot")
    async def test_rule_based_behavior_unchanged(
        self, _mock_save_perf, _mock_save_compute, _mock_save_transaction, _mock_save_time
    ):
        """Test that rule-based engine behavior is unchanged."""
        wallet = MockWallet(initial_balance=50.0)
        compute = MockCompute(initial_hours=20.0)  # Below survival buffer
        marketplace = MockMarketplace()  # Auto-generates tasks

        config = {
            "engine_type": "rule_based",
            "survival_buffer_hours": 24.0,
        }
        agent = AutonomousAgent(wallet, compute, marketplace, config)
        await agent.initialize()

        # Run cycle
        result = await agent.run_cycle()

        # Should prioritize task work (survival at risk)
        assert result["allocation"]["task_work_hours"] > 0
        assert result["allocation"]["company_work_hours"] == 0
        assert "survival" in result["allocation"]["reasoning"].lower()


class TestDocumentationExamples:
    """Tests based on documentation examples."""

    @patch("economic_agents.agent.core.autonomous_agent.LLM_AVAILABLE", True)
    @patch("economic_agents.agent.core.autonomous_agent.LLMDecisionEngine")
    def test_example_llm_agent_creation(self, mock_llm_class):
        """Test example from documentation for creating LLM agent."""
        mock_llm_instance = MagicMock()
        mock_llm_class.return_value = mock_llm_instance

        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        # Example from docs
        config = {
            "engine_type": "llm",
            "llm_timeout": 900,  # 15 minutes
            "fallback_enabled": True,
            "survival_buffer_hours": 24.0,
            "company_threshold": 100.0,
        }

        agent = AutonomousAgent(wallet, compute, marketplace, config)

        assert agent.config["engine_type"] == "llm"
        assert agent.config["llm_timeout"] == 900
        # Config is now full AgentConfig dict with all defaults filled in
        mock_llm_class.assert_called_once()
        actual_config = mock_llm_class.call_args[0][0]
        assert actual_config["engine_type"] == "llm"
        assert actual_config["llm_timeout"] == 900
        assert actual_config["fallback_enabled"] is True
        assert actual_config["survival_buffer_hours"] == 24.0
        assert actual_config["company_threshold"] == 100.0

    @pytest.mark.asyncio
    async def test_example_rule_based_agent_creation(self):
        """Test example from documentation for creating rule-based agent."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        # Example from docs (default behavior)
        config = {
            "survival_buffer_hours": 24.0,
            "company_threshold": 100.0,
        }

        agent = AutonomousAgent(wallet, compute, marketplace, config)
        await agent.initialize()

        assert isinstance(agent.decision_engine, DecisionEngine)
        assert agent.state.survival_buffer_hours == 24.0


class TestAutonomousAgentInitialization:
    """Tests for AutonomousAgent initialization patterns.

    These tests ensure the factory method pattern works correctly and that
    proper errors are raised when using uninitialized agents.
    """

    @pytest.mark.asyncio
    async def test_factory_method_returns_initialized_agent(self):
        """Test that create() factory method returns a fully initialized agent."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=50.0)
        marketplace = MockMarketplace()

        agent = await AutonomousAgent.create(wallet, compute, marketplace)

        # Agent should be fully initialized
        assert agent.state is not None
        assert agent.state.balance == 100.0
        # Use approximate comparison for compute hours (MockCompute uses time-based calculations)
        assert agent.state.compute_hours_remaining == pytest.approx(50.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_factory_method_with_config(self):
        """Test that create() factory method accepts configuration."""
        wallet = MockWallet(initial_balance=200.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        config = {
            "survival_buffer_hours": 48.0,
            "company_threshold": 500.0,
            "mode": "company",
        }

        agent = await AutonomousAgent.create(wallet, compute, marketplace, config)

        assert agent.state is not None
        assert agent.state.survival_buffer_hours == 48.0
        assert agent.state.mode == "company"

    def test_uninitialized_agent_has_none_state(self):
        """Test that agent created with constructor has None state."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        agent = AutonomousAgent(wallet, compute, marketplace)

        assert agent.state is None

    @pytest.mark.asyncio
    async def test_run_cycle_raises_error_without_initialization(self):
        """Test that run_cycle raises AgentNotInitializedError without initialization."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        agent = AutonomousAgent(wallet, compute, marketplace)

        with pytest.raises(AgentNotInitializedError) as exc_info:
            await agent.run_cycle()

        assert "run_cycle" in str(exc_info.value)
        assert "initialize()" in str(exc_info.value) or "create()" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_raises_error_without_initialization(self):
        """Test that run raises AgentNotInitializedError without initialization."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        agent = AutonomousAgent(wallet, compute, marketplace)

        with pytest.raises(AgentNotInitializedError) as exc_info:
            await agent.run(max_cycles=1)

        assert "run" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_manual_initialization_works(self):
        """Test that manual initialize() call works correctly."""
        wallet = MockWallet(initial_balance=150.0)
        compute = MockCompute(initial_hours=75.0)
        marketplace = MockMarketplace()

        agent = AutonomousAgent(wallet, compute, marketplace)

        # State should be None before initialization
        assert agent.state is None

        # Initialize manually
        await agent.initialize()

        # State should now be populated
        assert agent.state is not None
        assert agent.state.balance == 150.0
        # Use approximate comparison for compute hours (MockCompute uses time-based calculations)
        assert agent.state.compute_hours_remaining == pytest.approx(75.0, abs=0.01)

    @pytest.mark.asyncio
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_time_allocation")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_transaction")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_compute_usage")
    @patch("economic_agents.monitoring.metrics_collector.MetricsCollector._save_performance_snapshot")
    async def test_initialized_agent_can_run_cycle(
        self, _mock_save_perf, _mock_save_compute, _mock_save_transaction, _mock_save_time
    ):
        """Test that properly initialized agent can run cycles."""
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        # Use factory method for proper initialization
        agent = await AutonomousAgent.create(wallet, compute, marketplace)

        # Should not raise any errors
        result = await agent.run_cycle()

        assert result is not None
        assert "allocation" in result
        assert agent.state.cycles_completed == 1
