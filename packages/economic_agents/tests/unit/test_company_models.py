"""Tests for company data models."""

from datetime import datetime

from economic_agents.company.models import (
    BusinessPlan,
    Company,
    CompanyMetrics,
    CostStructure,
    Milestone,
    Product,
    ProductSpec,
    RevenueStream,
)


def test_milestone_creation():
    """Test milestone creation."""
    milestone = Milestone(
        title="MVP Launch",
        description="Launch minimum viable product",
        target_date="2024-12-01",
        completed=False,
    )

    assert milestone.title == "MVP Launch"
    assert milestone.completed is False


def test_revenue_stream_creation():
    """Test revenue stream creation."""
    stream = RevenueStream(
        name="Subscriptions",
        description="Monthly recurring revenue",
        projected_annual=100000.0,
    )

    assert stream.name == "Subscriptions"
    assert stream.projected_annual == 100000.0


def test_cost_structure():
    """Test cost structure with total calculation."""
    costs = CostStructure(
        compute_costs=10000.0,
        sub_agent_costs=20000.0,
        infrastructure_costs=5000.0,
        other_costs=3000.0,
    )

    assert costs.total_annual == 38000.0


def test_product_spec_creation():
    """Test product specification creation."""
    spec = ProductSpec(
        name="Data API",
        description="API for data processing",
        category="api-service",
        features=["Validation", "Transformation"],
        tech_stack=["Python", "FastAPI"],
    )

    assert spec.name == "Data API"
    assert spec.category == "api-service"
    assert len(spec.features) == 2


def test_product_creation():
    """Test product creation."""
    spec = ProductSpec(
        name="CLI Tool",
        description="Development CLI",
        category="cli-tool",
        features=["Scaffolding"],
        tech_stack=["Python"],
    )

    product = Product(
        spec=spec,
        status="alpha",
        completion_percentage=60.0,
        code_artifacts={"cli.py": "Main CLI"},
        documentation="# CLI Documentation",
    )

    assert product.status == "alpha"
    assert product.completion_percentage == 60.0


def test_company_metrics():
    """Test company metrics calculations."""
    metrics = CompanyMetrics(
        revenue=50000.0,
        expenses=30000.0,
        burn_rate_per_hour=10.0,
    )

    assert metrics.profit == 20000.0
    assert metrics.runway_hours == 2000.0


def test_company_metrics_no_burn():
    """Test company metrics with no burn rate."""
    metrics = CompanyMetrics(revenue=50000.0, expenses=0.0, burn_rate_per_hour=0.0)

    assert metrics.runway_hours == float("inf")


def test_company_metrics_negative_runway():
    """Test company metrics with negative available funds."""
    metrics = CompanyMetrics(revenue=10000.0, expenses=15000.0, burn_rate_per_hour=10.0)

    assert metrics.profit == -5000.0
    assert metrics.runway_hours == 0.0


def test_company_creation():
    """Test company creation."""
    company = Company(
        id="company_123",
        name="TestCo",
        mission="Build great products",
        created_at=datetime.now(),
        capital=100000.0,
        founder_agent_id="agent_1",
    )

    assert company.name == "TestCo"
    assert company.capital == 100000.0
    assert company.stage == "ideation"
    assert company.funding_status == "bootstrapped"


def test_company_add_sub_agent():
    """Test adding sub-agents to company."""
    company = Company(
        id="company_123",
        name="TestCo",
        mission="Build products",
        created_at=datetime.now(),
        capital=100000.0,
        founder_agent_id="agent_1",
    )

    company.add_sub_agent("board_1", "board")
    company.add_sub_agent("exec_1", "executive")
    company.add_sub_agent("emp_1", "employee")

    assert len(company.board_member_ids) == 1
    assert len(company.executive_ids) == 1
    assert len(company.employee_ids) == 1
    assert company.metrics.sub_agents_created == 3


def test_company_get_all_sub_agents():
    """Test getting all sub-agent IDs."""
    company = Company(
        id="company_123",
        name="TestCo",
        mission="Build products",
        created_at=datetime.now(),
        capital=100000.0,
        founder_agent_id="agent_1",
    )

    company.add_sub_agent("board_1", "board")
    company.add_sub_agent("exec_1", "executive")
    company.add_sub_agent("emp_1", "employee")

    all_agents = company.get_all_sub_agent_ids()
    assert len(all_agents) == 3
    assert "board_1" in all_agents
    assert "exec_1" in all_agents
    assert "emp_1" in all_agents


def test_company_to_dict():
    """Test company serialization."""
    company = Company(
        id="company_123",
        name="TestCo",
        mission="Build products",
        created_at=datetime.now(),
        capital=50000.0,
        founder_agent_id="agent_1",
    )

    company.add_sub_agent("board_1", "board")
    company.add_sub_agent("exec_1", "executive")

    company_dict = company.to_dict()

    assert company_dict["id"] == "company_123"
    assert company_dict["name"] == "TestCo"
    assert company_dict["capital"] == 50000.0
    assert company_dict["board_members"] == 1
    assert company_dict["executives"] == 1


def test_business_plan_creation():
    """Test business plan creation with all fields."""
    plan = BusinessPlan(
        company_name="TestCo",
        mission="Build products",
        vision="Market leader",
        one_liner="Best products",
        problem_statement="Problem X",
        solution_description="Solution Y",
        unique_value_proposition="Unique value",
        target_market="Developers",
        market_size=1000000.0,
        competition_analysis="Competitors A, B",
        competitive_advantages=["Advantage 1", "Advantage 2"],
        product_description="Product description",
        features=["Feature 1", "Feature 2"],
        development_roadmap=[],
        revenue_streams=[],
        pricing_strategy="Freemium",
        cost_structure=CostStructure(10000, 20000, 5000, 3000),
        funding_requested=100000.0,
        use_of_funds={"development": 50000},
        revenue_projections=[50000, 150000, 300000],
        break_even_timeline="Month 12",
        required_roles=["CTO", "Engineer"],
        milestones=[],
    )

    assert plan.company_name == "TestCo"
    assert plan.market_size == 1000000.0
    assert len(plan.revenue_projections) == 3
    assert plan.funding_requested == 100000.0
