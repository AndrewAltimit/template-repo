"""Tests for state persistence."""

from datetime import datetime
import json
from pathlib import Path
import shutil
import tempfile

import pytest

from economic_agents.agent.core.state import AgentState
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet
from economic_agents.persistence import StateManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for persistence tests."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    # Cleanup after test
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def state_manager(temp_dir):
    """Create a state manager with temporary directory."""
    return StateManager(base_dir=temp_dir)


@pytest.fixture
def test_state():
    """Create a test agent state."""
    state = AgentState(balance=1000.0, compute_hours_remaining=10.0, survival_buffer_hours=2.0)
    state.tasks_completed = 5
    state.tasks_failed = 1
    state.cycles_completed = 3
    state.has_company = True
    state.company_id = "company-123"
    return state


@pytest.fixture
def test_decisions():
    """Create test decision records."""
    return [
        {
            "timestamp": datetime(2024, 1, 1, 12, 0, 0),
            "state": {"balance": 1000.0},
            "allocation": {
                "task_work_hours": 5.0,
                "company_work_hours": 0.0,
                "reasoning": "Test decision",
            },
        },
        {
            "timestamp": datetime(2024, 1, 1, 13, 0, 0),
            "state": {"balance": 1100.0},
            "allocation": {
                "task_work_hours": 3.0,
                "company_work_hours": 2.0,
                "reasoning": "Another decision",
            },
        },
    ]


def test_state_manager_initialization(_state_manager, temp_dir):
    """Test state manager creates required directories."""
    assert Path(temp_dir).exists()
    assert (Path(temp_dir) / "agents").exists()
    assert (Path(temp_dir) / "registry").exists()


def test_save_agent_state(state_manager, test_state, test_decisions):
    """Test saving agent state to disk."""
    agent_id = "test-agent-123"
    saved_path = state_manager.save_agent_state(agent_id, test_state, test_decisions)

    assert Path(saved_path).exists()
    assert saved_path.endswith(f"{agent_id}.json")

    # Verify file contents
    with open(saved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["agent_id"] == agent_id
    assert "state" in data
    assert "decisions" in data
    assert "saved_at" in data


def test_load_agent_state(state_manager, test_state, test_decisions):
    """Test loading agent state from disk."""
    agent_id = "test-agent-456"
    state_manager.save_agent_state(agent_id, test_state, test_decisions)

    loaded = state_manager.load_agent_state(agent_id)

    assert loaded["state"].balance == test_state.balance
    assert loaded["state"].compute_hours_remaining == test_state.compute_hours_remaining
    assert loaded["state"].tasks_completed == test_state.tasks_completed
    assert loaded["state"].has_company == test_state.has_company
    assert loaded["state"].company_id == test_state.company_id
    assert len(loaded["decisions"]) == 2


def test_load_nonexistent_agent_state(state_manager):
    """Test loading state for non-existent agent raises error."""
    with pytest.raises(FileNotFoundError):
        state_manager.load_agent_state("nonexistent-agent")


def test_save_and_load_preserves_timestamps(state_manager, test_state, test_decisions):
    """Test that timestamps are preserved through save/load cycle."""
    agent_id = "test-agent-timestamps"
    state_manager.save_agent_state(agent_id, test_state, test_decisions)

    loaded = state_manager.load_agent_state(agent_id)

    assert loaded["decisions"][0]["timestamp"] == test_decisions[0]["timestamp"]
    assert loaded["decisions"][1]["timestamp"] == test_decisions[1]["timestamp"]


def test_list_saved_agents(state_manager, test_state, test_decisions):
    """Test listing all saved agent IDs."""
    # Save multiple agents
    state_manager.save_agent_state("agent-1", test_state, test_decisions)
    state_manager.save_agent_state("agent-2", test_state, test_decisions)
    state_manager.save_agent_state("agent-3", test_state, test_decisions)

    saved_agents = state_manager.list_saved_agents()

    assert len(saved_agents) == 3
    assert "agent-1" in saved_agents
    assert "agent-2" in saved_agents
    assert "agent-3" in saved_agents


def test_registry_exists(state_manager):
    """Test checking if registry exists."""
    assert state_manager.registry_exists() is False

    # Create a registry
    from economic_agents.investment.company_registry import CompanyRegistry

    registry = CompanyRegistry()
    state_manager.save_registry(registry)

    assert state_manager.registry_exists() is True


def test_save_registry(state_manager):
    """Test saving company registry to disk."""
    from economic_agents.investment.company_registry import CompanyRegistry

    registry = CompanyRegistry()
    saved_path = state_manager.save_registry(registry)

    assert Path(saved_path).exists()
    assert saved_path.endswith("registry.json")

    # Verify file contents
    with open(saved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "companies" in data
    assert "proposals" in data
    assert "investments" in data
    assert "saved_at" in data


def test_load_registry(state_manager):
    """Test loading company registry from disk."""
    from economic_agents.investment.company_registry import CompanyRegistry

    registry = CompanyRegistry()
    state_manager.save_registry(registry)

    loaded_registry = state_manager.load_registry()

    assert isinstance(loaded_registry, CompanyRegistry)


def test_load_nonexistent_registry(state_manager):
    """Test loading non-existent registry raises error."""
    with pytest.raises(FileNotFoundError):
        state_manager.load_registry()


def test_overwrite_agent_state(state_manager, test_state, test_decisions):
    """Test that saving agent state overwrites existing file."""
    agent_id = "test-agent-overwrite"

    # Save first time
    state_manager.save_agent_state(agent_id, test_state, test_decisions)

    # Modify state
    test_state.balance = 2000.0
    test_state.tasks_completed = 10

    # Save again
    state_manager.save_agent_state(agent_id, test_state, test_decisions)

    # Load and verify
    loaded = state_manager.load_agent_state(agent_id)
    assert loaded["state"].balance == 2000.0
    assert loaded["state"].tasks_completed == 10


@pytest.mark.asyncio
async def test_autonomous_agent_save_state_integration():
    """Test AutonomousAgent save_state method."""
    from economic_agents.agent.core.autonomous_agent import AutonomousAgent

    temp_dir = tempfile.mkdtemp()
    try:
        state_manager = StateManager(base_dir=temp_dir)

        wallet = MockWallet(initial_balance=1000.0)
        compute = MockCompute(initial_hours=10.0)
        marketplace = MockMarketplace()

        agent = AutonomousAgent(wallet, compute, marketplace)
        await agent.initialize()

        # Save state
        saved_path = agent.save_state(state_manager)

        assert Path(saved_path).exists()

        # Verify we can load it back
        loaded = state_manager.load_agent_state(agent.agent_id)
        assert loaded["state"].balance == agent.state.balance
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_autonomous_agent_load_state_integration():
    """Test AutonomousAgent load_state class method."""
    from economic_agents.agent.core.autonomous_agent import AutonomousAgent

    temp_dir = tempfile.mkdtemp()
    try:
        state_manager = StateManager(base_dir=temp_dir)

        wallet = MockWallet(initial_balance=1000.0)
        compute = MockCompute(initial_hours=10.0)
        marketplace = MockMarketplace()

        # Create and save agent
        agent = AutonomousAgent(wallet, compute, marketplace)
        await agent.initialize()
        agent.state.tasks_completed = 5
        agent.save_state(state_manager)

        # Load agent
        loaded_agent = AutonomousAgent.load_state(
            agent_id=agent.agent_id, wallet=wallet, compute=compute, marketplace=marketplace, state_manager=state_manager
        )

        assert loaded_agent.agent_id == agent.agent_id
        assert loaded_agent.state.tasks_completed == 5
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
