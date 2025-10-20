"""Tests for custom exceptions."""

from economic_agents.exceptions import (
    CompanyBankruptError,
    CompanyNotFoundError,
    EconomicAgentError,
    InsufficientCapitalError,
    InsufficientInvestorCapitalError,
    InvalidStageTransitionError,
)


def test_economic_agent_error_base():
    """Test base exception class."""
    error = EconomicAgentError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_insufficient_capital_error():
    """Test insufficient capital error with details."""
    error = InsufficientCapitalError(required=10000.0, available=5000.0, operation="hiring executive")

    assert error.required == 10000.0
    assert error.available == 5000.0
    assert error.operation == "hiring executive"
    assert "Insufficient capital" in str(error)
    assert "$10,000.00" in str(error)
    assert "$5,000.00" in str(error)
    assert "hiring executive" in str(error)


def test_company_bankrupt_error():
    """Test company bankruptcy error."""
    error = CompanyBankruptError(company_name="TechCorp", deficit=25000.0)

    assert error.company_name == "TechCorp"
    assert error.deficit == 25000.0
    assert "TechCorp" in str(error)
    assert "bankrupt" in str(error)
    assert "$25,000.00" in str(error)


def test_invalid_stage_transition_error():
    """Test invalid stage transition error."""
    error = InvalidStageTransitionError(current_stage="ideation", target_stage="operational")

    assert error.current_stage == "ideation"
    assert error.target_stage == "operational"
    assert "ideation" in str(error)
    assert "operational" in str(error)
    assert "Invalid stage transition" in str(error)


def test_company_not_found_error():
    """Test company not found error."""
    error = CompanyNotFoundError(company_id="company-123")

    assert error.company_id == "company-123"
    assert "company-123" in str(error)
    assert "not found" in str(error)


def test_company_not_found_error_with_available_ids():
    """Test company not found error with list of available IDs."""
    available_ids = ["comp-1", "comp-2", "comp-3", "comp-4", "comp-5", "comp-6"]
    error = CompanyNotFoundError(company_id="company-123", available_ids=available_ids)

    assert error.company_id == "company-123"
    assert error.available_ids == available_ids
    error_str = str(error)
    assert "company-123" in error_str
    assert "Available companies" in error_str
    # Should show first 5 IDs
    assert "comp-1" in error_str
    assert "comp-5" in error_str
    # Should indicate there are more
    assert "and 1 more" in error_str


def test_insufficient_investor_capital_error():
    """Test insufficient investor capital error."""
    error = InsufficientInvestorCapitalError(investor_name="Angel Investor", required=50000.0, available=30000.0)

    assert error.investor_name == "Angel Investor"
    assert error.required == 50000.0
    assert error.available == 30000.0
    assert "Angel Investor" in str(error)
    assert "$50,000.00" in str(error)
    assert "$30,000.00" in str(error)
    assert "insufficient capital" in str(error)


def test_exception_inheritance():
    """Test that all custom exceptions inherit from base class."""
    assert issubclass(InsufficientCapitalError, EconomicAgentError)
    assert issubclass(CompanyBankruptError, EconomicAgentError)
    assert issubclass(InvalidStageTransitionError, EconomicAgentError)
    assert issubclass(CompanyNotFoundError, EconomicAgentError)
    assert issubclass(InsufficientInvestorCapitalError, EconomicAgentError)
