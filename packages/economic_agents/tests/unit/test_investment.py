"""Tests for investment system."""

from datetime import datetime

import pytest
from economic_agents.company.company_builder import CompanyBuilder
from economic_agents.company.models import Company
from economic_agents.investment import (
    CompanyRegistry,
    Investment,
    InvestmentCriteria,
    InvestmentProposal,
    InvestmentStage,
    InvestorAgent,
    InvestorProfile,
    InvestorType,
    ProposalGenerator,
)


def test_investor_profile_creation():
    """Test creating an investor profile."""
    criteria = InvestmentCriteria(
        min_market_size=10_000_000.0,
        min_revenue_projection=50_000.0,
        max_burn_rate=10_000.0,
        required_team_size=3,
        preferred_stages=[InvestmentStage.SEED],
        preferred_markets=["developers"],
        risk_tolerance=0.6,
        min_roi_expectation=3.0,
    )

    profile = InvestorProfile(
        id="investor_1",
        name="Test Ventures",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=1_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    assert profile.name == "Test Ventures"
    assert profile.available_capital == 1_000_000.0
    assert profile.can_invest(500_000.0)
    assert not profile.can_invest(2_000_000.0)


def test_investor_agent_evaluates_good_proposal():
    """Test investor agent approves good proposal."""
    criteria = InvestmentCriteria(
        min_market_size=10_000_000.0,
        min_revenue_projection=40_000.0,
        max_burn_rate=10_000.0,
        required_team_size=3,
        preferred_stages=[InvestmentStage.SEED],
        preferred_markets=["developers"],
        risk_tolerance=0.6,
        min_roi_expectation=3.0,
    )

    profile = InvestorProfile(
        id="investor_1",
        name="Test Ventures",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=1_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    investor = InvestorAgent(profile)

    proposal = InvestmentProposal(
        id="proposal_1",
        company_id="company_1",
        company_name="Test Co",
        amount_requested=75_000.0,
        valuation=500_000.0,
        equity_offered=15.0,
        stage=InvestmentStage.SEED,
        use_of_funds={"product": 40_000.0, "team": 35_000.0},
        revenue_projections=[40_000.0, 120_000.0, 250_000.0],
        market_size=50_000_000.0,
        team_size=5,
        competitive_advantages=["First mover", "Strong team"],
        risks=["Market risk"],
        milestones=[],
    )

    decision = investor.evaluate_proposal(proposal)

    assert decision.approved is True
    assert decision.amount_offered == 75_000.0
    assert len(decision.conditions) > 0
    assert "approved" in decision.reasoning.lower()


def test_investor_agent_rejects_weak_proposal():
    """Test investor agent rejects proposal not meeting criteria."""
    criteria = InvestmentCriteria(
        min_market_size=100_000_000.0,  # Very high requirement
        min_revenue_projection=200_000.0,  # Very high requirement
        max_burn_rate=5_000.0,
        required_team_size=10,  # Very large team required
        preferred_stages=[InvestmentStage.SERIES_A],
        preferred_markets=["enterprises"],
        risk_tolerance=0.3,  # Low risk tolerance
        min_roi_expectation=5.0,
    )

    profile = InvestorProfile(
        id="investor_1",
        name="Conservative VC",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=1_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    investor = InvestorAgent(profile)

    # Proposal with weak metrics
    proposal = InvestmentProposal(
        id="proposal_1",
        company_id="company_1",
        company_name="Weak Co",
        amount_requested=50_000.0,
        valuation=200_000.0,
        equity_offered=25.0,
        stage=InvestmentStage.PRE_SEED,  # Wrong stage
        use_of_funds={"product": 30_000.0, "team": 20_000.0},
        revenue_projections=[10_000.0, 30_000.0, 60_000.0],  # Low revenue
        market_size=5_000_000.0,  # Small market
        team_size=2,  # Small team
        competitive_advantages=[],
        risks=["Market risk", "Team risk", "Technology risk"],
        milestones=[],
    )

    decision = investor.evaluate_proposal(proposal)

    assert decision.approved is False
    assert decision.amount_offered == 0.0
    assert "rejected" in decision.reasoning.lower()


def test_investor_agent_insufficient_capital():
    """Test investor cannot invest without sufficient capital."""
    criteria = InvestmentCriteria(
        min_market_size=10_000_000.0,
        min_revenue_projection=40_000.0,
        max_burn_rate=10_000.0,
        required_team_size=3,
        preferred_stages=[InvestmentStage.SEED],
        preferred_markets=["developers"],
        risk_tolerance=0.6,
        min_roi_expectation=3.0,
    )

    profile = InvestorProfile(
        id="investor_1",
        name="Small Fund",
        type=InvestorType.ANGEL,
        available_capital=10_000.0,  # Low capital
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    investor = InvestorAgent(profile)

    proposal = InvestmentProposal(
        id="proposal_1",
        company_id="company_1",
        company_name="Test Co",
        amount_requested=75_000.0,  # More than available
        valuation=500_000.0,
        equity_offered=15.0,
        stage=InvestmentStage.SEED,
        use_of_funds={"product": 40_000.0, "team": 35_000.0},
        revenue_projections=[40_000.0, 120_000.0, 250_000.0],
        market_size=50_000_000.0,
        team_size=5,
        competitive_advantages=["First mover"],
        risks=["Market risk"],
        milestones=[],
    )

    decision = investor.evaluate_proposal(proposal)

    # Should reject due to insufficient capital
    assert decision.approved is False


def test_investor_agent_execute_investment():
    """Test executing an approved investment."""
    criteria = InvestmentCriteria(
        min_market_size=10_000_000.0,
        min_revenue_projection=40_000.0,
        max_burn_rate=10_000.0,
        required_team_size=3,
        preferred_stages=[InvestmentStage.SEED],
        preferred_markets=["developers"],
        risk_tolerance=0.6,
        min_roi_expectation=3.0,
    )

    profile = InvestorProfile(
        id="investor_1",
        name="Test Ventures",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=1_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    investor = InvestorAgent(profile)

    proposal = InvestmentProposal(
        id="proposal_1",
        company_id="company_1",
        company_name="Test Co",
        amount_requested=75_000.0,
        valuation=500_000.0,
        equity_offered=15.0,
        stage=InvestmentStage.SEED,
        use_of_funds={"product": 40_000.0, "team": 35_000.0},
        revenue_projections=[40_000.0, 120_000.0, 250_000.0],
        market_size=50_000_000.0,
        team_size=5,
        competitive_advantages=["First mover"],
        risks=["Market risk"],
        milestones=[],
    )

    decision = investor.evaluate_proposal(proposal)
    assert decision.approved is True

    investment = investor.execute_investment(proposal, decision)

    assert investment.amount == 75_000.0
    assert investment.company_id == "company_1"
    assert profile.available_capital == 925_000.0
    assert profile.total_invested == 75_000.0
    assert profile.portfolio_size == 1


def test_investor_cannot_execute_rejected_investment():
    """Test cannot execute rejected investment."""
    criteria = InvestmentCriteria(
        min_market_size=100_000_000.0,
        min_revenue_projection=200_000.0,
        max_burn_rate=5_000.0,
        required_team_size=10,
        preferred_stages=[InvestmentStage.SERIES_A],
        preferred_markets=["enterprises"],
        risk_tolerance=0.3,
        min_roi_expectation=5.0,
    )

    profile = InvestorProfile(
        id="investor_1",
        name="Conservative VC",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=1_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    investor = InvestorAgent(profile)

    proposal = InvestmentProposal(
        id="proposal_1",
        company_id="company_1",
        company_name="Weak Co",
        amount_requested=50_000.0,
        valuation=200_000.0,
        equity_offered=25.0,
        stage=InvestmentStage.PRE_SEED,
        use_of_funds={"product": 30_000.0, "team": 20_000.0},
        revenue_projections=[10_000.0, 30_000.0, 60_000.0],
        market_size=5_000_000.0,
        team_size=2,
        competitive_advantages=[],
        risks=["Market risk", "Team risk"],
        milestones=[],
    )

    decision = investor.evaluate_proposal(proposal)
    assert decision.approved is False

    with pytest.raises(ValueError, match="Cannot execute rejected investment"):
        investor.execute_investment(proposal, decision)


def test_company_registry_register_company():
    """Test registering a company in the registry."""
    registry = CompanyRegistry()

    company = Company(
        id="company_1",
        name="Test Co",
        mission="Test mission",
        created_at=datetime.now(),
        capital=100_000.0,
        founder_agent_id="agent_1",
    )

    result = registry.register_company(company)
    assert result is True

    # Cannot register same company twice
    result = registry.register_company(company)
    assert result is False

    retrieved = registry.get_company("company_1")
    assert retrieved.name == "Test Co"


def test_company_registry_submit_proposal():
    """Test submitting proposal to registry."""
    registry = CompanyRegistry()

    company = Company(
        id="company_1",
        name="Test Co",
        mission="Test mission",
        created_at=datetime.now(),
        capital=100_000.0,
        founder_agent_id="agent_1",
    )

    registry.register_company(company)

    proposal = InvestmentProposal(
        id="proposal_1",
        company_id="company_1",
        company_name="Test Co",
        amount_requested=75_000.0,
        valuation=500_000.0,
        equity_offered=15.0,
        stage=InvestmentStage.SEED,
        use_of_funds={"product": 40_000.0, "team": 35_000.0},
        revenue_projections=[40_000.0, 120_000.0, 250_000.0],
        market_size=50_000_000.0,
        team_size=5,
        competitive_advantages=["First mover"],
        risks=["Market risk"],
        milestones=[],
    )

    result = registry.submit_proposal(proposal)
    assert result is True

    proposals = registry.get_company_proposals("company_1")
    assert len(proposals) == 1
    assert proposals[0].amount_requested == 75_000.0


def test_company_registry_record_investment():
    """Test recording investment in registry."""
    registry = CompanyRegistry()

    company = Company(
        id="company_1",
        name="Test Co",
        mission="Test mission",
        created_at=datetime.now(),
        capital=100_000.0,
        founder_agent_id="agent_1",
    )

    registry.register_company(company)

    investment = Investment(
        id="investment_1",
        investor_id="investor_1",
        company_id="company_1",
        proposal_id="proposal_1",
        decision_id="decision_1",
        amount=75_000.0,
        equity=15.0,
        valuation=500_000.0,
        stage=InvestmentStage.SEED,
    )

    result = registry.record_investment(investment)
    assert result is True

    # Company must update its own capital
    company.record_investment(investment.id, investment.investor_id, investment.amount)

    # Company capital should be updated
    updated_company = registry.get_company("company_1")
    assert updated_company.capital == 175_000.0

    total_funding = registry.get_total_funding("company_1")
    assert total_funding == 75_000.0


def test_company_registry_list_companies():
    """Test listing companies with filters."""
    registry = CompanyRegistry()

    company1 = Company(
        id="company_1",
        name="Test Co 1",
        mission="Test mission",
        created_at=datetime.now(),
        capital=100_000.0,
        founder_agent_id="agent_1",
        stage="development",
    )

    company2 = Company(
        id="company_2",
        name="Test Co 2",
        mission="Test mission",
        created_at=datetime.now(),
        capital=50_000.0,
        founder_agent_id="agent_2",
        stage="seeking_investment",
    )

    registry.register_company(company1)
    registry.register_company(company2)

    # List all
    all_companies = registry.list_companies()
    assert len(all_companies) == 2

    # Filter by stage
    seeking = registry.list_companies(seeking_investment=True)
    assert len(seeking) == 1
    assert seeking[0].name == "Test Co 2"

    # Filter by capital
    wealthy = registry.list_companies(min_capital=75_000.0)
    assert len(wealthy) == 1
    assert wealthy[0].name == "Test Co 1"


def test_proposal_generator_generates_proposal():
    """Test generating proposal from company."""
    builder = CompanyBuilder()

    opportunity = {"product_type": "api-service", "target_market": "developers"}
    company = builder.create_company("agent_1", opportunity, 100_000.0)

    generator = ProposalGenerator()
    proposal = generator.generate_proposal(company, InvestmentStage.SEED)

    assert proposal.company_id == company.id
    assert proposal.company_name == company.name
    assert proposal.amount_requested > 0
    assert proposal.valuation > 0
    assert proposal.stage == InvestmentStage.SEED
    assert len(proposal.competitive_advantages) > 0
    assert len(proposal.use_of_funds) > 0


def test_proposal_generator_calculates_reasonable_valuation():
    """Test proposal generator calculates reasonable valuation."""
    builder = CompanyBuilder()

    opportunity = {"product_type": "saas", "target_market": "teams"}
    company = builder.create_company("agent_1", opportunity, 100_000.0)

    generator = ProposalGenerator()
    proposal = generator.generate_proposal(company, InvestmentStage.SEED)

    # Valuation should be reasonable multiple of revenue
    if proposal.revenue_projections and proposal.revenue_projections[0] > 0:
        multiple = proposal.valuation / proposal.revenue_projections[0]
        assert 3 < multiple < 20  # Reasonable range for seed stage


def test_company_records_investment():
    """Test company can record received investments."""
    company = Company(
        id="company_1",
        name="Test Co",
        mission="Test mission",
        created_at=datetime.now(),
        capital=100_000.0,
        founder_agent_id="agent_1",
    )

    initial_capital = company.capital
    company.record_investment("investment_1", "investor_1", 75_000.0)

    assert len(company.funding_rounds) == 1
    assert company.total_funding_received == 75_000.0
    assert "investor_1" in company.investor_ids
    assert company.capital == initial_capital + 75_000.0


def test_registry_stats():
    """Test registry statistics."""
    registry = CompanyRegistry()

    company1 = Company(
        id="company_1",
        name="Test Co 1",
        mission="Test mission",
        created_at=datetime.now(),
        capital=100_000.0,
        founder_agent_id="agent_1",
        stage="development",
    )

    company2 = Company(
        id="company_2",
        name="Test Co 2",
        mission="Test mission",
        created_at=datetime.now(),
        capital=50_000.0,
        founder_agent_id="agent_2",
        stage="seeking_investment",
    )

    registry.register_company(company1)
    registry.register_company(company2)

    stats = registry.get_registry_stats()
    assert stats["total_companies"] == 2
    assert stats["companies_by_stage"]["development"] == 1
    assert stats["companies_by_stage"]["seeking_investment"] == 1
