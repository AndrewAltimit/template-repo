"""Tests for company monthly operations and burn rate."""

import pytest
from economic_agents.company.company_builder import (
    MONTHLY_PRODUCT_COST,
    MONTHLY_SALARIES,
    CompanyBuilder,
)
from economic_agents.company.models import Company
from economic_agents.exceptions import CompanyBankruptError


@pytest.fixture
def company_builder():
    """Create a company builder instance."""
    return CompanyBuilder(config={})


@pytest.fixture
def test_company():
    """Create a test company with team and products."""
    from datetime import datetime

    company = Company(
        id="test-company-123",
        name="TestCorp",
        mission="Test mission",
        created_at=datetime.now(),
        capital=100000.0,
        founder_agent_id="founder-123",
        stage="development",
        funding_status="bootstrapped",
    )
    return company


def test_calculate_burn_rate_no_team_no_products(company_builder, test_company):
    """Test burn rate calculation with no team or products."""
    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)
    assert burn_rate == 0.0


def test_calculate_burn_rate_with_board_members(company_builder, test_company):
    """Test burn rate includes board member salaries."""
    # Add board members
    test_company.add_sub_agent("board-1", "board")
    test_company.add_sub_agent("board-2", "board")

    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)
    expected = 2 * MONTHLY_SALARIES["board"]
    assert burn_rate == expected


def test_calculate_burn_rate_with_executives(company_builder, test_company):
    """Test burn rate includes executive salaries."""
    # Add executives
    test_company.add_sub_agent("exec-1", "executive")
    test_company.add_sub_agent("exec-2", "executive")

    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)
    expected = 2 * MONTHLY_SALARIES["executive"]
    assert burn_rate == expected


def test_calculate_burn_rate_with_employees(company_builder, test_company):
    """Test burn rate includes employee salaries."""
    # Add employees
    test_company.add_sub_agent("emp-1", "employee")
    test_company.add_sub_agent("emp-2", "employee")
    test_company.add_sub_agent("emp-3", "employee")

    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)
    expected = 3 * MONTHLY_SALARIES["employee"]
    assert burn_rate == expected


def test_calculate_burn_rate_with_products(company_builder, test_company):
    """Test burn rate includes product maintenance costs."""
    # Add mock products
    from economic_agents.company.models import Product, ProductSpec

    spec1 = ProductSpec(
        name="Product 1",
        description="Test product",
        category="api-service",
        features=[],
        tech_stack=[],
    )
    spec2 = ProductSpec(
        name="Product 2",
        description="Test product",
        category="cli-tool",
        features=[],
        tech_stack=[],
    )

    test_company.products = [
        Product(
            spec=spec1,
            status="active",
            completion_percentage=100,
            code_artifacts={},
            documentation="Test docs",
        ),
        Product(
            spec=spec2,
            status="active",
            completion_percentage=100,
            code_artifacts={},
            documentation="Test docs",
        ),
    ]

    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)
    expected = 2 * MONTHLY_PRODUCT_COST
    assert burn_rate == expected


def test_calculate_burn_rate_full_company(company_builder, test_company):
    """Test burn rate with full company (team + products)."""
    # Add team members
    test_company.add_sub_agent("board-1", "board")
    test_company.add_sub_agent("exec-1", "executive")
    test_company.add_sub_agent("exec-2", "executive")
    test_company.add_sub_agent("emp-1", "employee")
    test_company.add_sub_agent("emp-2", "employee")

    # Add products
    from economic_agents.company.models import Product, ProductSpec

    spec = ProductSpec(
        name="Product",
        description="Test",
        category="api",
        features=[],
        tech_stack=[],
    )
    test_company.products = [
        Product(
            spec=spec,
            status="active",
            completion_percentage=100,
            code_artifacts={},
            documentation="Test docs",
        )
    ]

    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)

    expected = (
        1 * MONTHLY_SALARIES["board"]
        + 2 * MONTHLY_SALARIES["executive"]
        + 2 * MONTHLY_SALARIES["employee"]
        + 1 * MONTHLY_PRODUCT_COST
    )
    assert burn_rate == expected


def test_simulate_monthly_operations_success(company_builder, test_company):
    """Test successful monthly operations with sufficient capital."""
    # Add some costs
    test_company.add_sub_agent("exec-1", "executive")
    test_company.capital = 50000.0
    initial_capital = test_company.capital
    initial_expenses = test_company.metrics.expenses

    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)

    result = company_builder.simulate_monthly_operations(test_company)

    assert result["success"] is True
    assert result["burn_rate"] == burn_rate
    assert test_company.capital == initial_capital - burn_rate
    assert test_company.metrics.expenses == initial_expenses + burn_rate
    assert result["remaining_capital"] == test_company.capital


def test_simulate_monthly_operations_calculates_runway(company_builder, test_company):
    """Test monthly operations calculates correct runway."""
    test_company.add_sub_agent("exec-1", "executive")
    test_company.capital = 60000.0

    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)
    result = company_builder.simulate_monthly_operations(test_company)

    expected_runway = (test_company.capital) / burn_rate
    assert result["runway_months"] == pytest.approx(expected_runway)


def test_simulate_monthly_operations_bankruptcy(company_builder, test_company):
    """Test monthly operations raises bankruptcy error."""
    test_company.add_sub_agent("exec-1", "executive")
    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)

    # Set capital below burn rate
    test_company.capital = burn_rate - 1000.0

    with pytest.raises(CompanyBankruptError) as exc_info:
        company_builder.simulate_monthly_operations(test_company)

    error = exc_info.value
    assert error.company_name == test_company.name
    assert error.deficit == 1000.0


def test_simulate_monthly_operations_at_exact_burn_rate(company_builder, test_company):
    """Test monthly operations when capital exactly equals burn rate."""
    test_company.add_sub_agent("exec-1", "executive")
    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)
    test_company.capital = burn_rate

    result = company_builder.simulate_monthly_operations(test_company)

    assert result["success"] is True
    assert test_company.capital == 0.0


def test_simulate_monthly_operations_just_below_burn_rate(company_builder, test_company):
    """Test monthly operations fails when capital just below burn rate."""
    test_company.add_sub_agent("exec-1", "executive")
    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)
    test_company.capital = burn_rate - 0.01

    with pytest.raises(CompanyBankruptError):
        company_builder.simulate_monthly_operations(test_company)


def test_get_company_status_includes_financials(company_builder, test_company):
    """Test company status includes financial information."""
    test_company.add_sub_agent("exec-1", "executive")
    test_company.capital = 50000.0
    test_company.metrics.expenses = 10000.0

    burn_rate = company_builder.calculate_monthly_burn_rate(test_company)
    status = company_builder.get_company_status(test_company)

    assert "financials" in status
    assert status["financials"]["capital"] == 50000.0
    assert status["financials"]["monthly_burn_rate"] == burn_rate
    assert status["financials"]["runway_months"] == 50000.0 / burn_rate
    assert status["financials"]["total_expenses"] == 10000.0


def test_get_company_status_infinite_runway_no_burn(company_builder, test_company):
    """Test company status shows infinite runway with zero burn rate."""
    test_company.capital = 50000.0

    status = company_builder.get_company_status(test_company)

    assert status["financials"]["monthly_burn_rate"] == 0.0
    assert status["financials"]["runway_months"] == float("inf")
