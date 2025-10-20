"""Unit tests for agent control router and AgentManager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from economic_agents.dashboard.agent_manager import AgentManager
from economic_agents.dashboard.app import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def mock_agent_manager():
    """Create a mock AgentManager for testing."""
    with patch("economic_agents.dashboard.routers.agent_control.agent_manager") as mock:
        yield mock


@pytest.fixture
async def clean_agent_manager():
    """Provide a clean AgentManager instance for testing."""
    manager = AgentManager()
    # Reset state
    manager.is_running = False
    manager.agent = None
    manager.task = None
    manager.cycle_count = 0
    manager.max_cycles = 0
    manager.should_stop = False
    manager.config = {}

    # Mock file operations to avoid permission errors in tests
    mock_file = MagicMock()
    with patch("builtins.open", return_value=mock_file):
        yield manager

    # Cleanup
    if manager.is_running:
        await manager.stop_agent()


class TestAgentControlRouter:
    """Test suite for agent control API endpoints."""

    def test_start_agent_success(self, mock_agent_manager):
        """Test successful agent start."""
        # Setup mock
        mock_agent_manager.start_agent = AsyncMock(
            return_value={
                "status": "started",
                "agent_id": "test-123",
                "mode": "survival",
                "max_cycles": 50,
                "initial_balance": 100.0,
            }
        )

        # Make request
        response = client.post(
            "/api/agent/start",
            json={
                "mode": "survival",
                "max_cycles": 50,
                "initial_balance": 100.0,
                "initial_compute_hours": 100.0,
                "compute_cost_per_hour": 0.0,
            },
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["agent_id"] == "test-123"
        assert data["mode"] == "survival"

    def test_start_agent_already_running(self, mock_agent_manager):
        """Test starting agent when one is already running."""
        # Setup mock to raise RuntimeError
        mock_agent_manager.start_agent = AsyncMock(side_effect=RuntimeError("Agent is already running"))

        # Make request
        response = client.post(
            "/api/agent/start",
            json={
                "mode": "survival",
                "max_cycles": 50,
                "initial_balance": 100.0,
                "initial_compute_hours": 100.0,
                "compute_cost_per_hour": 0.0,
            },
        )

        # Assertions
        assert response.status_code == 400
        assert "already running" in response.json()["detail"]

    def test_start_agent_invalid_mode(self, mock_agent_manager):
        """Test starting agent with invalid mode."""
        # Setup mock to raise ValueError
        mock_agent_manager.start_agent = AsyncMock(side_effect=ValueError("Invalid mode"))

        # Make request
        response = client.post(
            "/api/agent/start",
            json={
                "mode": "invalid",
                "max_cycles": 50,
                "initial_balance": 100.0,
                "initial_compute_hours": 100.0,
                "compute_cost_per_hour": 0.0,
            },
        )

        # Assertions
        assert response.status_code == 422

    def test_stop_agent_success(self, mock_agent_manager):
        """Test successful agent stop."""
        # Setup mock
        mock_agent_manager.stop_agent = AsyncMock(
            return_value={
                "status": "stopped",
                "cycles_completed": 25,
                "final_balance": 200.0,
                "compute_remaining": 75.0,
                "tasks_completed": 3,
                "company_formed": False,
            }
        )

        # Make request
        response = client.post("/api/agent/stop")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"
        assert data["cycles_completed"] == 25
        assert data["final_balance"] == 200.0

    def test_stop_agent_not_running(self, mock_agent_manager):
        """Test stopping agent when none is running."""
        # Setup mock
        mock_agent_manager.stop_agent = AsyncMock(return_value={"status": "not_running"})

        # Make request
        response = client.post("/api/agent/stop")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_running"

    def test_get_control_status_running(self, mock_agent_manager):
        """Test getting control status when agent is running."""
        # Setup mock
        mock_agent_manager.get_status = AsyncMock(
            return_value={
                "is_running": True,
                "cycle_count": 10,
                "max_cycles": 50,
                "config": {"mode": "survival"},
                "agent_id": "test-456",
                "balance": 150.0,
                "compute_hours": 90.0,
                "has_company": False,
                "tasks_completed": 2,
            }
        )

        # Make request
        response = client.get("/api/agent/control-status")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is True
        assert data["cycle_count"] == 10
        assert data["agent_id"] == "test-456"

    def test_get_control_status_not_running(self, mock_agent_manager):
        """Test getting control status when no agent is running."""
        # Setup mock
        mock_agent_manager.get_status = AsyncMock(
            return_value={
                "is_running": False,
                "cycle_count": 0,
                "max_cycles": 0,
                "config": {},
            }
        )

        # Make request
        response = client.get("/api/agent/control-status")

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is False
        assert data["cycle_count"] == 0


@pytest.mark.asyncio
class TestAgentManager:
    """Test suite for AgentManager class."""

    async def test_singleton_pattern(self):
        """Test that AgentManager follows singleton pattern."""
        manager1 = AgentManager()
        manager2 = AgentManager()
        assert manager1 is manager2

    async def test_start_agent_survival_mode(self, clean_agent_manager):
        """Test starting agent in survival mode."""
        manager = clean_agent_manager

        result = await manager.start_agent(
            mode="survival",
            max_cycles=10,
            initial_balance=100.0,
            initial_compute_hours=100.0,
        )

        assert result["status"] == "started"
        assert result["mode"] == "survival"
        assert result["max_cycles"] == 10
        assert manager.is_running is True
        assert manager.agent is not None

        # Cleanup
        await manager.stop_agent()

    async def test_start_agent_company_mode(self, clean_agent_manager):
        """Test starting agent in company mode."""
        manager = clean_agent_manager

        result = await manager.start_agent(
            mode="company",
            max_cycles=10,
            initial_balance=50000.0,
            initial_compute_hours=100.0,
        )

        assert result["status"] == "started"
        assert result["mode"] == "company"
        assert result["initial_balance"] == 50000.0
        assert manager.is_running is True

        # Cleanup
        await manager.stop_agent()

    async def test_start_agent_already_running_error(self, clean_agent_manager):
        """Test that starting agent when one is running raises error."""
        manager = clean_agent_manager

        # Start first agent
        await manager.start_agent(mode="survival", max_cycles=10)

        # Try to start second agent
        with pytest.raises(RuntimeError, match="already running"):
            await manager.start_agent(mode="survival", max_cycles=10)

        # Cleanup
        await manager.stop_agent()

    async def test_start_agent_invalid_mode_error(self, clean_agent_manager):
        """Test that invalid mode raises ValueError."""
        manager = clean_agent_manager

        with pytest.raises(ValueError, match="Invalid mode"):
            await manager.start_agent(mode="invalid", max_cycles=10)

    async def test_stop_agent_success(self, clean_agent_manager):
        """Test stopping a running agent."""
        manager = clean_agent_manager

        # Start agent with enough cycles to not complete immediately
        await manager.start_agent(mode="survival", max_cycles=100)

        # Let it run a few cycles
        await asyncio.sleep(1.5)

        # Verify it's still running
        assert manager.is_running is True

        # Stop agent
        result = await manager.stop_agent()

        assert result["status"] == "stopped"
        assert "cycles_completed" in result
        assert result["cycles_completed"] < 100  # Stopped before max
        assert manager.is_running is False

    async def test_stop_agent_not_running(self, clean_agent_manager):
        """Test stopping when no agent is running."""
        manager = clean_agent_manager

        result = await manager.stop_agent()

        assert result["status"] == "not_running"

    async def test_get_status_running(self, clean_agent_manager):
        """Test getting status when agent is running."""
        manager = clean_agent_manager

        # Start agent
        await manager.start_agent(mode="survival", max_cycles=10, initial_balance=100.0)

        # Get status
        status = await manager.get_status()

        assert status["is_running"] is True
        assert status["max_cycles"] == 10
        assert "agent_id" in status
        assert status["balance"] == 100.0

        # Cleanup
        await manager.stop_agent()

    async def test_get_status_not_running(self, clean_agent_manager):
        """Test getting status when no agent is running."""
        manager = clean_agent_manager

        status = await manager.get_status()

        assert status["is_running"] is False
        assert status["cycle_count"] == 0
        assert status["max_cycles"] == 0

    async def test_agent_runs_cycles(self, clean_agent_manager):
        """Test that agent actually runs cycles."""
        manager = clean_agent_manager

        # Start agent
        await manager.start_agent(mode="survival", max_cycles=10)

        # Let it run some cycles
        await asyncio.sleep(1.5)

        # Check that cycles were run
        status = await manager.get_status()
        assert status["cycle_count"] >= 1
        assert status["is_running"] is True

        # Cleanup
        await manager.stop_agent()

    async def test_agent_stops_at_max_cycles(self, clean_agent_manager):
        """Test that agent stops when reaching max cycles."""
        manager = clean_agent_manager

        # Start agent with very short cycle count
        await manager.start_agent(mode="survival", max_cycles=3)

        # Wait for completion (3 cycles * 0.5s each = 1.5s minimum)
        await asyncio.sleep(2.5)

        # Agent should have stopped automatically
        status = await manager.get_status()
        assert status["is_running"] is False
        assert status["cycle_count"] == 3
