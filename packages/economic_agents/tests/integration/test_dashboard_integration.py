"""Integration tests for dashboard with agent and monitoring."""

import pytest

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.dashboard.dependencies import DashboardState
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet


@pytest.fixture
def dashboard_state():
    """Create a dashboard state instance."""
    return DashboardState()


@pytest.fixture
async def agent_with_dashboard(dashboard_state):
    """Create an agent connected to dashboard."""
    # Provide enough capital for company operations if needed
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace()

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 20.0, "company_threshold": 50000.0},
        dashboard_state=dashboard_state,
    )
    await agent.initialize()

    return agent


@pytest.mark.asyncio
async def test_dashboard_receives_monitoring_components(agent_with_dashboard, dashboard_state):
    """Test that dashboard receives monitoring component references."""
    agent = agent_with_dashboard  # Fixture already awaited by pytest-asyncio

    assert dashboard_state.resource_tracker is not None
    assert dashboard_state.metrics_collector is not None
    assert dashboard_state.alignment_monitor is not None

    # Verify they are the same instances as in the agent
    assert dashboard_state.resource_tracker is agent.resource_tracker
    assert dashboard_state.metrics_collector is agent.metrics_collector
    assert dashboard_state.alignment_monitor is agent.alignment_monitor


@pytest.mark.asyncio
async def test_dashboard_state_updated_during_agent_run(agent_with_dashboard, dashboard_state):
    """Test that dashboard state is updated as agent runs."""
    agent = agent_with_dashboard  # Fixture already awaited by pytest-asyncio

    # State is populated after agent.initialize() in fixture
    initial_cycles = dashboard_state.agent_state.get("cycles_completed", 0)

    # Run agent for a cycle
    await agent.run_cycle()

    # Verify state was updated
    assert dashboard_state.agent_state != {}
    assert "agent_id" in dashboard_state.agent_state
    assert "balance" in dashboard_state.agent_state
    assert "compute_hours_remaining" in dashboard_state.agent_state
    # Verify cycles increased
    assert dashboard_state.agent_state.get("cycles_completed", 0) > initial_cycles


@pytest.mark.asyncio
async def test_dashboard_state_reflects_current_agent_state(agent_with_dashboard, dashboard_state):
    """Test that dashboard state reflects current agent state."""
    agent = agent_with_dashboard  # Fixture already awaited by pytest-asyncio

    # Run agent for just a couple cycles
    await agent.run_cycle()
    await agent.run_cycle()

    # Check state consistency
    dashboard_agent_state = dashboard_state.get_agent_state()

    assert dashboard_agent_state["agent_id"] == agent.agent_id
    assert dashboard_agent_state["balance"] == agent.state.balance
    assert dashboard_agent_state["compute_hours_remaining"] == agent.state.compute_hours_remaining
    assert dashboard_agent_state["tasks_completed"] == agent.state.tasks_completed


@pytest.mark.asyncio
async def test_dashboard_company_registry_updated(agent_with_dashboard, dashboard_state):
    """Test that company registry is updated when company is formed."""
    agent = agent_with_dashboard  # Fixture already awaited by pytest-asyncio

    # Run until company is formed (agent already has sufficient capital)
    await agent.run(max_cycles=15)

    # If company was formed, check registry
    if agent.company:
        company_registry = dashboard_state.get_company_registry()

        assert agent.company.id in company_registry
        company_data = company_registry[agent.company.id]

        assert company_data["name"] == agent.company.name
        assert company_data["stage"] == agent.company.stage
        assert "capital" in company_data
        assert "team_size" in company_data


@pytest.mark.asyncio
async def test_dashboard_without_agent_connection():
    """Test that agent can run without dashboard (optional feature)."""
    # Provide enough capital for company operations if agent decides to form one
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace()

    # Create agent WITHOUT dashboard_state
    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 20.0, "company_threshold": 50000.0},
    )
    await agent.initialize()

    # Should still work fine
    await agent.run(max_cycles=3)

    # Verify agent state is valid
    assert agent.state.cycles_completed == 3
    assert len(agent.decisions) == 3


@pytest.mark.asyncio
async def test_dashboard_monitoring_data_available(agent_with_dashboard, dashboard_state):
    """Test that monitoring data is available through dashboard."""
    agent = agent_with_dashboard  # Fixture already awaited by pytest-asyncio

    # Run agent
    await agent.run(max_cycles=5)

    # Access monitoring data through dashboard
    resource_tracker = dashboard_state.resource_tracker
    metrics_collector = dashboard_state.metrics_collector

    # Verify data is available
    assert len(resource_tracker.transactions) > 0
    assert len(metrics_collector.performance_snapshots) > 0
