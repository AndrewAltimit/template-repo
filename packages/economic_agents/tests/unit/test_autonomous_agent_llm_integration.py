"""Tests for AutonomousAgent LLM decision engine integration."""

from unittest.mock import MagicMock, patch

import pytest
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.agent.core.decision_engine import DecisionEngine, ResourceAllocation
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

        # Verify LLMDecisionEngine was created with config
        mock_llm_class.assert_called_once_with(config)
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
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=100.0)
        marketplace = MockMarketplace()

        config = {"engine_type": "invalid_type"}

        with pytest.raises(ValueError) as exc_info:
            AutonomousAgent(wallet, compute, marketplace, config)

        assert "Invalid engine_type" in str(exc_info.value)
        assert "invalid_type" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("economic_agents.agent.core.autonomous_agent.LLM_AVAILABLE", True)
    @patch("economic_agents.agent.core.autonomous_agent.LLMDecisionEngine")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_time_allocation")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_transaction")
    @patch("economic_agents.monitoring.resource_tracker.ResourceTracker._save_compute_usage")
    @patch("economic_agents.monitoring.metrics_collector.MetricsCollector._save_performance_snapshot")
    async def test_llm_engine_used_in_run_cycle(
        self, mock_save_perf, mock_save_compute, mock_save_transaction, mock_save_time, mock_llm_class
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

        # Verify full config was passed to LLMDecisionEngine
        mock_llm_class.assert_called_once_with(config)


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
        self, mock_save_perf, mock_save_compute, mock_save_transaction, mock_save_time
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
        mock_llm_class.assert_called_once_with(config)

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
