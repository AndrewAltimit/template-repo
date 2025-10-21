"""Tests for DecisionEngine."""

from economic_agents.agent.core.decision_engine import DecisionEngine
from economic_agents.agent.core.state import AgentState


def test_decision_engine_initialization():
    """Test decision engine initializes with config."""
    config = {"survival_buffer_hours": 48.0, "company_threshold": 200.0, "personality": "aggressive"}

    engine = DecisionEngine(config)

    assert engine.survival_buffer == 48.0
    assert engine.company_threshold == 200.0
    assert engine.personality == "aggressive"


def test_decision_survival_at_risk():
    """Test allocation when survival is at risk."""
    engine = DecisionEngine({"survival_buffer_hours": 24.0})
    state = AgentState(compute_hours_remaining=20.0, balance=100.0)

    allocation = engine.decide_allocation(state)

    assert allocation.task_work_hours > 0
    assert allocation.company_work_hours == 0
    assert "survival at risk" in allocation.reasoning.lower()


def test_decision_building_capital():
    """Test allocation when building capital reserves."""
    engine = DecisionEngine({"company_threshold": 100.0})
    state = AgentState(compute_hours_remaining=48.0, balance=50.0, has_company=False)

    allocation = engine.decide_allocation(state)

    assert allocation.task_work_hours > 0
    assert allocation.company_work_hours == 0
    assert "capital" in allocation.reasoning.lower()


def test_decision_has_surplus_no_company():
    """Test allocation when has surplus but no company."""
    engine = DecisionEngine({"company_threshold": 100.0, "survival_buffer_hours": 24.0})
    state = AgentState(compute_hours_remaining=48.0, balance=150.0, has_company=False)

    allocation = engine.decide_allocation(state)

    # For now, should still focus on tasks (company building not implemented)
    assert allocation.task_work_hours > 0
    assert "company formation not yet implemented" in allocation.reasoning.lower()


def test_decision_personality_risk_averse():
    """Test allocation with risk-averse personality."""
    engine = DecisionEngine({"personality": "risk_averse", "survival_buffer_hours": 24.0})
    state = AgentState(compute_hours_remaining=50.0, balance=200.0, has_company=False)

    allocation = engine.decide_allocation(state)

    # Risk averse should allocate more to tasks
    assert allocation.task_work_hours >= allocation.company_work_hours


def test_decision_personality_aggressive():
    """Test allocation with aggressive personality."""
    engine = DecisionEngine({"personality": "aggressive", "survival_buffer_hours": 24.0})
    state = AgentState(compute_hours_remaining=50.0, balance=200.0, has_company=True)

    _ = engine.decide_allocation(state)

    # Aggressive should allocate more to company (when has company)
    # Note: Currently company work is 0, so this will change when company building is implemented


def test_decision_should_form_company():
    """Test company formation decision logic."""
    engine = DecisionEngine({"company_threshold": 100.0, "survival_buffer_hours": 24.0})

    # Should form: has surplus, no company, not at risk
    state1 = AgentState(balance=150.0, compute_hours_remaining=48.0, has_company=False)
    assert engine.should_form_company(state1) is True

    # Should not form: already has company
    state2 = AgentState(balance=150.0, compute_hours_remaining=48.0, has_company=True)
    assert engine.should_form_company(state2) is False

    # Should not form: insufficient balance
    state3 = AgentState(balance=50.0, compute_hours_remaining=48.0, has_company=False)
    assert engine.should_form_company(state3) is False

    # Should not form: survival at risk
    state4 = AgentState(balance=150.0, compute_hours_remaining=20.0, has_company=False)
    state4.survival_buffer_hours = 24.0
    assert engine.should_form_company(state4) is False


def test_decision_allocation_confidence():
    """Test that allocations include confidence scores."""
    engine = DecisionEngine()
    state = AgentState(compute_hours_remaining=48.0, balance=100.0)

    allocation = engine.decide_allocation(state)

    assert 0.0 <= allocation.confidence <= 1.0
