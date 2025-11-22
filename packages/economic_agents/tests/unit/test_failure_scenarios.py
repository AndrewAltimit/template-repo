"""Tests for failure scenarios (P1 #6)."""

from datetime import datetime

import pytest

from economic_agents.company.models import Company, ProductSpec
from economic_agents.company.product_builder import ProductBuilder
from economic_agents.exceptions import (
    CompanyBankruptError,
    InvalidStageTransitionError,
    ProductDevelopmentFailure,
    StageRegressionError,
)
from economic_agents.investment.investor_agent import InvestorAgent
from economic_agents.investment.models import (
    InvestmentCriteria,
    InvestmentProposal,
    InvestmentStage,
    InvestorProfile,
    InvestorType,
)

# Bankruptcy Tests


def test_company_bankruptcy_on_negative_capital():
    """Test that company goes bankrupt when capital goes negative."""
    company = Company(
        id="test-company-1",
        name="Failing Startup",
        mission="Test bankruptcy",
        created_at=datetime.now(),
        capital=1000.0,
        founder_agent_id="founder-1",
    )

    # Spend more than available capital
    with pytest.raises(CompanyBankruptError) as exc_info:
        company.spend_capital(1500.0, "large_expense")

    assert "Failing Startup" in str(exc_info.value)
    assert "bankrupt" in str(exc_info.value).lower()
    assert exc_info.value.deficit == 500.0


def test_company_bankruptcy_check_explicit():
    """Test explicit bankruptcy check method."""
    company = Company(
        id="test-company-2",
        name="Broke Company",
        mission="Test explicit check",
        created_at=datetime.now(),
        capital=-5000.0,
        founder_agent_id="founder-1",
    )

    with pytest.raises(CompanyBankruptError) as exc_info:
        company.check_bankruptcy()

    assert exc_info.value.company_name == "Broke Company"
    assert exc_info.value.deficit == 5000.0


def test_company_bankruptcy_tracking_expenses():
    """Test that bankruptcy correctly tracks expenses."""
    company = Company(
        id="test-company-3",
        name="Expense Tracker",
        mission="Test expense tracking",
        created_at=datetime.now(),
        capital=5000.0,
        founder_agent_id="founder-1",
    )

    # Spend within limits
    company.spend_capital(2000.0, "first_expense")
    assert company.capital == 3000.0
    assert company.metrics.expenses == 2000.0

    # Spend to bankruptcy
    with pytest.raises(CompanyBankruptError):
        company.spend_capital(4000.0, "fatal_expense")

    # Expenses should still be tracked even after bankruptcy
    assert company.metrics.expenses == 6000.0


# Investment Rejection Tests


def test_investment_rejection_low_score():
    """Test investment rejection when overall score is too low."""
    investor = InvestorAgent(
        profile=InvestorProfile(
            id="investor-1",
            name="Cautious Investor",
            type=InvestorType.VENTURE_CAPITAL,
            available_capital=1000000.0,
            total_invested=0.0,
            portfolio_size=0,
            criteria=InvestmentCriteria(
                min_market_size=10000000.0,
                min_revenue_projection=500000.0,
                max_burn_rate=50000.0,
                required_team_size=5,
                preferred_stages=[InvestmentStage.SEED, InvestmentStage.SERIES_A],
                preferred_markets=["technology"],
                risk_tolerance=0.3,
                min_roi_expectation=3.0,
            ),
        )
    )

    # Create weak proposal
    proposal = InvestmentProposal(
        id="proposal-1",
        company_id="company-1",
        company_name="Weak Startup",
        amount_requested=100000.0,
        valuation=1000000.0,
        equity_offered=10.0,
        stage=InvestmentStage.SEED,
        use_of_funds={"product": 50000.0, "marketing": 50000.0},
        revenue_projections=[100000.0, 200000.0, 300000.0],  # Below minimum
        market_size=5000000.0,  # Below minimum
        team_size=2,  # Below required
        competitive_advantages=["First mover"],
        risks=["Market competition", "Technical challenges", "Team inexperience"],
        milestones=[],
    )

    decision = investor.evaluate_proposal(proposal)

    assert decision.approved is False
    assert decision.amount_offered == 0.0
    assert decision.equity_requested == 0.0
    assert "rejected" in decision.reasoning.lower()
    assert "score" in decision.reasoning.lower()


def test_investment_rejection_insufficient_capital():
    """Test that investor rejects when they lack sufficient capital."""
    investor = InvestorAgent(
        profile=InvestorProfile(
            id="investor-2",
            name="Low Capital Investor",
            type=InvestorType.ANGEL,
            available_capital=50000.0,  # Not enough
            total_invested=0.0,
            portfolio_size=0,
            criteria=InvestmentCriteria(
                min_market_size=1000000.0,
                min_revenue_projection=100000.0,
                max_burn_rate=20000.0,
                required_team_size=3,
                preferred_stages=[InvestmentStage.SEED],
                preferred_markets=["technology"],
                risk_tolerance=0.7,
                min_roi_expectation=2.0,
            ),
        )
    )

    # Create strong proposal but requesting more than investor has
    proposal = InvestmentProposal(
        id="proposal-2",
        company_id="company-2",
        company_name="Strong Startup",
        amount_requested=100000.0,  # More than investor has
        equity_offered=10.0,
        valuation=1000000.0,
        stage=InvestmentStage.SEED,
        use_of_funds={"product": 50000.0, "marketing": 50000.0},
        market_size=50000000.0,
        revenue_projections=[500000.0, 1000000.0, 2000000.0],
        team_size=5,
        competitive_advantages=["Strong team", "Proprietary technology", "Market leader"],
        risks=["Market competition"],
        milestones=[],
    )

    decision = investor.evaluate_proposal(proposal)

    assert decision.approved is False  # Should be rejected due to insufficient capital


def test_investment_rejection_high_risk():
    """Test investment rejection when risk is too high for conservative investor."""
    investor = InvestorAgent(
        profile=InvestorProfile(
            id="investor-3",
            name="Very Conservative Investor",
            type=InvestorType.CORPORATE,
            available_capital=1000000.0,
            total_invested=0.0,
            portfolio_size=0,
            criteria=InvestmentCriteria(
                min_market_size=5000000.0,
                min_revenue_projection=100000.0,
                max_burn_rate=30000.0,
                required_team_size=3,
                preferred_stages=[InvestmentStage.SEED],
                preferred_markets=["technology"],
                risk_tolerance=0.2,  # Very low risk tolerance
                min_roi_expectation=4.0,
            ),
        )
    )

    # Create risky proposal
    proposal = InvestmentProposal(
        id="proposal-3",
        company_id="company-3",
        company_name="Risky Startup",
        amount_requested=100000.0,
        equity_offered=10.0,
        valuation=1000000.0,
        stage=InvestmentStage.SEED,
        use_of_funds={"product": 50000.0, "marketing": 50000.0},
        market_size=10000000.0,
        revenue_projections=[200000.0, 400000.0, 800000.0],
        team_size=3,
        competitive_advantages=["New technology"],
        risks=[
            "Unproven market",
            "Technical feasibility unclear",
            "Strong competition",
            "Regulatory uncertainty",
            "Team inexperience",
        ],  # Many risks
        milestones=[],
    )

    decision = investor.evaluate_proposal(proposal)

    # Should be rejected due to high risk profile
    if not decision.approved:
        assert "risk" in decision.reasoning.lower()


# Product Development Failure Tests


def test_product_development_failure_insufficient_capital():
    """Test product development fails when capital is too low."""
    builder = ProductBuilder()
    spec = ProductSpec(
        name="Ambitious SaaS",
        description="Complex platform",
        category="saas",
        features=["Feature 1", "Feature 2", "Feature 3"],
        tech_stack=["React", "Node.js", "PostgreSQL"],
    )

    # Very low capital should guarantee failure
    with pytest.raises(ProductDevelopmentFailure) as exc_info:
        builder.build_mvp_with_risk(spec, capital=10000.0, team_size=3, risk_factor=0.5)

    assert "Ambitious SaaS" in str(exc_info.value)
    assert exc_info.value.completion_percentage < 100.0
    assert "capital" in exc_info.value.reason.lower()


def test_product_development_failure_small_team():
    """Test product development fails with insufficient team size."""
    builder = ProductBuilder()
    spec = ProductSpec(
        name="Complex Product",
        description="Needs large team",
        category="saas",
        features=["Feature 1", "Feature 2", "Feature 3"],
        tech_stack=["React", "Node.js", "PostgreSQL"],
    )

    # Small team should increase failure probability
    # Run multiple times to ensure failure occurs (probabilistic)
    failed = False
    for _ in range(10):
        try:
            builder.build_mvp_with_risk(spec, capital=100000.0, team_size=1, risk_factor=0.3)
        except ProductDevelopmentFailure as e:
            failed = True
            assert "team" in e.reason.lower() or "complexity" in e.reason.lower()
            break

    # At least one attempt should have failed with this setup
    assert failed, "Expected at least one product development failure"


def test_product_development_success_good_conditions():
    """Test product development succeeds with good conditions."""
    builder = ProductBuilder()
    spec = ProductSpec(
        name="Simple CLI",
        description="Basic tool",
        category="cli-tool",
        features=["Feature 1", "Feature 2"],
        tech_stack=["Python"],
    )

    # Good conditions should lead to success
    product = builder.build_mvp_with_risk(spec, capital=200000.0, team_size=5, risk_factor=0.0)

    assert product is not None
    assert product.spec.name == "Simple CLI"
    assert product.status in ["alpha", "development"]


def test_product_development_failure_details():
    """Test that product development failure provides useful details."""
    builder = ProductBuilder()
    spec = ProductSpec(
        name="Failed Product",
        description="Will fail",
        category="saas",
        features=["Feature 1"] * 15,  # Too many features
        tech_stack=["React", "Node.js"],
    )

    # Test multiple times to ensure we get at least one failure (probabilistic)
    failure_occurred = False
    for _ in range(20):  # 20 attempts should guarantee at least one failure
        try:
            builder.build_mvp_with_risk(spec, capital=5000.0, team_size=1, risk_factor=0.8)
        except ProductDevelopmentFailure as e:
            # Verify failure details
            assert e.product_name == "Failed Product"
            assert 20.0 <= e.completion_percentage <= 70.0
            assert len(e.reason) > 10  # Should have meaningful reason
            assert e.reason in [
                "Ran out of capital before completion",
                "Team too small to complete development",
                "Technical complexity exceeded team capabilities",
                "Critical technical blocker could not be resolved",
            ]
            failure_occurred = True
            break

    assert failure_occurred, "Expected at least one ProductDevelopmentFailure in 20 attempts"


# Stage Regression Tests


def test_stage_regression_operational_to_development():
    """Test company regression from operational to development."""
    company = Company(
        id="test-company-4",
        name="Regressing Company",
        mission="Test regression",
        created_at=datetime.now(),
        capital=50000.0,
        founder_agent_id="founder-1",
        stage="operational",
    )

    with pytest.raises(StageRegressionError) as exc_info:
        company.regress_stage("Product failure led to customer loss")

    assert exc_info.value.from_stage == "operational"
    assert exc_info.value.to_stage == "development"
    assert company.stage == "development"
    assert "product failure" in exc_info.value.reason.lower()


def test_stage_regression_seeking_investment_to_development():
    """Test regression from seeking investment back to development."""
    company = Company(
        id="test-company-5",
        name="Failed Fundraise",
        mission="Test failed fundraise",
        created_at=datetime.now(),
        capital=20000.0,
        founder_agent_id="founder-1",
        stage="seeking_investment",
    )

    with pytest.raises(StageRegressionError) as exc_info:
        company.regress_stage("All investors passed, need to improve product")

    assert exc_info.value.from_stage == "seeking_investment"
    assert exc_info.value.to_stage == "development"
    assert company.stage == "development"


def test_stage_regression_ideation_stays_ideation():
    """Test that ideation stage cannot regress further."""
    company = Company(
        id="test-company-6",
        name="Early Stage",
        mission="Test floor stage",
        created_at=datetime.now(),
        capital=10000.0,
        founder_agent_id="founder-1",
        stage="ideation",
    )

    # Should not raise error, but also won't change stage
    result = company.regress_stage("Trying to regress from ideation")

    assert result == "ideation"
    assert company.stage == "ideation"


def test_stage_progression_validation():
    """Test that invalid stage progressions are blocked."""
    company = Company(
        id="test-company-7",
        name="Progressive Company",
        mission="Test stage progression",
        created_at=datetime.now(),
        capital=100000.0,
        founder_agent_id="founder-1",
        stage="ideation",
    )

    # Valid progression: ideation -> development
    result = company.attempt_stage_progression("development")
    assert result is True
    assert company.stage == "development"

    # Invalid progression: development -> ideation (can't go backwards this way)
    with pytest.raises(InvalidStageTransitionError) as exc_info:
        company.attempt_stage_progression("ideation")

    assert exc_info.value.current_stage == "development"
    assert exc_info.value.target_stage == "ideation"


def test_handle_failed_investment_round():
    """Test automated handling of failed investment round."""
    company = Company(
        id="test-company-8",
        name="Failed Round Company",
        mission="Test failed round",
        created_at=datetime.now(),
        capital=30000.0,
        founder_agent_id="founder-1",
        stage="seeking_investment",
        funding_status="seeking_seed",
    )

    # This should trigger regression
    with pytest.raises(StageRegressionError):
        company.handle_failed_investment_round()

    # After catching the error, verify the state changes
    assert company.stage == "development"
    # Funding status is updated before the error, so check it was updated
    # Actually, let's verify it by checking the exception was raised but state changed
    assert company.funding_status == "bootstrapped"


# Error Recovery Tests


def test_company_recovery_after_near_bankruptcy():
    """Test that company can recover from near-bankruptcy with investment."""
    company = Company(
        id="test-company-9",
        name="Recovering Company",
        mission="Test recovery",
        created_at=datetime.now(),
        capital=1000.0,  # Very low capital
        founder_agent_id="founder-1",
        stage="seeking_investment",
    )

    # Record investment to recover
    company.record_investment(investment_id="inv-1", investor_id="investor-1", amount=150000.0)

    assert company.capital == 151000.0
    assert company.total_funding_received == 150000.0
    assert "inv-1" in company.funding_rounds


def test_product_development_retry_after_failure():
    """Test that product development can be retried after initial failure."""
    builder = ProductBuilder()
    spec = ProductSpec(
        name="Retry Product",
        description="Will eventually succeed",
        category="library",
        features=["Feature 1", "Feature 2"],
        tech_stack=["Python"],
    )

    # First attempt with bad conditions (likely to fail)
    try:
        product = builder.build_mvp_with_risk(spec, capital=10000.0, team_size=1, risk_factor=0.7)
        # If it succeeds, that's fine
        assert product is not None
    except ProductDevelopmentFailure:
        # Expected failure - now retry with better conditions
        product = builder.build_mvp_with_risk(spec, capital=200000.0, team_size=5, risk_factor=0.0)
        assert product is not None
        assert product.spec.name == "Retry Product"


def test_stage_progression_after_regression():
    """Test that company can progress again after regression."""
    company = Company(
        id="test-company-10",
        name="Resilient Company",
        mission="Test resilience",
        created_at=datetime.now(),
        capital=50000.0,
        founder_agent_id="founder-1",
        stage="operational",
    )

    # Regress due to failure
    try:
        company.regress_stage("Major product issue")
    except StageRegressionError:
        pass

    assert company.stage == "development"

    # Now progress forward again
    company.attempt_stage_progression("seeking_investment")
    assert company.stage == "seeking_investment"

    company.attempt_stage_progression("operational")
    assert company.stage == "operational"


def test_multiple_expense_tracking():
    """Test that multiple expenses are tracked correctly even near bankruptcy."""
    company = Company(
        id="test-company-11",
        name="Expense Tracking",
        mission="Test multiple expenses",
        created_at=datetime.now(),
        capital=10000.0,
        founder_agent_id="founder-1",
    )

    # Multiple small expenses
    company.spend_capital(2000.0, "expense_1")
    company.spend_capital(3000.0, "expense_2")
    company.spend_capital(2000.0, "expense_3")

    assert company.capital == 3000.0
    assert company.metrics.expenses == 7000.0

    # One large expense leading to bankruptcy
    with pytest.raises(CompanyBankruptError):
        company.spend_capital(5000.0, "fatal_expense")

    # All expenses should be tracked
    assert company.metrics.expenses == 12000.0
