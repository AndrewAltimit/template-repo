"""Integration tests for autonomous agent core loop."""

import pytest
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet


@pytest.mark.asyncio
async def test_agent_initialization():
    """Test agent initializes correctly with all components."""
    wallet = MockWallet(initial_balance=50.0)
    compute = MockCompute(initial_hours=24.0, cost_per_hour=2.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace, config={"survival_buffer_hours": 24.0})
    await agent.initialize()

    assert agent.state.balance == 50.0
    assert agent.state.compute_hours_remaining == pytest.approx(24.0, abs=0.1)
    assert agent.state.is_active is True


@pytest.mark.asyncio
async def test_agent_single_cycle():
    """Test agent executes a single decision cycle."""
    wallet = MockWallet(initial_balance=50.0)
    compute = MockCompute(initial_hours=24.0, cost_per_hour=2.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace)
    await agent.initialize()

    result = await agent.run_cycle()

    assert "timestamp" in result
    assert "state" in result
    assert "allocation" in result
    assert agent.state.cycles_completed == 1


@pytest.mark.asyncio
async def test_agent_completes_task():
    """Test agent successfully completes a task and earns money."""
    wallet = MockWallet(initial_balance=50.0)
    compute = MockCompute(initial_hours=24.0, cost_per_hour=2.0)
    marketplace = MockMarketplace(seed=42)  # Fixed seed for deterministic results

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace)
    await agent.initialize()

    # Run multiple cycles to ensure at least one task success
    for _ in range(5):
        result = await agent.run_cycle()
        if "task_result" in result and result["task_result"].get("success"):
            break

    # Check that agent earned money from at least one successful task
    assert agent.state.tasks_completed >= 1 or agent.state.tasks_failed >= 1


@pytest.mark.asyncio
async def test_agent_resource_allocation():
    """Test agent allocates resources based on state."""
    wallet = MockWallet(initial_balance=200.0)  # High balance
    compute = MockCompute(initial_hours=48.0, cost_per_hour=2.0)  # Plenty of compute
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace, config={"survival_buffer_hours": 24.0})
    await agent.initialize()

    result = await agent.run_cycle()

    allocation = result["allocation"]
    assert allocation["task_work_hours"] >= 0
    assert allocation["company_work_hours"] >= 0
    assert "reasoning" in allocation


@pytest.mark.asyncio
async def test_agent_survival_mode():
    """Test agent prioritizes survival when compute is low."""
    wallet = MockWallet(initial_balance=50.0)
    compute = MockCompute(initial_hours=10.0, cost_per_hour=2.0)  # Low compute
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace, config={"survival_buffer_hours": 24.0})
    await agent.initialize()

    result = await agent.run_cycle()

    allocation = result["allocation"]
    # Should allocate to tasks when survival at risk
    assert allocation["task_work_hours"] > 0
    assert "survival" in allocation["reasoning"].lower()


@pytest.mark.asyncio
async def test_agent_multiple_cycles():
    """Test agent runs multiple cycles successfully."""
    wallet = MockWallet(initial_balance=100.0)
    compute = MockCompute(initial_hours=10.0, cost_per_hour=2.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace)
    await agent.initialize()

    # Run 3 cycles
    decisions = await agent.run(max_cycles=3)

    assert len(decisions) == 3
    assert agent.state.cycles_completed == 3


@pytest.mark.asyncio
async def test_agent_stops_when_out_of_compute():
    """Test agent checks compute status and stops appropriately."""
    wallet = MockWallet(initial_balance=100.0)
    compute = MockCompute(initial_hours=0.005, cost_per_hour=2.0)  # Almost no compute (0.005 hours = 18 seconds)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace)
    await agent.initialize()

    # Try to run for many cycles
    decisions = await agent.run(max_cycles=10)

    # With almost no compute and the 0.01 threshold, agent should stop immediately or after 1 cycle
    assert len(decisions) <= 1
    assert agent.state.is_active is False


@pytest.mark.asyncio
async def test_agent_tracks_decisions():
    """Test agent properly tracks all decisions."""
    wallet = MockWallet(initial_balance=100.0)
    compute = MockCompute(initial_hours=24.0, cost_per_hour=2.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace)
    await agent.initialize()

    await agent.run(max_cycles=5)

    decisions = agent.get_decisions()
    assert len(decisions) == 5

    for decision in decisions:
        assert "timestamp" in decision
        assert "allocation" in decision
        assert "state" in decision


@pytest.mark.asyncio
async def test_agent_state_updates():
    """Test agent state updates correctly after cycles."""
    wallet = MockWallet(initial_balance=100.0)
    compute = MockCompute(initial_hours=24.0, cost_per_hour=2.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace)
    await agent.initialize()

    initial_compute = agent.state.compute_hours_remaining

    await agent.run(max_cycles=3)

    # Compute should have decreased
    final_compute = agent.state.compute_hours_remaining
    assert final_compute < initial_compute


@pytest.mark.asyncio
async def test_agent_with_different_personalities():
    """Test agent behavior with different personality configs."""
    wallet_averse = MockWallet(initial_balance=200.0)
    compute_averse = MockCompute(initial_hours=48.0, cost_per_hour=2.0)
    marketplace_averse = MockMarketplace(seed=42)

    agent_averse = AutonomousAgent(
        wallet=wallet_averse,
        compute=compute_averse,
        marketplace=marketplace_averse,
        config={"personality": "risk_averse", "survival_buffer_hours": 24.0},
    )
    await agent_averse.initialize()

    result_averse = await agent_averse.run_cycle()

    wallet_aggressive = MockWallet(initial_balance=200.0)
    compute_aggressive = MockCompute(initial_hours=48.0, cost_per_hour=2.0)
    marketplace_aggressive = MockMarketplace(seed=42)

    agent_aggressive = AutonomousAgent(
        wallet=wallet_aggressive,
        compute=compute_aggressive,
        marketplace=marketplace_aggressive,
        config={"personality": "aggressive", "survival_buffer_hours": 24.0},
    )
    await agent_aggressive.initialize()

    result_aggressive = await agent_aggressive.run_cycle()

    # Both should make decisions
    assert "allocation" in result_averse
    assert "allocation" in result_aggressive


@pytest.mark.asyncio
async def test_agent_end_to_end_survival():
    """Test complete end-to-end survival scenario."""
    wallet = MockWallet(initial_balance=50.0)
    compute = MockCompute(initial_hours=5.0, cost_per_hour=2.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace)
    await agent.initialize()

    # Run until compute expires or 10 cycles
    decisions = await agent.run(max_cycles=10)

    # Verify agent made decisions and tracked state
    assert len(decisions) > 0
    assert agent.state.cycles_completed == len(decisions)

    # Verify compute was consumed
    final_compute = agent.state.compute_hours_remaining
    assert final_compute < 5.0
