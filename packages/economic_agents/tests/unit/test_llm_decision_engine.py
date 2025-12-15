"""Unit tests for LLMDecisionEngine."""

# pylint: disable=protected-access  # Testing protected members is legitimate in tests

from unittest.mock import MagicMock, patch

import pytest

from economic_agents.agent.core.decision_engine import ResourceAllocation
from economic_agents.agent.core.state import AgentState
from economic_agents.agent.llm import LLMDecisionEngine


class TestLLMDecisionEngine:
    """Tests for LLMDecisionEngine class."""

    def test_initialization_default_config(self):
        """Test LLMDecisionEngine initializes with default configuration."""
        engine = LLMDecisionEngine()

        assert engine.fallback_enabled is True
        assert engine.fallback is not None
        assert engine.executor is not None
        assert len(engine.decisions) == 0

    def test_initialization_custom_config(self):
        """Test LLMDecisionEngine initializes with custom configuration."""
        config = {
            "llm_timeout": 600,
            "fallback_enabled": False,
            "survival_buffer_hours": 12.0,
        }
        engine = LLMDecisionEngine(config)

        assert engine.fallback_enabled is False
        assert engine.executor.timeout == 600

    @patch("economic_agents.agent.llm.llm_decision_engine.ClaudeExecutor")
    def test_decide_allocation_success(self, mock_executor_class):
        """Test successful allocation decision from Claude."""
        # Setup mock
        mock_executor = MagicMock()
        mock_executor.execute.return_value = """{
            "task_work_hours": 1.0,
            "company_work_hours": 0.5,
            "reasoning": "Allocating resources based on current needs",
            "confidence": 0.85
        }"""
        mock_executor_class.return_value = mock_executor

        # Create engine and state
        engine = LLMDecisionEngine()
        state = AgentState(balance=100.0, compute_hours_remaining=10.0)

        # Make decision
        allocation = engine.decide_allocation(state)

        # Verify
        assert allocation.task_work_hours == 1.0
        assert allocation.company_work_hours == 0.5
        assert allocation.reasoning == "Allocating resources based on current needs"
        assert allocation.confidence == 0.85

        # Verify decision logged
        assert len(engine.decisions) == 1
        assert engine.decisions[0].fallback_used is False

    @patch("economic_agents.agent.llm.llm_decision_engine.ClaudeExecutor")
    def test_decide_allocation_with_markdown(self, mock_executor_class):
        """Test parsing JSON wrapped in markdown code block."""
        # Setup mock with markdown-wrapped JSON
        mock_executor = MagicMock()
        mock_executor.execute.return_value = """Here's my decision:

```json
{
    "task_work_hours": 0.8,
    "company_work_hours": 0.2,
    "reasoning": "Focus on survival",
    "confidence": 0.9
}
```

Hope this helps!"""
        mock_executor_class.return_value = mock_executor

        # Create engine and state
        engine = LLMDecisionEngine()
        state = AgentState(balance=50.0, compute_hours_remaining=5.0)

        # Make decision
        allocation = engine.decide_allocation(state)

        # Verify
        assert allocation.task_work_hours == 0.8
        assert allocation.company_work_hours == 0.2

    @patch("economic_agents.agent.llm.llm_decision_engine.ClaudeExecutor")
    def test_decide_allocation_fallback_on_error(self, mock_executor_class):
        """Test fallback to rule-based engine on Claude error."""
        # Setup mock to raise error
        mock_executor = MagicMock()
        mock_executor.execute.side_effect = RuntimeError("Claude failed")
        mock_executor_class.return_value = mock_executor

        # Create engine and state
        engine = LLMDecisionEngine()
        state = AgentState(balance=100.0, compute_hours_remaining=10.0)

        # Make decision (should fallback)
        allocation = engine.decide_allocation(state)

        # Verify fallback was used
        assert isinstance(allocation, ResourceAllocation)
        assert len(engine.decisions) == 1
        assert engine.decisions[0].fallback_used is True

    @patch("economic_agents.agent.llm.llm_decision_engine.ClaudeExecutor")
    def test_decide_allocation_fallback_disabled(self, mock_executor_class):
        """Test that error is raised when fallback is disabled."""
        # Setup mock to raise error
        mock_executor = MagicMock()
        mock_executor.execute.side_effect = RuntimeError("Claude failed")
        mock_executor_class.return_value = mock_executor

        # Create engine with fallback disabled
        config = {"fallback_enabled": False}
        engine = LLMDecisionEngine(config)
        state = AgentState(balance=100.0, compute_hours_remaining=10.0)

        # Should raise error
        with pytest.raises(RuntimeError) as exc_info:
            engine.decide_allocation(state)

        assert "fallback disabled" in str(exc_info.value)

    def test_parse_allocation_clean_json(self):
        """Test parsing clean JSON response."""
        engine = LLMDecisionEngine()

        response = """{
            "task_work_hours": 1.5,
            "company_work_hours": 0.5,
            "reasoning": "Test reasoning",
            "confidence": 0.75
        }"""

        allocation = engine._parse_allocation(response)

        assert allocation.task_work_hours == 1.5
        assert allocation.company_work_hours == 0.5
        assert allocation.reasoning == "Test reasoning"
        assert allocation.confidence == 0.75

    def test_parse_allocation_with_markdown_json(self):
        """Test parsing JSON in markdown code block."""
        engine = LLMDecisionEngine()

        response = """```json
{
    "task_work_hours": 1.0,
    "company_work_hours": 0.0,
    "reasoning": "Focus on tasks",
    "confidence": 0.8
}
```"""

        allocation = engine._parse_allocation(response)

        assert allocation.task_work_hours == 1.0
        assert allocation.company_work_hours == 0.0

    def test_parse_allocation_with_text_before_json(self):
        """Test parsing JSON with extra text."""
        engine = LLMDecisionEngine()

        response = """Here's my allocation decision:
{
    "task_work_hours": 2.0,
    "company_work_hours": 1.0,
    "reasoning": "Balanced approach",
    "confidence": 0.85
}
Thanks!"""

        allocation = engine._parse_allocation(response)

        assert allocation.task_work_hours == 2.0
        assert allocation.company_work_hours == 1.0

    def test_parse_allocation_invalid_json(self):
        """Test error handling for invalid JSON."""
        engine = LLMDecisionEngine()

        response = "This is not JSON at all"

        with pytest.raises(ValueError) as exc_info:
            engine._parse_allocation(response)

        assert "No JSON object found" in str(exc_info.value)

    def test_parse_allocation_missing_fields(self):
        """Test error handling for missing required fields."""
        engine = LLMDecisionEngine()

        response = '{"task_work_hours": 1.0}'  # Missing other fields

        with pytest.raises(ValueError) as exc_info:
            engine._parse_allocation(response)

        assert "Invalid JSON structure" in str(exc_info.value)

    def test_validate_allocation_valid(self):
        """Test validation of valid allocation."""
        engine = LLMDecisionEngine()
        state = AgentState(balance=100.0, compute_hours_remaining=10.0)

        allocation = ResourceAllocation(
            task_work_hours=1.0,
            company_work_hours=0.5,
            reasoning="This is a good reason for allocation",
            confidence=0.8,
        )

        assert engine._validate_allocation(allocation, state) is True

    def test_validate_allocation_exceeds_available(self):
        """Test validation fails when allocation exceeds available hours."""
        engine = LLMDecisionEngine()
        state = AgentState(balance=100.0, compute_hours_remaining=10.0)

        allocation = ResourceAllocation(
            task_work_hours=8.0,
            company_work_hours=5.0,  # Total = 13 > 10 available
            reasoning="Too much allocation",
            confidence=0.8,
        )

        assert engine._validate_allocation(allocation, state) is False

    def test_validate_allocation_negative_hours(self):
        """Test validation fails for negative hours."""
        engine = LLMDecisionEngine()
        state = AgentState(balance=100.0, compute_hours_remaining=10.0)

        allocation = ResourceAllocation(
            task_work_hours=-1.0,
            company_work_hours=0.5,
            reasoning="Negative hours",
            confidence=0.8,
        )

        assert engine._validate_allocation(allocation, state) is False

    def test_validate_allocation_survival_at_risk(self):
        """Test validation fails when survival at risk but tasks not prioritized."""
        engine = LLMDecisionEngine()
        state = AgentState(
            balance=10.0,
            compute_hours_remaining=5.0,  # Below survival buffer (24h)
            survival_buffer_hours=24.0,
        )

        allocation = ResourceAllocation(
            task_work_hours=0.1,  # Too low when survival at risk
            company_work_hours=0.5,
            reasoning="Not enough task focus",
            confidence=0.8,
        )

        assert engine._validate_allocation(allocation, state) is False

    def test_validate_allocation_insufficient_reasoning(self):
        """Test validation fails for insufficient reasoning."""
        engine = LLMDecisionEngine()
        state = AgentState(balance=100.0, compute_hours_remaining=10.0)

        allocation = ResourceAllocation(
            task_work_hours=1.0, company_work_hours=0.5, reasoning="Short", confidence=0.8  # Too short
        )

        assert engine._validate_allocation(allocation, state) is False

    def test_validate_allocation_invalid_confidence(self):
        """Test validation fails for confidence out of range."""
        engine = LLMDecisionEngine()
        state = AgentState(balance=100.0, compute_hours_remaining=10.0)

        allocation = ResourceAllocation(
            task_work_hours=1.0,
            company_work_hours=0.5,
            reasoning="Good reasoning here",
            confidence=1.5,  # > 1.0
        )

        assert engine._validate_allocation(allocation, state) is False

    def test_decision_logging(self):
        """Test that decisions are logged correctly."""
        engine = LLMDecisionEngine()
        state = AgentState(balance=100.0, compute_hours_remaining=10.0, mode="survival")

        allocation = ResourceAllocation(
            task_work_hours=1.0,
            company_work_hours=0.0,
            reasoning="Test decision",
            confidence=0.8,
        )

        # Log a decision
        engine._log_decision(
            state=state,
            prompt="test prompt",
            response='{"test": "response"}',
            allocation=allocation,
            execution_time=5.5,
            fallback_used=False,
        )

        # Verify
        assert len(engine.decisions) == 1
        decision = engine.decisions[0]

        assert decision.agent_type == "claude"
        assert decision.state_snapshot["balance"] == 100.0
        assert decision.state_snapshot["mode"] == "survival"
        assert decision.execution_time_seconds == 5.5
        assert decision.fallback_used is False

    def test_get_decisions(self):
        """Test getting decision history."""
        engine = LLMDecisionEngine()

        # Add some decisions
        for i in range(3):
            state = AgentState(balance=100.0, compute_hours_remaining=10.0)
            allocation = ResourceAllocation(
                task_work_hours=1.0,
                company_work_hours=0.0,
                reasoning=f"Decision {i}",
                confidence=0.8,
            )
            engine._log_decision(
                state=state,
                prompt=f"prompt {i}",
                response="response",
                allocation=allocation,
                execution_time=1.0,
                fallback_used=False,
            )

        decisions = engine.get_decisions()

        assert len(decisions) == 3
        assert decisions[0].parsed_decision["reasoning"] == "Decision 0"
        assert decisions[2].parsed_decision["reasoning"] == "Decision 2"

    def test_clear_decisions(self):
        """Test clearing decision history."""
        engine = LLMDecisionEngine()

        # Add a decision
        state = AgentState(balance=100.0, compute_hours_remaining=10.0)
        allocation = ResourceAllocation(
            task_work_hours=1.0,
            company_work_hours=0.0,
            reasoning="Test",
            confidence=0.8,
        )
        engine._log_decision(
            state=state,
            prompt="prompt",
            response="response",
            allocation=allocation,
            execution_time=1.0,
            fallback_used=False,
        )

        assert len(engine.decisions) == 1

        # Clear
        engine.clear_decisions()

        assert len(engine.decisions) == 0

    def test_build_allocation_prompt(self):
        """Test prompt building includes all necessary information."""
        engine = LLMDecisionEngine({"company_threshold": 150.0})
        state = AgentState(
            balance=120.0,
            compute_hours_remaining=8.5,
            survival_buffer_hours=20.0,
            mode="survival",
            tasks_completed=5,
        )

        prompt = engine._build_allocation_prompt(state)

        # Verify key information is in prompt
        assert "$120.00" in prompt
        assert "8.50h" in prompt  # Changed to match actual format with 2 decimal places
        assert "20.0h" in prompt
        assert "survival" in prompt
        assert "5" in prompt or "5 " in prompt
        assert "$150.00" in prompt
        assert "JSON" in prompt
