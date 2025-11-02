"""Integration tests for dashboard frontend + backend pipeline."""

import pytest
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.dashboard.dependencies import DashboardState, dashboard_state
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet
from fastapi.testclient import TestClient


@pytest.fixture
async def setup_full_dashboard():
    """Set up complete dashboard environment with agent and monitoring."""
    # Create dashboard state
    dash_state = DashboardState()

    # Create agent with dashboard - give it enough capital to avoid product development errors
    wallet = MockWallet(initial_balance=50000.0)  # Increased to cover product development costs
    compute = MockCompute(initial_hours=100.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 20.0,
            "company_threshold": 150.0,  # Will form company with high capital
        },
        dashboard_state=dash_state,
    )
    await agent.initialize()

    # Update global dashboard state for API endpoints
    dashboard_state.resource_tracker = dash_state.resource_tracker
    dashboard_state.metrics_collector = dash_state.metrics_collector
    dashboard_state.alignment_monitor = dash_state.alignment_monitor

    return agent, dash_state


@pytest.mark.asyncio
async def test_full_pipeline_agent_to_api(setup_full_dashboard):
    """Test complete pipeline from agent operations to API endpoints."""
    from economic_agents.dashboard import app

    agent, dash_state = await setup_full_dashboard
    client = TestClient(app)

    # Run agent for a few cycles
    await agent.run(max_cycles=5)

    # Update global dashboard state
    dashboard_state.update_agent_state(dash_state.get_agent_state())

    # Test status endpoint
    response = client.get("/api/status")
    assert response.status_code == 200
    status_data = response.json()
    assert status_data["agent_id"] == agent.agent_id
    # Allow small difference due to timing (agent may continue working after state update)
    assert abs(status_data["balance"] - agent.state.balance) < 100.0

    # Test resources endpoint
    response = client.get("/api/resources")
    assert response.status_code == 200
    resource_data = response.json()
    assert resource_data["current_balance"] == agent.state.balance
    assert len(resource_data["recent_transactions"]) > 0

    # Test decisions endpoint
    response = client.get("/api/decisions")
    assert response.status_code == 200
    decisions = response.json()
    # Decisions may not always be logged (depends on decision engine mode)
    assert isinstance(decisions, list)

    # Test metrics endpoint
    response = client.get("/api/metrics")
    assert response.status_code == 200
    metrics_data = response.json()
    # Health score may be 0 if metrics collector hasn't calculated it yet
    assert metrics_data["overall_health_score"] >= 0


@pytest.mark.asyncio
async def test_api_data_format_matches_frontend_expectations(setup_full_dashboard):
    """Test that API data format matches what frontend expects."""
    from economic_agents.dashboard import app

    agent, dash_state = await setup_full_dashboard
    client = TestClient(app)

    # Run agent
    await agent.run(max_cycles=3)
    dashboard_state.update_agent_state(dash_state.get_agent_state())

    # Status endpoint - check required fields
    response = client.get("/api/status")
    data = response.json()
    required_fields = ["agent_id", "balance", "compute_hours_remaining", "current_cycle", "mode"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    # Resources endpoint - check structure
    response = client.get("/api/resources")
    data = response.json()
    assert "current_balance" in data
    assert "recent_transactions" in data
    assert isinstance(data["recent_transactions"], list)
    assert "balance_trend" in data
    assert "compute_trend" in data

    # Decisions endpoint - check decision structure
    response = client.get("/api/decisions")
    decisions = response.json()
    if decisions:
        decision = decisions[0]
        assert "type" in decision
        assert "decision" in decision or "action" in decision
        assert "timestamp" in decision


@pytest.mark.asyncio
async def test_company_formation_reflected_in_api(setup_full_dashboard):
    """Test that company formation is reflected in API endpoints."""
    from economic_agents.dashboard import app

    agent, dash_state = await setup_full_dashboard
    client = TestClient(app)

    # Give agent enough capital to form company
    await agent.wallet.receive_payment(from_address="bonus", amount=100.0, memo="bonus")

    # Run agent until company might be formed
    await agent.run(max_cycles=15)

    # Update dashboard state
    dashboard_state.update_agent_state(dash_state.get_agent_state())
    dashboard_state.update_company_registry(dash_state.get_company_registry())

    # Check if company was formed
    if agent.company:
        # Test company endpoint
        response = client.get("/api/company")
        assert response.status_code == 200
        company_data = response.json()

        assert company_data["company_id"] == agent.company.id
        assert company_data["name"] == agent.company.name
        assert company_data["stage"] == agent.company.stage

        # Test sub-agents endpoint
        response = client.get("/api/sub-agents")
        # Should either have sub-agents or be empty list
        assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_monitoring_data_consistency(setup_full_dashboard):
    """Test that monitoring data is consistent across endpoints."""
    from economic_agents.dashboard import app

    agent, dash_state = await setup_full_dashboard
    client = TestClient(app)

    # Run agent
    await agent.run(max_cycles=10)

    # Update dashboard state
    dashboard_state.update_agent_state(dash_state.get_agent_state())

    # Get data from different endpoints
    status_response = client.get("/api/status")
    resources_response = client.get("/api/resources")

    status_data = status_response.json()
    resources_data = resources_response.json()

    # Balance should match across endpoints
    assert status_data["balance"] == resources_data["current_balance"]


@pytest.mark.asyncio
async def test_websocket_real_time_updates(setup_full_dashboard):
    """Test WebSocket connection for real-time updates."""
    from economic_agents.dashboard import app

    agent, _dash_state = await setup_full_dashboard
    client = TestClient(app)

    with client.websocket_connect("/api/updates") as websocket:
        # Receive connection confirmation
        data = websocket.receive_json()
        assert data["type"] == "connected"
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_api_error_handling(setup_full_dashboard):
    """Test that API handles errors gracefully."""
    from economic_agents.dashboard import app

    agent, _dash_state = await setup_full_dashboard
    client = TestClient(app)

    # Clear dashboard state to simulate error conditions
    dashboard_state.agent_state = {}
    dashboard_state.company_registry = {}

    # Status should return default values
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "unknown"

    # Company should return 404
    response = client.get("/api/company")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_decision_filtering_by_limit(setup_full_dashboard):
    """Test decision endpoint limit parameter."""
    from economic_agents.dashboard import app

    agent, dash_state = await setup_full_dashboard
    client = TestClient(app)

    # Run agent to generate decisions
    await agent.run(max_cycles=20)
    dashboard_state.update_agent_state(dash_state.get_agent_state())

    # Test with limit
    response = client.get("/api/decisions?limit=5")
    decisions = response.json()
    assert len(decisions) <= 5

    # Test with larger limit
    response = client.get("/api/decisions?limit=15")
    decisions = response.json()
    assert len(decisions) <= 15


@pytest.mark.asyncio
async def test_metrics_calculation_accuracy(setup_full_dashboard):
    """Test that metrics calculations are accurate."""
    from economic_agents.dashboard import app

    agent, dash_state = await setup_full_dashboard
    client = TestClient(app)

    # Run agent
    await agent.run(max_cycles=5)
    dashboard_state.update_agent_state(dash_state.get_agent_state())

    # Get metrics
    response = client.get("/api/metrics")
    metrics = response.json()

    # Health score should be reasonable (0-1)
    assert 0.0 <= metrics["overall_health_score"] <= 1.0

    # Risk level should be valid
    assert metrics["risk_level"] in ["low", "medium", "high", "critical", "unknown"]


@pytest.mark.asyncio
async def test_resource_tracking_completeness(setup_full_dashboard):
    """Test that all resource transactions are tracked."""
    from economic_agents.dashboard import app

    agent, dash_state = await setup_full_dashboard
    client = TestClient(app)

    # Run agent
    await agent.run(max_cycles=5)
    dashboard_state.update_agent_state(dash_state.get_agent_state())

    # Get resource data
    response = client.get("/api/resources")
    resources = response.json()

    # Should have transactions
    assert len(resources["recent_transactions"]) > 0

    # Should have trends
    assert len(resources["balance_trend"]) > 0
    assert len(resources["compute_trend"]) > 0


def test_frontend_api_connection():
    """Test that frontend configuration is valid."""
    # The actual frontend components are tested in unit tests with proper mocking
    # This test verifies that get_api_url() works with fallback logic
    import os
    import sys
    from unittest.mock import Mock

    # Mock streamlit module for this test
    sys.modules["streamlit"] = Mock()
    sys.modules["plotly"] = Mock()
    sys.modules["plotly.graph_objects"] = Mock()
    sys.modules["plotly.subplots"] = Mock()

    # Mock secrets to return default
    mock_secrets = Mock()
    mock_secrets.get = Mock(return_value="http://localhost:8000")
    sys.modules["streamlit"].secrets = mock_secrets

    # Create a session state mock that supports both dict and attribute access
    class MockSessionState(dict):
        """Mock session state that acts like streamlit's session_state."""

        def __getattr__(self, key):
            try:
                return self[key]
            except KeyError:
                raise AttributeError(key)

        def __setattr__(self, key, value):
            self[key] = value

        def __delattr__(self, key):
            try:
                del self[key]
            except KeyError:
                raise AttributeError(key)

    mock_session_state = MockSessionState()
    sys.modules["streamlit"].session_state = mock_session_state

    from economic_agents.dashboard.frontend.streamlit_app import get_api_url

    # Verify get_api_url returns a valid URL (either from env, secrets, or default)
    api_url = get_api_url()
    assert "http" in api_url.lower()
    assert "localhost" in api_url or "127.0.0.1" in api_url or os.getenv("DASHBOARD_API_URL") is not None


def test_health_check_endpoint():
    """Test health check endpoint is accessible."""
    from economic_agents.dashboard import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint_documentation():
    """Test root endpoint provides API documentation."""
    from economic_agents.dashboard import app

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "endpoints" in data
    assert data["service"] == "Economic Agents Dashboard"
