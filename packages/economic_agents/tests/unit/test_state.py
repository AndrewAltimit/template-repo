"""Tests for AgentState."""

from economic_agents.agent.core.state import AgentState


def test_state_initialization():
    """Test agent state initializes with defaults."""
    state = AgentState()

    assert state.balance == 0.0
    assert state.compute_hours_remaining == 0.0
    assert state.mode == "survival"
    assert state.is_active is True
    assert state.cycles_completed == 0


def test_state_update_balance():
    """Test updating balance tracks earnings and spending."""
    state = AgentState(balance=100.0)

    state.update_balance(50.0)  # Earn
    assert state.balance == 150.0
    assert state.total_earned == 50.0
    assert state.total_spent == 0.0

    state.update_balance(-30.0)  # Spend
    assert state.balance == 120.0
    assert state.total_earned == 50.0
    assert state.total_spent == 30.0


def test_state_is_survival_at_risk():
    """Test survival risk detection."""
    state = AgentState(compute_hours_remaining=48.0, survival_buffer_hours=24.0)
    assert state.is_survival_at_risk() is False

    state.compute_hours_remaining = 20.0
    assert state.is_survival_at_risk() is True

    state.compute_hours_remaining = 0.0
    assert state.is_survival_at_risk() is True


def test_state_has_surplus_capital():
    """Test surplus capital detection."""
    state = AgentState(balance=150.0)

    assert state.has_surplus_capital(100.0) is True
    assert state.has_surplus_capital(200.0) is False
    assert state.has_surplus_capital(150.0) is False  # Equal is not surplus


def test_state_to_dict():
    """Test converting state to dictionary."""
    state = AgentState(balance=100.0, compute_hours_remaining=24.0, mode="entrepreneur")

    state_dict = state.to_dict()

    assert state_dict["balance"] == 100.0
    assert state_dict["compute_hours_remaining"] == 24.0
    assert state_dict["mode"] == "entrepreneur"
    assert "created_at" not in state_dict  # Should not include timestamps


def test_state_company_tracking():
    """Test company-related state fields."""
    state = AgentState()

    assert state.has_company is False
    assert state.company_id is None

    state.company_id = "company_123"
    state.has_company = True

    assert state.has_company is True
    assert state.company_id == "company_123"
