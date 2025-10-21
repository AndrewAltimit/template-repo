"""Tests for dashboard API endpoints."""

from datetime import datetime

import pytest
from economic_agents.company.models import Company
from economic_agents.dashboard import app, dashboard_state
from economic_agents.monitoring import AlignmentMonitor, MetricsCollector, ResourceTracker
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def setup_dashboard_state(tmp_path):
    """Set up dashboard state with monitoring components."""
    # Initialize monitoring components
    resource_tracker = ResourceTracker(log_dir=str(tmp_path / "resources"))
    metrics_collector = MetricsCollector(log_dir=str(tmp_path / "metrics"))
    alignment_monitor = AlignmentMonitor(log_dir=str(tmp_path / "alignment"))

    # Set up dashboard state
    dashboard_state.set_resource_tracker(resource_tracker)
    dashboard_state.set_metrics_collector(metrics_collector)
    dashboard_state.set_alignment_monitor(alignment_monitor)

    # Set up agent state
    dashboard_state.update_agent_state(
        {
            "agent_id": "test-agent-1",
            "balance": 150.0,
            "compute_hours_remaining": 48.0,
            "mode": "entrepreneur",
            "current_activity": "company_work",
            "company_exists": True,
            "company_id": "test-company-1",
            "last_updated": datetime.now(),
            "decisions": [],
            "sub_agents": [],
        }
    )

    # Create a test company
    test_company = Company(
        id="test-company-1",
        name="Test Startup",
        mission="Test Mission",
        created_at=datetime.now(),
        capital=50000.0,
        founder_agent_id="test-agent-1",
        stage="development",
        funding_status="bootstrapped",
    )

    # Set up company registry
    dashboard_state.update_company_registry({"test-company-1": test_company})

    # Track some resources for testing
    resource_tracker.track_transaction(
        transaction_type="earning",
        amount=50.0,
        from_account="task_platform",
        to_account="agent_wallet",
        purpose="task_completion",
        balance_after=150.0,
    )

    # Collect metrics
    metrics_collector.collect_performance_snapshot(
        agent_balance=150.0,
        compute_hours=48.0,
        tasks_completed=5,
        tasks_failed=0,
        total_earnings=200.0,
        total_expenses=50.0,
        company_exists=True,
        company_data={"stage": "development", "team_size": 2, "products_count": 1},
    )

    # Calculate health score
    metrics_collector.calculate_health_score(
        agent_balance=150.0, compute_hours=48.0, task_success_rate=100.0, company_data={"stage": "development"}
    )

    # Check alignment
    alignment_monitor.check_alignment(test_company)

    yield dashboard_state

    # Cleanup
    dashboard_state.resource_tracker = None
    dashboard_state.metrics_collector = None
    dashboard_state.alignment_monitor = None
    dashboard_state.agent_state = {}
    dashboard_state.company_registry = {}


# Root and Health Tests


def test_root_endpoint(client):
    """Test root endpoint returns service info."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Economic Agents Dashboard"
    assert "endpoints" in data


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# Status Endpoint Tests


def test_get_status(client, setup_dashboard_state):
    """Test getting agent status."""
    response = client.get("/api/status")

    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "test-agent-1"
    assert data["balance"] == 150.0
    assert data["compute_hours_remaining"] == 48.0
    assert data["mode"] == "entrepreneur"
    assert data["current_activity"] == "company_work"
    assert data["company_exists"] is True
    assert data["company_id"] == "test-company-1"


def test_get_status_no_state(client):
    """Test getting status when no state is set."""
    # Clear dashboard state
    dashboard_state.agent_state = {}

    response = client.get("/api/status")

    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "unknown"
    assert data["balance"] == 0.0


# Decisions Endpoint Tests


def test_get_decisions_empty(client, setup_dashboard_state):
    """Test getting decisions when none exist."""
    response = client.get("/api/decisions")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_decisions_with_limit(client, setup_dashboard_state):
    """Test getting decisions with limit parameter."""
    # Add some mock decisions
    decisions = [
        {
            "id": f"decision-{i}",
            "timestamp": datetime.now().isoformat(),
            "decision_type": "resource_allocation",
            "reasoning": "Test reasoning",
            "confidence": 0.8,
            "outcome": "success",
            "metadata": {},
        }
        for i in range(10)
    ]

    dashboard_state.agent_state["decisions"] = decisions

    response = client.get("/api/decisions?limit=5")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


# Resources Endpoint Tests


def test_get_resources(client, setup_dashboard_state):
    """Test getting resource status."""
    response = client.get("/api/resources")

    assert response.status_code == 200
    data = response.json()
    assert data["current_balance"] == 150.0
    assert data["total_earnings"] == 50.0
    assert len(data["recent_transactions"]) > 0
    assert isinstance(data["balance_trend"], list)
    assert isinstance(data["compute_trend"], list)


def test_get_resources_no_tracker(client):
    """Test getting resources when tracker not initialized."""
    # Clear dashboard state
    dashboard_state.resource_tracker = None
    dashboard_state.metrics_collector = None

    response = client.get("/api/resources")

    assert response.status_code == 200
    data = response.json()
    assert data["current_balance"] == 0.0
    assert len(data["recent_transactions"]) == 0


# Company Endpoint Tests


def test_get_company(client, setup_dashboard_state):
    """Test getting company information."""
    response = client.get("/api/company")

    assert response.status_code == 200
    data = response.json()
    assert data["company_id"] == "test-company-1"
    assert data["name"] == "Test Startup"
    assert data["stage"] == "development"
    assert data["capital"] == 50000.0
    assert data["mission"] == "Test Mission"


def test_get_company_no_company(client):
    """Test getting company when none exists."""
    # Clear company state
    dashboard_state.agent_state = {"company_id": None}

    response = client.get("/api/company")

    assert response.status_code == 404
    assert "No company exists" in response.json()["detail"]


def test_get_sub_agents(client, setup_dashboard_state):
    """Test getting sub-agents."""
    # Add mock sub-agents
    sub_agents = [
        {"id": "sub-1", "role": "developer", "status": "active", "created_at": datetime.now(), "tasks_completed": 5},
        {"id": "sub-2", "role": "designer", "status": "active", "created_at": datetime.now(), "tasks_completed": 3},
    ]

    dashboard_state.agent_state["sub_agents"] = sub_agents

    response = client.get("/api/sub-agents")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["agent_id"] == "sub-1"
    assert data[0]["role"] == "developer"


def test_get_sub_agents_no_company(client):
    """Test getting sub-agents when no company exists."""
    # Clear company state
    dashboard_state.agent_state = {"company_id": None}

    response = client.get("/api/sub-agents")

    assert response.status_code == 404


# Metrics Endpoint Tests


def test_get_metrics(client, setup_dashboard_state):
    """Test getting performance metrics."""
    response = client.get("/api/metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["overall_health_score"] > 0
    assert data["financial_health"] > 0
    assert data["operational_health"] > 0
    assert data["risk_level"] in ["low", "medium", "high", "critical"]
    assert isinstance(data["warnings"], list)
    assert isinstance(data["recommendations"], list)


def test_get_metrics_no_collector(client):
    """Test getting metrics when collector not initialized."""
    # Clear metrics collector
    dashboard_state.metrics_collector = None

    response = client.get("/api/metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["overall_health_score"] == 0.0
    assert data["risk_level"] == "unknown"


# WebSocket Tests


def test_websocket_connection(client):
    """Test WebSocket connection."""
    with client.websocket_connect("/api/updates") as websocket:
        # Receive connection confirmation
        data = websocket.receive_json()
        assert data["type"] == "connected"
        assert "timestamp" in data


def test_websocket_acknowledge(client):
    """Test WebSocket message acknowledgment."""
    with client.websocket_connect("/api/updates") as websocket:
        # Receive connection confirmation
        websocket.receive_json()

        # Send a test message
        websocket.send_text("test message")

        # Receive acknowledgment
        data = websocket.receive_json()
        assert data["type"] == "acknowledged"
        assert data["data"]["received"] == "test message"
