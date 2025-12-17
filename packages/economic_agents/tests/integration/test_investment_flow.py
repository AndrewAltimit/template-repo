"""Integration tests for complete investment flow."""

from economic_agents.company.company_builder import CompanyBuilder
from economic_agents.investment import (
    CompanyRegistry,
    InvestmentCriteria,
    InvestmentStage,
    InvestorAgent,
    InvestorProfile,
    InvestorType,
    ProposalGenerator,
)


def test_end_to_end_investment_flow():
    """Test complete flow: company formation -> proposal -> evaluation -> investment."""
    # Step 1: Create company
    builder = CompanyBuilder()
    opportunity = {"product_type": "api-service", "target_market": "developers"}
    company = builder.create_company("agent_1", opportunity, 100_000.0)

    # Step 2: Register company
    registry = CompanyRegistry()
    registry.register_company(company)

    # Step 3: Generate investment proposal
    generator = ProposalGenerator()
    proposal = generator.generate_proposal(company, InvestmentStage.SEED)
    proposal = generator.submit_proposal(proposal)
    registry.submit_proposal(proposal)

    # Step 4: Create investor
    criteria = InvestmentCriteria(
        min_market_size=10_000_000.0,
        min_revenue_projection=30_000.0,
        max_burn_rate=10_000.0,
        required_team_size=3,
        preferred_stages=[InvestmentStage.SEED],
        preferred_markets=["developers"],
        risk_tolerance=0.7,
        min_roi_expectation=3.0,
    )

    investor_profile = InvestorProfile(
        id="investor_1",
        name="Dev Ventures",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=2_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    investor = InvestorAgent(investor_profile)

    # Step 5: Investor evaluates proposal
    decision = investor.evaluate_proposal(proposal)

    # Should be approved (good company, matches criteria)
    assert decision.approved is True
    assert decision.amount_offered > 0

    # Step 6: Execute investment
    investment = investor.execute_investment(proposal, decision)
    registry.record_investment(investment)

    # Step 7: Record investment in company
    company.record_investment(investment.id, investor_profile.id, investment.amount)

    # Verify final state
    assert company.total_funding_received == investment.amount
    assert investor_profile.portfolio_size == 1
    assert len(registry.get_company_investments("company_1" if company.id == "company_1" else company.id)) == 1


def test_multiple_investors_one_company():
    """Test multiple investors funding the same company."""
    # Create company
    builder = CompanyBuilder()
    opportunity = {"product_type": "saas", "target_market": "teams"}
    company = builder.create_company("agent_1", opportunity, 100_000.0)

    registry = CompanyRegistry()
    registry.register_company(company)

    # Generate proposal
    generator = ProposalGenerator()
    proposal = generator.generate_proposal(company, InvestmentStage.SEED)
    registry.submit_proposal(proposal)

    # Create two investors with different profiles
    angel_criteria = InvestmentCriteria(
        min_market_size=5_000_000.0,
        min_revenue_projection=20_000.0,
        max_burn_rate=15_000.0,
        required_team_size=2,
        preferred_stages=[InvestmentStage.PRE_SEED, InvestmentStage.SEED],
        preferred_markets=["teams", "developers"],
        risk_tolerance=0.8,  # High risk tolerance
        min_roi_expectation=4.0,
    )

    angel_profile = InvestorProfile(
        id="investor_1",
        name="Angel Investor",
        type=InvestorType.ANGEL,
        available_capital=500_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=angel_criteria,
    )

    vc_criteria = InvestmentCriteria(
        min_market_size=20_000_000.0,
        min_revenue_projection=40_000.0,
        max_burn_rate=10_000.0,
        required_team_size=3,
        preferred_stages=[InvestmentStage.SEED, InvestmentStage.SERIES_A],
        preferred_markets=["teams", "enterprises"],
        risk_tolerance=0.6,
        min_roi_expectation=3.5,
    )

    vc_profile = InvestorProfile(
        id="investor_2",
        name="VC Fund",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=5_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=vc_criteria,
    )

    angel = InvestorAgent(angel_profile)
    vc = InvestorAgent(vc_profile)

    # Both investors evaluate the same proposal
    angel_decision = angel.evaluate_proposal(proposal)
    vc_decision = vc.evaluate_proposal(proposal)

    # At least one should approve
    approvals = sum([angel_decision.approved, vc_decision.approved])
    assert approvals >= 1

    # Execute approved investments
    initial_capital = company.capital
    total_invested = 0.0

    if angel_decision.approved:
        investment = angel.execute_investment(proposal, angel_decision)
        registry.record_investment(investment)
        company.record_investment(investment.id, angel_profile.id, investment.amount)
        total_invested += investment.amount

    if vc_decision.approved:
        investment = vc.execute_investment(proposal, vc_decision)
        registry.record_investment(investment)
        company.record_investment(investment.id, vc_profile.id, investment.amount)
        total_invested += investment.amount

    # Verify company received funding
    assert company.capital == initial_capital + total_invested
    assert company.total_funding_received == total_invested


def test_investor_portfolio_diversification():
    """Test investor building portfolio across multiple companies."""
    # Create multiple companies
    builder = CompanyBuilder()
    companies = []

    for i, product_type in enumerate(["api-service", "cli-tool", "saas"]):
        opportunity = {"product_type": product_type, "target_market": "developers"}
        company = builder.create_company(f"agent_{i + 1}", opportunity, 100_000.0)
        companies.append(company)

    # Register all companies
    registry = CompanyRegistry()
    for company in companies:
        registry.register_company(company)

    # Generate proposals
    generator = ProposalGenerator()
    proposals = []
    for company in companies:
        proposal = generator.generate_proposal(company, InvestmentStage.SEED)
        registry.submit_proposal(proposal)
        proposals.append(proposal)

    # Create investor
    criteria = InvestmentCriteria(
        min_market_size=10_000_000.0,
        min_revenue_projection=30_000.0,
        max_burn_rate=10_000.0,
        required_team_size=3,
        preferred_stages=[InvestmentStage.SEED],
        preferred_markets=["developers"],
        risk_tolerance=0.7,
        min_roi_expectation=3.0,
    )

    profile = InvestorProfile(
        id="investor_1",
        name="Diversified VC",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=5_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    investor = InvestorAgent(profile)

    # Evaluate all proposals
    approved_count = 0
    for i, proposal in enumerate(proposals):
        decision = investor.evaluate_proposal(proposal)

        if decision.approved:
            investment = investor.execute_investment(proposal, decision)
            registry.record_investment(investment)
            companies[i].record_investment(investment.id, profile.id, investment.amount)
            approved_count += 1

    # Investor should have diversified portfolio
    assert profile.portfolio_size > 0
    assert profile.portfolio_size <= len(companies)
    assert profile.total_invested > 0
    assert profile.available_capital < 5_000_000.0


def test_company_seeking_investment_stage():
    """Test company advancing to seeking_investment stage."""
    builder = CompanyBuilder()
    opportunity = {"product_type": "api-service", "target_market": "developers"}
    company = builder.create_company("agent_1", opportunity, 100_000.0)

    # Advance company to seeking investment
    builder.advance_company_stage(company)  # ideation -> development
    builder.develop_product(company, "api-service")  # Develop product
    builder.advance_company_stage(company)  # development -> seeking_investment

    assert company.stage == "seeking_investment"

    # Company should now be eligible for investment
    registry = CompanyRegistry()
    registry.register_company(company)

    seeking_companies = registry.list_companies(seeking_investment=True)
    assert len(seeking_companies) == 1
    assert seeking_companies[0].id == company.id


def test_registry_provides_company_summary():
    """Test registry provides comprehensive company summary."""
    builder = CompanyBuilder()
    opportunity = {"product_type": "api-service", "target_market": "developers"}
    company = builder.create_company("agent_1", opportunity, 100_000.0)
    builder.develop_product(company, "api-service")

    registry = CompanyRegistry()
    registry.register_company(company)

    # Add proposal and investment
    generator = ProposalGenerator()
    proposal = generator.generate_proposal(company, InvestmentStage.SEED)
    registry.submit_proposal(proposal)

    criteria = InvestmentCriteria(
        min_market_size=10_000_000.0,
        min_revenue_projection=30_000.0,
        max_burn_rate=10_000.0,
        required_team_size=3,
        preferred_stages=[InvestmentStage.SEED],
        preferred_markets=["developers"],
        risk_tolerance=0.7,
        min_roi_expectation=3.0,
    )

    profile = InvestorProfile(
        id="investor_1",
        name="Test VC",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=1_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    investor = InvestorAgent(profile)
    decision = investor.evaluate_proposal(proposal)

    if decision.approved:
        investment = investor.execute_investment(proposal, decision)
        registry.record_investment(investment)

    summary = registry.get_company_summary(company.id)

    assert "company" in summary
    assert "proposals" in summary
    assert "team_size" in summary
    assert "products" in summary
    assert summary["products"] >= 1
    assert summary["team_size"] >= 3


def test_investor_decision_history():
    """Test investor maintains decision history."""
    builder = CompanyBuilder()
    companies = []

    for i in range(3):
        opportunity = {"product_type": "api-service", "target_market": "developers"}
        company = builder.create_company(f"agent_{i + 1}", opportunity, 100_000.0)
        companies.append(company)

    generator = ProposalGenerator()
    proposals = [generator.generate_proposal(c, InvestmentStage.SEED) for c in companies]

    criteria = InvestmentCriteria(
        min_market_size=10_000_000.0,
        min_revenue_projection=30_000.0,
        max_burn_rate=10_000.0,
        required_team_size=3,
        preferred_stages=[InvestmentStage.SEED],
        preferred_markets=["developers"],
        risk_tolerance=0.7,
        min_roi_expectation=3.0,
    )

    profile = InvestorProfile(
        id="investor_1",
        name="Test VC",
        type=InvestorType.VENTURE_CAPITAL,
        available_capital=2_000_000.0,
        total_invested=0.0,
        portfolio_size=0,
        criteria=criteria,
    )

    investor = InvestorAgent(profile)

    # Evaluate all proposals
    for proposal in proposals:
        decision = investor.evaluate_proposal(proposal)
        # Execute if approved
        if decision.approved and profile.can_invest(decision.amount_offered):
            investor.execute_investment(proposal, decision)

    # Check decision history
    assert len(profile.decision_history) == 3
    assert profile.decision_history[0] is not None
