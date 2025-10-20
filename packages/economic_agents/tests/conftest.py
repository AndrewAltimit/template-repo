"""Pytest fixtures for economic agents tests (P1 #8)."""

from datetime import datetime

import pytest
from economic_agents.company.models import Company, ProductSpec
from economic_agents.investment.models import (
    InvestmentCriteria,
    InvestmentProposal,
    InvestmentStage,
    InvestorProfile,
    InvestorType,
)
from economic_agents.sub_agents.board_member import BoardMember
from economic_agents.sub_agents.executive import Executive
from economic_agents.sub_agents.individual_contributor import IndividualContributor
from economic_agents.sub_agents.subject_matter_expert import SubjectMatterExpert
from economic_agents.time.simulation import SimulationClock, TimeTracker

# Company Fixtures


@pytest.fixture
def standard_company():
    """Create a standard company for testing.

    Returns:
        Company with typical startup configuration
    """
    return Company(
        id="test-company-1",
        name="Test Startup",
        mission="Build innovative AI products",
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        capital=100000.0,
        founder_agent_id="founder-1",
        stage="development",
        funding_status="bootstrapped",
    )


@pytest.fixture
def seed_stage_company():
    """Create a seed-stage company seeking investment.

    Returns:
        Company in seed stage with lower capital
    """
    return Company(
        id="test-company-2",
        name="Seed Startup",
        mission="Seeking seed funding",
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        capital=25000.0,
        founder_agent_id="founder-2",
        stage="seeking_investment",
        funding_status="seeking_seed",
    )


@pytest.fixture
def operational_company():
    """Create an operational company with products and team.

    Returns:
        Company in operational stage
    """
    company = Company(
        id="test-company-3",
        name="Operational Corp",
        mission="Scaling successful product",
        created_at=datetime(2023, 1, 1, 0, 0, 0),
        capital=500000.0,
        founder_agent_id="founder-3",
        stage="operational",
        funding_status="funded",
    )
    # Add some team members
    company.add_sub_agent("board-1", "board")
    company.add_sub_agent("exec-1", "executive")
    company.add_sub_agent("ic-1", "employee")
    company.add_sub_agent("ic-2", "employee")
    return company


# Investor Fixtures


@pytest.fixture
def angel_investor():
    """Create a standard angel investor.

    Returns:
        InvestorProfile for angel investor
    """
    return InvestorProfile(
        id="investor-1",
        name="Angel Investor",
        type=InvestorType.ANGEL,
        available_capital=500000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=InvestmentCriteria(
            min_market_size=5000000.0,
            min_revenue_projection=100000.0,
            max_burn_rate=20000.0,
            required_team_size=2,
            preferred_stages=[InvestmentStage.PRE_SEED, InvestmentStage.SEED],
            preferred_markets=["technology", "ai"],
            risk_tolerance=0.7,
            min_roi_expectation=3.0,
        ),
    )


@pytest.fixture
def vc_investor():
    """Create a venture capital investor.

    Returns:
        InvestorProfile for VC investor
    """
    return InvestorProfile(
        id="investor-2",
        name="VC Fund",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=10000000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=InvestmentCriteria(
            min_market_size=50000000.0,
            min_revenue_projection=500000.0,
            max_burn_rate=100000.0,
            required_team_size=5,
            preferred_stages=[InvestmentStage.SERIES_A, InvestmentStage.SERIES_B],
            preferred_markets=["technology", "saas", "ai"],
            risk_tolerance=0.5,
            min_roi_expectation=5.0,
        ),
    )


@pytest.fixture
def conservative_investor():
    """Create a conservative investor with low risk tolerance.

    Returns:
        InvestorProfile for conservative investor
    """
    return InvestorProfile(
        id="investor-3",
        name="Conservative Fund",
        type=InvestorType.CORPORATE,
        available_capital=2000000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=InvestmentCriteria(
            min_market_size=20000000.0,
            min_revenue_projection=1000000.0,
            max_burn_rate=30000.0,
            required_team_size=10,
            preferred_stages=[InvestmentStage.SERIES_B, InvestmentStage.SERIES_C],
            preferred_markets=["enterprise", "saas"],
            risk_tolerance=0.2,
            min_roi_expectation=3.0,
        ),
    )


# Investment Proposal Fixtures


@pytest.fixture
def strong_proposal():
    """Create a strong investment proposal.

    Returns:
        InvestmentProposal with attractive metrics
    """
    return InvestmentProposal(
        id="proposal-1",
        company_id="company-1",
        company_name="Strong Startup",
        amount_requested=500000.0,
        equity_offered=15.0,
        valuation=3000000.0,
        stage=InvestmentStage.SEED,
        use_of_funds={"product": 250000.0, "marketing": 150000.0, "operations": 100000.0},
        revenue_projections=[500000.0, 1500000.0, 3000000.0],
        market_size=100000000.0,
        team_size=8,
        competitive_advantages=["Proprietary technology", "Strong team", "Market leader", "Network effects"],
        risks=["Market competition"],
        milestones=[
            {"title": "Product launch", "month": 3},
            {"title": "1000 customers", "month": 6},
            {"title": "Break-even", "month": 12},
        ],
    )


@pytest.fixture
def weak_proposal():
    """Create a weak investment proposal.

    Returns:
        InvestmentProposal with poor metrics
    """
    return InvestmentProposal(
        id="proposal-2",
        company_id="company-2",
        company_name="Weak Startup",
        amount_requested=200000.0,
        equity_offered=25.0,
        valuation=800000.0,
        stage=InvestmentStage.SEED,
        use_of_funds={"product": 100000.0, "operations": 100000.0},
        revenue_projections=[50000.0, 100000.0, 200000.0],
        market_size=5000000.0,
        team_size=2,
        competitive_advantages=["First mover"],
        risks=["Market uncertainty", "Technical challenges", "Small team", "Competition"],
        milestones=[],
    )


# Product Spec Fixtures


@pytest.fixture
def api_product_spec():
    """Create API service product specification.

    Returns:
        ProductSpec for API service
    """
    return ProductSpec(
        name="AI Data API",
        description="RESTful API for AI-powered data processing",
        category="api-service",
        features=["Real-time processing", "Batch operations", "Webhooks", "Analytics dashboard"],
        tech_stack=["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
    )


@pytest.fixture
def saas_product_spec():
    """Create SaaS platform product specification.

    Returns:
        ProductSpec for SaaS product
    """
    return ProductSpec(
        name="Enterprise Analytics Platform",
        description="Comprehensive analytics solution for enterprises",
        category="saas",
        features=[
            "Custom dashboards",
            "Real-time analytics",
            "User management",
            "API access",
            "Export functionality",
            "Alerts & notifications",
        ],
        tech_stack=["React", "TypeScript", "Node.js", "PostgreSQL", "Redis", "AWS"],
    )


@pytest.fixture
def cli_product_spec():
    """Create CLI tool product specification.

    Returns:
        ProductSpec for CLI tool
    """
    return ProductSpec(
        name="DevOps CLI Tool",
        description="Command-line tool for DevOps automation",
        category="cli-tool",
        features=["Deploy automation", "Log analysis", "Config management"],
        tech_stack=["Python", "Click", "Docker"],
    )


# Sub-Agent Fixtures


@pytest.fixture
def board_member_finance():
    """Create a finance-focused board member.

    Returns:
        BoardMember specialized in finance
    """
    return BoardMember(agent_id="board-1", specialization="finance")


@pytest.fixture
def board_member_governance():
    """Create a governance-focused board member.

    Returns:
        BoardMember specialized in governance
    """
    return BoardMember(agent_id="board-2", specialization="governance")


@pytest.fixture
def ceo():
    """Create a CEO executive.

    Returns:
        Executive with CEO role
    """
    return Executive(agent_id="exec-1", role_title="CEO", specialization="leadership")


@pytest.fixture
def cto():
    """Create a CTO executive.

    Returns:
        Executive with CTO role
    """
    return Executive(agent_id="exec-2", role_title="CTO", specialization="technology")


@pytest.fixture
def cfo():
    """Create a CFO executive.

    Returns:
        Executive with CFO role
    """
    return Executive(agent_id="exec-3", role_title="CFO", specialization="finance")


@pytest.fixture
def backend_developer():
    """Create a backend developer IC.

    Returns:
        IndividualContributor specialized in backend
    """
    return IndividualContributor(agent_id="ic-1", specialization="backend-dev")


@pytest.fixture
def frontend_developer():
    """Create a frontend developer IC.

    Returns:
        IndividualContributor specialized in frontend
    """
    return IndividualContributor(agent_id="ic-2", specialization="frontend-dev")


@pytest.fixture
def qa_engineer():
    """Create a QA engineer IC.

    Returns:
        IndividualContributor specialized in QA
    """
    return IndividualContributor(agent_id="ic-3", specialization="qa")


@pytest.fixture
def sme_security():
    """Create a security SME.

    Returns:
        SubjectMatterExpert specialized in security
    """
    return SubjectMatterExpert(agent_id="sme-1", specialization="security")


@pytest.fixture
def sme_scaling():
    """Create a scaling SME.

    Returns:
        SubjectMatterExpert specialized in scaling
    """
    return SubjectMatterExpert(agent_id="sme-2", specialization="scaling")


@pytest.fixture
def sme_ml():
    """Create a machine learning SME.

    Returns:
        SubjectMatterExpert specialized in ML
    """
    return SubjectMatterExpert(agent_id="sme-3", specialization="machine-learning")


# Time Simulation Fixtures


@pytest.fixture
def simulation_clock():
    """Create a standard simulation clock.

    Returns:
        SimulationClock with 24 hours per cycle
    """
    return SimulationClock(hours_per_cycle=24.0, start_date=datetime(2024, 1, 1, 0, 0, 0))


@pytest.fixture
def monthly_clock():
    """Create a simulation clock with monthly cycles.

    Returns:
        SimulationClock with 730 hours per cycle (1 month)
    """
    return SimulationClock(hours_per_cycle=730.0, start_date=datetime(2024, 1, 1, 0, 0, 0))


@pytest.fixture
def time_tracker(simulation_clock):
    """Create a time tracker with standard clock.

    Args:
        simulation_clock: Fixture providing simulation clock

    Returns:
        TimeTracker instance
    """
    return TimeTracker(clock=simulation_clock)


@pytest.fixture
def monthly_time_tracker(monthly_clock):
    """Create a time tracker with monthly clock.

    Args:
        monthly_clock: Fixture providing monthly clock

    Returns:
        TimeTracker instance
    """
    return TimeTracker(clock=monthly_clock)


# Factory Fixtures


@pytest.fixture
def company_factory():
    """Factory for creating companies with custom parameters.

    Returns:
        Callable that creates Company instances
    """

    def _create_company(
        company_id="test-company",
        name="Test Company",
        capital=100000.0,
        stage="development",
        funding_status="bootstrapped",
    ):
        return Company(
            id=company_id,
            name=name,
            mission=f"Mission for {name}",
            created_at=datetime.now(),
            capital=capital,
            founder_agent_id="founder-test",
            stage=stage,
            funding_status=funding_status,
        )

    return _create_company


@pytest.fixture
def product_spec_factory():
    """Factory for creating product specs with custom parameters.

    Returns:
        Callable that creates ProductSpec instances
    """

    def _create_product_spec(name="Test Product", category="api-service", feature_count=3):
        features = [f"Feature {i+1}" for i in range(feature_count)]
        tech_stack = ["Python", "FastAPI", "PostgreSQL"]

        return ProductSpec(
            name=name, description=f"Description for {name}", category=category, features=features, tech_stack=tech_stack
        )

    return _create_product_spec


@pytest.fixture
def sub_agent_factory():
    """Factory for creating sub-agents of various types.

    Returns:
        Callable that creates sub-agent instances
    """

    def _create_sub_agent(agent_type, agent_id="test-agent", **kwargs):
        if agent_type == "board":
            return BoardMember(agent_id=agent_id, specialization=kwargs.get("specialization", "finance"))
        elif agent_type == "executive":
            return Executive(
                agent_id=agent_id,
                role_title=kwargs.get("role_title", "CEO"),
                specialization=kwargs.get("specialization", "leadership"),
            )
        elif agent_type == "ic":
            return IndividualContributor(agent_id=agent_id, specialization=kwargs.get("specialization", "backend-dev"))
        elif agent_type == "sme":
            return SubjectMatterExpert(agent_id=agent_id, specialization=kwargs.get("specialization", "security"))
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

    return _create_sub_agent


# Temp Directory Fixtures for File I/O


@pytest.fixture
def temp_log_dirs(tmp_path):
    """Provide temporary directories for agent logging.

    Creates temp directories for resource tracker, metrics collector,
    and alignment monitor to avoid permission errors in tests.

    Args:
        tmp_path: pytest's built-in temp directory fixture

    Returns:
        Dict with log directory paths
    """
    log_dirs = {
        "resources": tmp_path / "resources",
        "metrics": tmp_path / "metrics",
        "alignment": tmp_path / "alignment",
        "reports": tmp_path / "reports",
    }

    # Create directories
    for directory in log_dirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    return log_dirs


@pytest.fixture(autouse=True)
def mock_file_operations(monkeypatch, tmp_path):
    """Automatically mock file I/O operations to use temp directories.

    This fixture is autouse=True, so it applies to all tests automatically.
    It prevents permission errors by mocking the _save_* methods in
    ResourceTracker, MetricsCollector, and AlignmentMonitor.

    Args:
        monkeypatch: pytest's monkeypatch fixture
        tmp_path: pytest's tmp_path fixture
    """
    # Mock ResourceTracker file operations
    monkeypatch.setattr(
        "economic_agents.monitoring.resource_tracker.ResourceTracker._save_transaction", lambda self, transaction: None
    )
    monkeypatch.setattr(
        "economic_agents.monitoring.resource_tracker.ResourceTracker._save_compute_usage", lambda self, usage: None
    )
    monkeypatch.setattr(
        "economic_agents.monitoring.resource_tracker.ResourceTracker._save_time_allocation", lambda self, allocation: None
    )

    # Mock MetricsCollector file operations
    monkeypatch.setattr(
        "economic_agents.monitoring.metrics_collector.MetricsCollector._save_performance_snapshot", lambda self, snapshot: None
    )

    # Mock AlignmentMonitor file operations
    monkeypatch.setattr(
        "economic_agents.monitoring.alignment_monitor.AlignmentMonitor._save_alignment_score", lambda self, score: None
    )
    monkeypatch.setattr(
        "economic_agents.monitoring.alignment_monitor.AlignmentMonitor._save_anomaly", lambda self, anomaly: None
    )
    monkeypatch.setattr(
        "economic_agents.monitoring.alignment_monitor.AlignmentMonitor._save_goal_progress", lambda self, progress: None
    )

    # Mock StateManager file operations (if it exists and has _save_state method)
    try:
        monkeypatch.setattr("economic_agents.persistence.state_manager.StateManager._save_state", lambda self, state: None)
    except AttributeError:
        pass  # Method doesn't exist, skip
