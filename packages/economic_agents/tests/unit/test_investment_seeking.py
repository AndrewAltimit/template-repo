"""Tests for investment seeking integration in autonomous agent."""

import pytest
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.company.models import BusinessPlan, Company, CostStructure
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet
from economic_agents.investment import InvestmentStage


def create_test_business_plan(company_name="TestCorp") -> BusinessPlan:
    """Create a minimal business plan for testing."""
    return BusinessPlan(
        company_name=company_name,
        mission="Test mission",
        vision="Test vision",
        one_liner="Test one liner",
        problem_statement="Test problem",
        solution_description="Test solution",
        unique_value_proposition="Test UVP",
        target_market="developers",
        market_size=1000000.0,
        competition_analysis="Test competition",
        competitive_advantages=["advantage1"],
        product_description="Test product",
        features=["feature1", "feature2"],
        development_roadmap=[],
        revenue_streams=[],
        pricing_strategy="subscription",
        cost_structure=CostStructure(
            compute_costs=1000.0,
            sub_agent_costs=3000.0,
            infrastructure_costs=1000.0,
            other_costs=1000.0,
        ),
        funding_requested=100000.0,
        use_of_funds={"development": 50000.0, "marketing": 30000.0, "operations": 20000.0},
        revenue_projections=[10000.0, 50000.0, 150000.0],
        break_even_timeline="18 months",
        required_roles=["CEO", "CTO"],
        milestones=[],
    )


@pytest.fixture
def agent_with_company():
    """Create an autonomous agent with a company."""
    from datetime import datetime

    wallet = MockWallet(initial_balance=5000.0)
    compute = MockCompute(initial_hours=100.0)
    marketplace = MockMarketplace()

    agent = AutonomousAgent(wallet, compute, marketplace, config={"company_threshold": 1000.0})

    # Create business plan
    business_plan = create_test_business_plan("TestCorp")

    # Create company manually
    agent.company = Company(
        id="test-company",
        name="TestCorp",
        mission="Test mission",
        created_at=datetime.now(),
        capital=100.0,  # Low capital to trigger investment seeking
        founder_agent_id=agent.agent_id,
        business_plan=business_plan,
        stage="development",
        funding_status="bootstrapped",
    )
    agent.state.has_company = True
    agent.state.company_id = agent.company.id

    return agent


def test_should_seek_investment_no_company():
    """Test investment seeking returns False without company."""
    wallet = MockWallet(initial_balance=1000.0)
    compute = MockCompute(initial_hours=10.0)
    marketplace = MockMarketplace()
    agent = AutonomousAgent(wallet, compute, marketplace)

    assert agent._should_seek_investment() is False


def test_should_seek_investment_already_seeking():
    """Test investment seeking returns False if already seeking."""
    from datetime import datetime

    wallet = MockWallet(initial_balance=1000.0)
    compute = MockCompute(initial_hours=10.0)
    marketplace = MockMarketplace()
    agent = AutonomousAgent(wallet, compute, marketplace)

    agent.company = Company(
        id="test-company",
        name="TestCorp",
        mission="Test",
        created_at=datetime.now(),
        capital=50.0,
        founder_agent_id=agent.agent_id,
        stage="seeking_investment",
        funding_status="bootstrapped",
    )

    assert agent._should_seek_investment() is False


def test_should_seek_investment_capital_below_threshold(agent_with_company):
    """Test investment seeking triggered when capital below threshold."""
    # Company has 100.0 capital, threshold is 1000.0 * 0.3 = 300.0
    assert agent_with_company._should_seek_investment() is True


def test_should_seek_investment_capital_above_threshold():
    """Test investment seeking not triggered when capital sufficient."""
    from datetime import datetime

    wallet = MockWallet(initial_balance=5000.0)
    compute = MockCompute(initial_hours=100.0)
    marketplace = MockMarketplace()
    agent = AutonomousAgent(wallet, compute, marketplace, config={"company_threshold": 1000.0})

    agent.company = Company(
        id="test-company",
        name="TestCorp",
        mission="Test",
        created_at=datetime.now(),
        capital=500.0,  # Above 300.0 threshold
        founder_agent_id=agent.agent_id,
        stage="ideation",
        funding_status="bootstrapped",
    )
    agent.state.has_company = True

    assert agent._should_seek_investment() is False


def test_should_seek_investment_development_stage_with_products(agent_with_company):
    """Test investment seeking in development stage with products."""
    from economic_agents.company.models import Product, ProductSpec

    spec = ProductSpec(name="Product", description="Test", category="api", features=[], tech_stack=[])
    agent_with_company.company.products = [
        Product(
            spec=spec,
            status="active",
            completion_percentage=100,
            code_artifacts={},
            documentation="Test docs",
        )
    ]
    agent_with_company.company.stage = "development"
    agent_with_company.company.capital = 400.0  # Below 50% threshold (500.0)

    assert agent_with_company._should_seek_investment() is True


def test_seek_investment_no_company():
    """Test seeking investment without company returns error."""
    wallet = MockWallet(initial_balance=1000.0)
    compute = MockCompute(initial_hours=10.0)
    marketplace = MockMarketplace()
    agent = AutonomousAgent(wallet, compute, marketplace)

    result = agent._seek_investment()

    assert result["success"] is False
    assert "No company exists" in result["error"]


def test_seek_investment_creates_proposal(agent_with_company):
    """Test seeking investment creates proposal."""
    result = agent_with_company._seek_investment()

    assert result["success"] is True
    assert "proposal_id" in result
    assert "amount_requested" in result
    assert "valuation" in result
    assert "equity_offered" in result
    assert "stage" in result


def test_seek_investment_determines_seed_stage(agent_with_company):
    """Test investment seeking determines SEED stage for first funding."""
    agent_with_company.company.funding_rounds = []

    result = agent_with_company._seek_investment()

    assert result["stage"] == InvestmentStage.SEED.value


def test_seek_investment_determines_series_a_stage(agent_with_company):
    """Test investment seeking determines SERIES_A for second funding."""
    # Mock one previous funding round
    agent_with_company.company.funding_rounds = [{"stage": "seed", "amount": 100000}]

    result = agent_with_company._seek_investment()

    assert result["stage"] == InvestmentStage.SERIES_A.value


def test_seek_investment_determines_series_b_stage(agent_with_company):
    """Test investment seeking determines SERIES_B for third+ funding."""
    # Mock two previous funding rounds
    agent_with_company.company.funding_rounds = [
        {"stage": "seed", "amount": 100000},
        {"stage": "series_a", "amount": 500000},
    ]

    result = agent_with_company._seek_investment()

    assert result["stage"] == InvestmentStage.SERIES_B.value


def test_seek_investment_updates_company_stage(agent_with_company):
    """Test seeking investment updates company stage."""
    initial_stage = agent_with_company.company.stage

    agent_with_company._seek_investment()

    assert agent_with_company.company.stage == "seeking_investment"
    assert initial_stage != "seeking_investment"


def test_seek_investment_logs_decision(agent_with_company):
    """Test seeking investment logs decision."""
    initial_log_count = len(agent_with_company.decision_logger.decisions)

    agent_with_company._seek_investment()

    assert len(agent_with_company.decision_logger.decisions) > initial_log_count

    # Check last logged decision
    last_decision = agent_with_company.decision_logger.decisions[-1]
    assert last_decision.decision_type == "seek_investment"
    assert "proposal_id" in last_decision.context
    assert "amount_requested" in last_decision.context


def test_run_cycle_checks_investment_seeking(agent_with_company):
    """Test run cycle checks for investment seeking."""
    from economic_agents.company.models import Product, ProductSpec

    # Give company a product so it doesn't try to develop one during cycle
    spec = ProductSpec(name="Product", description="Test", category="api", features=[], tech_stack=[])
    agent_with_company.company.products = [
        Product(
            spec=spec,
            status="active",
            completion_percentage=100,
            code_artifacts={},
            documentation="Test docs",
        )
    ]

    # Add enough team members so it doesn't try to hire (limit is 5)
    # Company already has some initial team members, add more to reach 5+
    for i in range(5):
        agent_with_company.company.add_sub_agent(f"emp-{i}", "employee")

    # Capital is 100.0 which is below threshold (300.0)
    # Investment seeking should be checked before company work
    result = agent_with_company.run_cycle()

    # Investment seeking should have been triggered since capital < 300.0 threshold
    assert "investment_seeking" in result
    assert result["investment_seeking"]["success"] is True


def test_run_cycle_skips_investment_when_not_needed():
    """Test run cycle skips investment when not needed."""
    from datetime import datetime

    wallet = MockWallet(initial_balance=50000.0)
    compute = MockCompute(initial_hours=100.0)
    marketplace = MockMarketplace()
    agent = AutonomousAgent(wallet, compute, marketplace, config={"company_threshold": 1000.0})

    business_plan = create_test_business_plan("TestCorp")

    agent.company = Company(
        id="test-company",
        name="TestCorp",
        mission="Test",
        created_at=datetime.now(),
        capital=50000.0,  # High capital, no investment needed
        founder_agent_id=agent.agent_id,
        business_plan=business_plan,
        stage="development",
        funding_status="bootstrapped",
    )
    agent.state.has_company = True
    agent.state.company_id = agent.company.id

    result = agent.run_cycle()

    assert "investment_seeking" not in result


def test_investment_seeking_context_includes_capital():
    """Test investment seeking decision context includes capital info."""
    from datetime import datetime

    wallet = MockWallet(initial_balance=5000.0)
    compute = MockCompute(initial_hours=100.0)
    marketplace = MockMarketplace()
    agent = AutonomousAgent(wallet, compute, marketplace)

    business_plan = create_test_business_plan("TestCorp")

    agent.company = Company(
        id="test-company",
        name="TestCorp",
        mission="Test",
        created_at=datetime.now(),
        capital=50.0,
        founder_agent_id=agent.agent_id,
        business_plan=business_plan,
        stage="development",
        funding_status="bootstrapped",
    )
    agent.state.has_company = True

    agent._seek_investment()

    last_decision = agent.decision_logger.decisions[-1]
    assert "current_capital" in last_decision.context
    assert last_decision.context["current_capital"] == 50.0
