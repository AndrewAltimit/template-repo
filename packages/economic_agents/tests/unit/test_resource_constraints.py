"""Tests for resource constraints in company operations."""

import pytest
from economic_agents.company.company_builder import (
    HIRING_COSTS,
    MONTHLY_PRODUCT_COST,
    MONTHLY_SALARIES,
    PRODUCT_DEVELOPMENT_COST,
    CompanyBuilder,
)
from economic_agents.company.models import Company
from economic_agents.exceptions import InsufficientCapitalError


@pytest.fixture
def company_builder():
    """Create a company builder instance."""
    return CompanyBuilder(config={})


@pytest.fixture
def test_company():
    """Create a test company with sufficient capital."""
    from datetime import datetime

    company = Company(
        id="test-company-123",
        name="TestCorp",
        mission="Test mission",
        created_at=datetime.now(),
        capital=50000.0,
        founder_agent_id="founder-123",
        stage="ideation",
        funding_status="bootstrapped",
    )
    return company


def test_hiring_costs_defined():
    """Test that hiring costs are properly defined."""
    assert HIRING_COSTS["board"] == 0.0
    assert HIRING_COSTS["executive"] == 5000.0
    assert HIRING_COSTS["employee"] == 2000.0


def test_monthly_salaries_defined():
    """Test that monthly salaries are properly defined."""
    assert MONTHLY_SALARIES["board"] == 0.0
    assert MONTHLY_SALARIES["executive"] == 15000.0
    assert MONTHLY_SALARIES["employee"] == 10000.0


def test_product_costs_defined():
    """Test that product development costs are properly defined."""
    assert PRODUCT_DEVELOPMENT_COST == 10000.0
    assert MONTHLY_PRODUCT_COST == 2000.0


def test_expand_team_with_sufficient_capital(company_builder, test_company):
    """Test hiring with sufficient capital deducts cost."""
    initial_capital = test_company.capital
    initial_expenses = test_company.metrics.expenses

    agent_id = company_builder.expand_team(test_company, "employee", "backend-dev")

    assert agent_id is not None
    assert test_company.capital == initial_capital - HIRING_COSTS["employee"]
    assert test_company.metrics.expenses == initial_expenses + HIRING_COSTS["employee"]
    assert agent_id in test_company.get_all_sub_agent_ids()


def test_expand_team_with_insufficient_capital(company_builder, test_company):
    """Test hiring fails with insufficient capital."""
    test_company.capital = 1000.0  # Less than employee hiring cost

    with pytest.raises(InsufficientCapitalError) as exc_info:
        company_builder.expand_team(test_company, "employee", "backend-dev")

    error = exc_info.value
    assert error.required == HIRING_COSTS["employee"]
    assert error.available == 1000.0
    assert "employee" in error.operation
    assert "backend-dev" in error.operation


def test_expand_team_board_member_no_cost(company_builder, test_company):
    """Test board member hiring has no cost."""
    initial_capital = test_company.capital

    agent_id = company_builder.expand_team(test_company, "board", "advisor")

    assert agent_id is not None
    assert test_company.capital == initial_capital  # No cost for board
    assert agent_id in test_company.board_member_ids


def test_expand_team_executive_with_cost(company_builder, test_company):
    """Test executive hiring deducts correct cost."""
    initial_capital = test_company.capital

    agent_id = company_builder.expand_team(test_company, "executive", "CTO")

    assert agent_id is not None
    assert test_company.capital == initial_capital - HIRING_COSTS["executive"]
    assert agent_id in test_company.executive_ids


def test_develop_product_with_sufficient_capital(company_builder, test_company):
    """Test product development with sufficient capital."""
    initial_capital = test_company.capital
    initial_expenses = test_company.metrics.expenses
    initial_product_count = len(test_company.products)

    company_builder.develop_product(test_company, "api-service")

    assert len(test_company.products) == initial_product_count + 1
    assert test_company.capital == initial_capital - PRODUCT_DEVELOPMENT_COST
    assert test_company.metrics.expenses == initial_expenses + PRODUCT_DEVELOPMENT_COST
    assert test_company.stage == "development"


def test_develop_product_with_insufficient_capital(company_builder, test_company):
    """Test product development fails with insufficient capital."""
    test_company.capital = 5000.0  # Less than product development cost

    with pytest.raises(InsufficientCapitalError) as exc_info:
        company_builder.develop_product(test_company, "api-service")

    error = exc_info.value
    assert error.required == PRODUCT_DEVELOPMENT_COST
    assert error.available == 5000.0
    assert "api-service" in error.operation
    assert "developing" in error.operation


def test_develop_product_updates_metrics(company_builder, test_company):
    """Test product development updates company metrics."""
    company_builder.develop_product(test_company, "cli-tool")

    assert test_company.metrics.products_developed == 1


def test_expand_team_at_exact_cost_boundary(company_builder, test_company):
    """Test hiring when capital exactly equals cost."""
    test_company.capital = HIRING_COSTS["employee"]

    agent_id = company_builder.expand_team(test_company, "employee", "backend-dev")

    assert agent_id is not None
    assert test_company.capital == 0.0


def test_develop_product_at_exact_cost_boundary(company_builder, test_company):
    """Test product development when capital exactly equals cost."""
    test_company.capital = PRODUCT_DEVELOPMENT_COST

    company_builder.develop_product(test_company, "library")

    assert len(test_company.products) == 1
    assert test_company.capital == 0.0


def test_expand_team_just_below_cost_boundary(company_builder, test_company):
    """Test hiring fails when capital is just below cost."""
    test_company.capital = HIRING_COSTS["executive"] - 0.01

    with pytest.raises(InsufficientCapitalError):
        company_builder.expand_team(test_company, "executive", "CFO")


def test_develop_product_just_below_cost_boundary(company_builder, test_company):
    """Test product development fails when capital is just below cost."""
    test_company.capital = PRODUCT_DEVELOPMENT_COST - 0.01

    with pytest.raises(InsufficientCapitalError):
        company_builder.develop_product(test_company, "api-service")
