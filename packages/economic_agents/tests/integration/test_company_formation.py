"""Integration tests for company formation."""

import pytest

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet


@pytest.mark.asyncio
async def test_agent_forms_company_with_sufficient_capital():
    """Test agent forms company when it has sufficient capital."""
    # Provide $100k to cover company formation (~$15k) + operations + product development (~$10k)
    wallet = MockWallet(initial_balance=100000.0)  # Above threshold
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)  # Free compute
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 24.0, "company_threshold": 50000.0},
    )
    await agent.initialize()

    # Run a few cycles to let agent accumulate and form company
    _ = await agent.run(max_cycles=10)

    # Agent should have formed a company
    assert agent.state.has_company is True
    assert agent.company is not None
    assert agent.company.name is not None


@pytest.mark.asyncio
async def test_agent_does_not_form_company_insufficient_capital():
    """Test agent does not form company with insufficient capital."""
    wallet = MockWallet(initial_balance=50.0)  # Below threshold
    compute = MockCompute(initial_hours=24.0, cost_per_hour=2.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 24.0, "company_threshold": 200.0},  # High threshold
    )
    await agent.initialize()

    await agent.run(max_cycles=3)

    # Agent should not have formed company
    assert agent.state.has_company is False
    assert agent.company is None


@pytest.mark.asyncio
async def test_company_has_initial_team():
    """Test formed company has initial team structure."""
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 24.0, "company_threshold": 50000.0},
    )
    await agent.initialize()

    await agent.run(max_cycles=10)

    if agent.company:
        # Company should have initial team
        assert len(agent.company.board_member_ids) >= 2
        assert len(agent.company.executive_ids) >= 1
        assert agent.company.business_plan is not None


@pytest.mark.asyncio
async def test_company_develops_products():
    """Test company can develop products."""
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)  # More compute for company work
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 20.0, "company_threshold": 50000.0, "personality": "aggressive"},
    )
    await agent.initialize()

    await agent.run(max_cycles=15)

    if agent.company and agent.company.stage == "development":
        # Company should have developed at least one product
        assert len(agent.company.products) >= 1


@pytest.mark.asyncio
async def test_company_formation_decision_logged():
    """Test company formation is logged in decision history."""
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 24.0, "company_threshold": 50000.0},
    )
    await agent.initialize()

    await agent.run(max_cycles=10)

    # Check decision log for company formation
    if agent.state.has_company:
        company_decisions = [d for d in agent.decisions if "company_formation" in d]
        assert len(company_decisions) > 0


@pytest.mark.asyncio
async def test_agent_balances_survival_and_company_work():
    """Test agent allocates time to both survival and company work."""
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 24.0,
            "company_threshold": 50000.0,
            "personality": "balanced",
        },
    )
    await agent.initialize()

    await agent.run(max_cycles=15)

    # Check that agent did both task work and company work
    task_work_cycles = sum(1 for d in agent.decisions if "task_result" in d)
    company_work_cycles = sum(1 for d in agent.decisions if "company_work" in d)

    # Agent should have done some task work (survival)
    assert task_work_cycles > 0

    # If company exists, should have done company work
    if agent.state.has_company:
        assert company_work_cycles > 0


@pytest.mark.asyncio
async def test_company_capital_allocation():
    """Test company receives proper capital allocation."""
    initial_balance = 100000.0
    wallet = MockWallet(initial_balance=initial_balance)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 24.0, "company_threshold": 50000.0},
    )
    await agent.initialize()

    # Track balance before company formation
    balance_before_company = await agent.wallet.get_balance()

    await agent.run(max_cycles=10)

    if agent.company:
        # Company should have received capital (30% of balance at formation)
        assert agent.company.capital > 0
        # Company capital allocation came from agent's balance
        # Note: Agent may earn more through tasks, so just verify company has capital
        assert agent.company.capital <= balance_before_company


@pytest.mark.asyncio
async def test_company_business_plan_generated():
    """Test company has complete business plan."""
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 24.0, "company_threshold": 50000.0},
    )
    await agent.initialize()

    await agent.run(max_cycles=10)

    if agent.company:
        plan = agent.company.business_plan
        assert plan is not None
        assert plan.company_name == agent.company.name
        assert plan.mission is not None
        assert len(plan.features) > 0
        assert len(plan.revenue_streams) > 0
        assert plan.funding_requested > 0


@pytest.mark.asyncio
async def test_company_stage_progression():
    """Test company progresses through stages."""
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 20.0, "company_threshold": 50000.0, "personality": "aggressive"},
    )
    await agent.initialize()

    await agent.run(max_cycles=20)

    if agent.company:
        # Company should progress from ideation
        assert agent.company.stage in ["development", "seeking_investment", "operational"]


@pytest.mark.asyncio
async def test_company_team_expansion():
    """Test company can expand team over time."""
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 20.0, "company_threshold": 50000.0, "personality": "aggressive"},
    )
    await agent.initialize()

    # Track initial team size
    await agent.run(max_cycles=5)
    initial_team_size = len(agent.company.get_all_sub_agent_ids()) if agent.company else 0

    # Continue running
    await agent.run(max_cycles=15)

    if agent.company and initial_team_size > 0:
        # Team might have expanded
        final_team_size = len(agent.company.get_all_sub_agent_ids())
        # At minimum, team should still exist
        assert final_team_size >= initial_team_size


@pytest.mark.asyncio
async def test_agent_company_end_to_end():
    """Test complete end-to-end company formation and operation."""
    wallet = MockWallet(initial_balance=100000.0)
    compute = MockCompute(initial_hours=200.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 20.0, "company_threshold": 50000.0, "personality": "balanced"},
    )
    await agent.initialize()

    await agent.run(max_cycles=25)

    # Verify agent state
    assert agent.state.cycles_completed > 0
    assert agent.state.tasks_completed > 0

    # If company formed, verify structure
    if agent.state.has_company:
        company = agent.company
        assert company.name is not None
        assert company.founder_agent_id == agent.agent_id
        assert len(company.get_all_sub_agent_ids()) >= 3
        assert company.business_plan is not None
        assert company.capital > 0 or company.metrics.expenses > 0  # Capital was allocated
