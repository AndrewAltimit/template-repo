"""Tests for LLM decision visualization in dashboard."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from economic_agents.dashboard.agent_manager import agent_manager
from economic_agents.dashboard.app import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_llm_agent():
    """Create mock agent with LLM decision engine."""
    mock_agent = MagicMock()
    mock_decision_engine = MagicMock()

    # Mock LLM decisions
    mock_decisions = [
        MagicMock(
            decision_id="dec_0_1234567890",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            agent_type="claude",
            state_snapshot={
                "balance": 100.0,
                "compute_hours_remaining": 50.0,
                "has_company": False,
                "mode": "survival",
                "tasks_completed": 0,
            },
            prompt="You are an autonomous economic agent...",
            raw_response='{"task_work_hours": 26.0, "company_work_hours": 0.0, '
            '"reasoning": "Strategic allocation", "confidence": 0.85}',
            parsed_decision={
                "task_work_hours": 26.0,
                "company_work_hours": 0.0,
                "reasoning": "Strategic allocation for survival",
                "confidence": 0.85,
            },
            validation_passed=True,
            execution_time_seconds=45.23,
            fallback_used=False,
        ),
        MagicMock(
            decision_id="dec_1_1234567891",
            timestamp=datetime(2024, 1, 1, 12, 1, 0),
            agent_type="claude",
            state_snapshot={
                "balance": 120.0,
                "compute_hours_remaining": 24.0,
                "has_company": False,
                "mode": "survival",
                "tasks_completed": 1,
            },
            prompt="You are an autonomous economic agent...",
            raw_response="Error: timeout",
            parsed_decision={
                "task_work_hours": 20.0,
                "company_work_hours": 0.0,
                "reasoning": "Fallback to rule-based due to timeout",
                "confidence": 0.50,
            },
            validation_passed=False,
            execution_time_seconds=5.0,
            fallback_used=True,
        ),
    ]

    mock_decision_engine.get_decisions.return_value = mock_decisions
    mock_agent.decision_engine = mock_decision_engine

    return mock_agent


def test_llm_decisions_endpoint_no_agent(client):
    """Test LLM decisions endpoint when no agent is running."""
    response = client.get("/api/decisions/llm")
    assert response.status_code == 200
    assert response.json() == []


def test_llm_decisions_endpoint_with_llm_agent(client, mock_llm_agent):
    """Test LLM decisions endpoint with LLM agent."""
    with patch.object(agent_manager, "agent", mock_llm_agent):
        response = client.get("/api/decisions/llm")
        assert response.status_code == 200

        decisions = response.json()
        assert len(decisions) == 2

        # Check first decision
        assert decisions[0]["decision_id"] == "dec_0_1234567890"
        assert decisions[0]["agent_type"] == "claude"
        assert decisions[0]["execution_time_seconds"] == 45.23
        assert decisions[0]["fallback_used"] is False
        assert decisions[0]["validation_passed"] is True
        assert decisions[0]["parsed_decision"]["confidence"] == 0.85

        # Check second decision (fallback)
        assert decisions[1]["decision_id"] == "dec_1_1234567891"
        assert decisions[1]["fallback_used"] is True
        assert decisions[1]["validation_passed"] is False


def test_llm_decisions_endpoint_limit(client, mock_llm_agent):
    """Test LLM decisions endpoint respects limit parameter."""
    with patch.object(agent_manager, "agent", mock_llm_agent):
        response = client.get("/api/decisions/llm?limit=1")
        assert response.status_code == 200

        decisions = response.json()
        assert len(decisions) == 1


def test_llm_decisions_endpoint_rule_based_agent(client):
    """Test LLM decisions endpoint with rule-based agent (no get_decisions method)."""
    mock_agent = MagicMock()
    mock_agent.decision_engine = MagicMock(spec=[])  # No get_decisions method

    with patch.object(agent_manager, "agent", mock_agent):
        response = client.get("/api/decisions/llm")
        assert response.status_code == 200
        assert response.json() == []


def test_agent_start_with_llm_engine(client):
    """Test starting agent with LLM engine configuration."""
    config = {
        "mode": "survival",
        "max_cycles": 10,
        "initial_balance": 100.0,
        "initial_compute_hours": 50.0,
        "compute_cost_per_hour": 0.0,
        "engine_type": "llm",
        "llm_timeout": 120,
    }

    # Stop any running agent first
    try:
        client.post("/api/agent/stop")
    except Exception:
        pass

    response = client.post("/api/agent/start", json=config)
    assert response.status_code == 200

    result = response.json()
    assert result["status"] == "started"
    assert result["mode"] == "survival"

    # Check control status shows LLM config
    # Note: Agent may have already completed if cycles run fast
    status_response = client.get("/api/agent/control-status")
    assert status_response.status_code == 200

    status = status_response.json()
    # Config should be preserved even if agent finished
    assert status["config"]["engine_type"] == "llm"
    assert status["config"]["llm_timeout"] == 120

    # Clean up
    client.post("/api/agent/stop")


def test_agent_start_with_rule_based_engine(client):
    """Test starting agent with rule-based engine (default)."""
    config = {
        "mode": "survival",
        "max_cycles": 10,
        "initial_balance": 100.0,
        "initial_compute_hours": 50.0,
        "compute_cost_per_hour": 0.0,
        "engine_type": "rule_based",
        "llm_timeout": 120,
    }

    # Stop any running agent first
    try:
        client.post("/api/agent/stop")
    except Exception:
        pass

    response = client.post("/api/agent/start", json=config)
    assert response.status_code == 200

    result = response.json()
    assert result["status"] == "started"

    # Check control status shows rule-based config
    # Note: Agent may have already completed if cycles run fast
    status_response = client.get("/api/agent/control-status")
    assert status_response.status_code == 200

    status = status_response.json()
    # Config should be preserved even if agent finished
    assert status["config"]["engine_type"] == "rule_based"

    # Clean up
    client.post("/api/agent/stop")


def test_llm_decision_response_model():
    """Test LLMDecisionResponse model validation."""
    from economic_agents.dashboard.models import LLMDecisionResponse

    decision = LLMDecisionResponse(
        decision_id="dec_test",
        timestamp=datetime.now(),
        agent_type="claude",
        state_snapshot={"balance": 100.0},
        prompt="Test prompt",
        raw_response='{"test": true}',
        parsed_decision={"test": True},
        validation_passed=True,
        execution_time_seconds=30.0,
        fallback_used=False,
    )

    assert decision.decision_id == "dec_test"
    assert decision.agent_type == "claude"
    assert decision.execution_time_seconds == 30.0
    assert decision.fallback_used is False


def test_decision_response_model_with_llm_fields():
    """Test DecisionResponse model includes LLM-specific fields."""
    from economic_agents.dashboard.models import DecisionResponse

    decision = DecisionResponse(
        id="test_decision",
        timestamp=datetime.now(),
        decision_type="allocation",
        reasoning="Test reasoning",
        confidence=0.85,
        engine_type="llm",
        execution_time_seconds=45.0,
        fallback_used=False,
        validation_passed=True,
        raw_response='{"test": true}',
    )

    assert decision.engine_type == "llm"
    assert decision.execution_time_seconds == 45.0
    assert decision.fallback_used is False
    assert decision.validation_passed is True


def test_agent_start_request_model():
    """Test AgentStartRequest model includes engine_type and llm_timeout."""
    from economic_agents.dashboard.models import AgentStartRequest

    request = AgentStartRequest(
        mode="survival",
        max_cycles=50,
        initial_balance=100.0,
        initial_compute_hours=100.0,
        compute_cost_per_hour=0.0,
        engine_type="llm",
        llm_timeout=120,
    )

    assert request.engine_type == "llm"
    assert request.llm_timeout == 120


def test_agent_start_request_defaults():
    """Test AgentStartRequest model uses correct defaults."""
    from economic_agents.dashboard.models import AgentStartRequest

    request = AgentStartRequest()

    assert request.mode == "survival"
    assert request.engine_type == "rule_based"
    assert request.llm_timeout == 120
    assert request.max_cycles == 50
