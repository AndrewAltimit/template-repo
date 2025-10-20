"""Tests for company builder and related components."""

from economic_agents.company.business_plan_generator import BusinessPlanGenerator
from economic_agents.company.company_builder import CompanyBuilder
from economic_agents.company.models import ProductSpec
from economic_agents.company.product_builder import ProductBuilder
from economic_agents.company.sub_agent_manager import SubAgentManager


def test_sub_agent_manager_create_board_member():
    """Test creating a board member."""
    manager = SubAgentManager()

    agent = manager.create_sub_agent(
        role="board_member",
        specialization="finance",
        company_id="company_123",
    )

    assert agent.role == "board_member"
    assert agent.specialization == "finance"
    assert agent.company_id == "company_123"


def test_sub_agent_manager_create_executive():
    """Test creating an executive."""
    manager = SubAgentManager()

    agent = manager.create_sub_agent(
        role="executive",
        specialization="technology",
        company_id="company_123",
        role_title="CTO",
    )

    assert agent.role == "executive"
    assert agent.role_title == "CTO"


def test_sub_agent_manager_create_initial_team():
    """Test creating initial company team."""
    manager = SubAgentManager()

    team = manager.create_initial_team("company_123")

    assert "board" in team
    assert "executives" in team
    assert len(team["board"]) == 2  # 2 board members
    assert len(team["executives"]) == 1  # CEO


def test_sub_agent_manager_create_expanded_team():
    """Test creating expanded team with technical roles."""
    manager = SubAgentManager()

    team = manager.create_expanded_team("company_123", include_technical=True)

    assert len(team["executives"]) >= 2  # CEO + CTO
    assert len(team["employees"]) >= 2  # SME + IC


def test_sub_agent_manager_coordinate():
    """Test coordinating sub-agents on task."""
    manager = SubAgentManager()

    # Create some agents
    manager.create_sub_agent("board_member", "governance", "company_123")
    manager.create_sub_agent("executive", "leadership", "company_123", role_title="CEO")

    task = {"type": "strategic_decision", "roles": ["board_member", "executive"]}
    actions = manager.coordinate_sub_agents(task)

    assert len(actions) > 0
    assert all("agent_id" in action for action in actions)


def test_sub_agent_manager_get_team_summary():
    """Test getting team summary statistics."""
    manager = SubAgentManager()

    manager.create_initial_team("company_123")

    summary = manager.get_team_summary()

    assert "total_agents" in summary
    assert summary["total_agents"] >= 3
    assert "by_role" in summary


def test_business_plan_generator_api_service():
    """Test generating API service business plan."""
    generator = BusinessPlanGenerator()

    opportunity = {"product_type": "api-service", "target_market": "developers"}
    plan = generator.generate_plan(opportunity)

    assert "API" in plan.company_name or "api" in plan.company_name.lower()
    assert plan.target_market == "developers"
    assert len(plan.features) > 0
    assert plan.funding_requested > 0


def test_business_plan_generator_cli_tool():
    """Test generating CLI tool business plan."""
    generator = BusinessPlanGenerator()

    opportunity = {"product_type": "cli-tool", "target_market": "developers"}
    plan = generator.generate_plan(opportunity)

    assert "CLI" in plan.company_name or "Tool" in plan.company_name
    assert len(plan.revenue_streams) > 0


def test_business_plan_generator_saas():
    """Test generating SaaS business plan."""
    generator = BusinessPlanGenerator()

    opportunity = {"product_type": "saas", "target_market": "teams"}
    plan = generator.generate_plan(opportunity)

    assert plan.funding_requested > 100000.0  # SaaS requires more capital
    assert len(plan.required_roles) >= 3  # SaaS needs larger team


def test_product_builder_api_service_mvp():
    """Test building API service MVP."""
    builder = ProductBuilder()

    spec = ProductSpec(
        name="Data API",
        description="Data processing API",
        category="api-service",
        features=["Validation", "Transform"],
        tech_stack=["Python", "FastAPI"],
    )

    product = builder.build_mvp(spec)

    assert product.status in ["alpha", "development"]
    assert product.completion_percentage > 0
    assert len(product.code_artifacts) > 0
    assert "server" in str(product.code_artifacts).lower() or "api" in str(product.code_artifacts).lower()


def test_product_builder_cli_tool_mvp():
    """Test building CLI tool MVP."""
    builder = ProductBuilder()

    spec = ProductSpec(
        name="DevTool",
        description="Developer CLI",
        category="cli-tool",
        features=["Scaffolding"],
        tech_stack=["Python"],
    )

    product = builder.build_mvp(spec)

    assert "cli" in str(product.code_artifacts).lower()
    assert product.documentation is not None


def test_product_builder_iterate():
    """Test iterating on existing product."""
    builder = ProductBuilder()

    spec = ProductSpec(
        name="Product",
        description="Test product",
        category="library",
        features=["Feature 1"],
        tech_stack=["Python"],
    )

    product = builder.build_mvp(spec)
    initial_completion = product.completion_percentage

    updated_product = builder.iterate_product(product, "features")

    assert updated_product.completion_percentage > initial_completion


def test_product_builder_generate_demo():
    """Test generating product demo."""
    builder = ProductBuilder()

    spec = ProductSpec(
        name="Test Product",
        description="A test product",
        category="api-service",
        features=["Feature 1", "Feature 2"],
        tech_stack=["Python"],
    )

    product = builder.build_mvp(spec)
    demo = builder.generate_demo(product)

    assert "Test Product" in demo
    assert "Feature 1" in demo
    assert "Feature 2" in demo


def test_company_builder_create_company():
    """Test creating a company."""
    builder = CompanyBuilder()

    opportunity = {"product_type": "api-service", "target_market": "developers"}

    company = builder.create_company(
        founder_agent_id="agent_123",
        opportunity=opportunity,
        initial_capital=100000.0,
    )

    assert company.name is not None
    assert company.capital == 100000.0
    assert company.founder_agent_id == "agent_123"
    assert company.business_plan is not None
    assert len(company.get_all_sub_agent_ids()) >= 3  # Initial team


def test_company_builder_expand_team():
    """Test expanding company team."""
    builder = CompanyBuilder()

    opportunity = {"product_type": "api-service", "target_market": "developers"}
    company = builder.create_company("agent_123", opportunity, 100000.0)

    initial_team_size = len(company.get_all_sub_agent_ids())

    agent_id = builder.expand_team(company, "employee", "backend-dev")

    assert agent_id is not None
    assert len(company.get_all_sub_agent_ids()) == initial_team_size + 1


def test_company_builder_develop_product():
    """Test developing a product for company."""
    builder = CompanyBuilder()

    opportunity = {"product_type": "api-service", "target_market": "developers"}
    company = builder.create_company("agent_123", opportunity, 100000.0)

    assert len(company.products) == 0

    builder.develop_product(company, "api-service")

    assert len(company.products) == 1
    assert company.products[0].spec.category == "api-service"
    assert company.metrics.products_developed == 1


def test_company_builder_advance_stage():
    """Test advancing company stage."""
    builder = CompanyBuilder()

    opportunity = {"product_type": "api-service", "target_market": "developers"}
    company = builder.create_company("agent_123", opportunity, 100000.0)

    assert company.stage == "ideation"

    builder.advance_company_stage(company)

    assert company.stage == "development"


def test_company_builder_get_status():
    """Test getting comprehensive company status."""
    builder = CompanyBuilder()

    opportunity = {"product_type": "api-service", "target_market": "developers"}
    company = builder.create_company("agent_123", opportunity, 100000.0)
    builder.develop_product(company, "api-service")

    status = builder.get_company_status(company)

    assert "company" in status
    assert "team" in status
    assert "products" in status
    assert len(status["products"]) == 1
