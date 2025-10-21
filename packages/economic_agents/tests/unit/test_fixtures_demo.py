"""Demonstration tests showing fixture usage (P1 #8).

This file demonstrates how test fixtures reduce code duplication
and improve test maintainability.
"""


def test_standard_company_fixture(standard_company):
    """Test using standard company fixture."""
    assert standard_company.name == "Test Startup"
    assert standard_company.capital == 100000.0
    assert standard_company.stage == "development"


def test_seed_stage_company_fixture(seed_stage_company):
    """Test using seed stage company fixture."""
    assert seed_stage_company.stage == "seeking_investment"
    assert seed_stage_company.funding_status == "seeking_seed"
    assert seed_stage_company.capital < 50000.0


def test_operational_company_fixture(operational_company):
    """Test using operational company with team."""
    assert operational_company.stage == "operational"
    assert len(operational_company.board_member_ids) == 1
    assert len(operational_company.executive_ids) == 1
    assert len(operational_company.employee_ids) == 2


def test_angel_investor_fixture(angel_investor):
    """Test using angel investor fixture."""
    assert angel_investor.type.value == "angel"
    assert angel_investor.available_capital == 500000.0
    assert angel_investor.criteria.risk_tolerance == 0.7


def test_vc_investor_fixture(vc_investor):
    """Test using VC investor fixture."""
    assert vc_investor.type.value == "venture_capital"
    assert vc_investor.available_capital > 5000000.0
    assert vc_investor.criteria.min_market_size > 10000000.0


def test_strong_proposal_fixture(strong_proposal):
    """Test using strong proposal fixture."""
    assert strong_proposal.market_size >= 50000000.0
    assert len(strong_proposal.competitive_advantages) >= 3
    assert strong_proposal.team_size >= 5


def test_weak_proposal_fixture(weak_proposal):
    """Test using weak proposal fixture."""
    assert weak_proposal.market_size < 10000000.0
    assert weak_proposal.team_size < 3
    assert len(weak_proposal.risks) > len(weak_proposal.competitive_advantages)


def test_api_product_spec_fixture(api_product_spec):
    """Test using API product spec fixture."""
    assert api_product_spec.category == "api-service"
    assert len(api_product_spec.features) >= 3
    assert "Python" in api_product_spec.tech_stack


def test_saas_product_spec_fixture(saas_product_spec):
    """Test using SaaS product spec fixture."""
    assert saas_product_spec.category == "saas"
    assert len(saas_product_spec.features) >= 5


def test_ceo_fixture(ceo):
    """Test using CEO fixture."""
    assert ceo.role_title == "CEO"
    assert ceo.specialization == "leadership"


def test_cto_fixture(cto):
    """Test using CTO fixture."""
    assert cto.role_title == "CTO"
    assert cto.specialization == "technology"


def test_backend_developer_fixture(backend_developer):
    """Test using backend developer fixture."""
    assert "backend" in backend_developer.specialization.lower()


def test_sme_security_fixture(sme_security):
    """Test using security SME fixture."""
    assert sme_security.specialization == "security"
    kb = sme_security.knowledge_base
    assert len(kb["best_practices"]) >= 5
    assert len(kb["risks"]) >= 3


def test_simulation_clock_fixture(simulation_clock):
    """Test using simulation clock fixture."""
    assert simulation_clock.current_cycle == 0
    assert simulation_clock.hours_per_cycle == 24.0


def test_monthly_clock_fixture(monthly_clock):
    """Test using monthly clock fixture."""
    assert monthly_clock.hours_per_cycle == 730.0


def test_time_tracker_fixture(time_tracker):
    """Test using time tracker fixture."""
    assert time_tracker.clock is not None
    assert len(time_tracker.events) == 0


# Factory Fixture Tests


def test_company_factory(company_factory):
    """Test using company factory."""
    company1 = company_factory(name="Company 1", capital=50000.0)
    company2 = company_factory(name="Company 2", capital=200000.0, stage="operational")

    assert company1.name == "Company 1"
    assert company1.capital == 50000.0
    assert company2.name == "Company 2"
    assert company2.stage == "operational"


def test_product_spec_factory(product_spec_factory):
    """Test using product spec factory."""
    spec1 = product_spec_factory(name="Product A", feature_count=5)
    spec2 = product_spec_factory(name="Product B", category="saas", feature_count=10)

    assert spec1.name == "Product A"
    assert len(spec1.features) == 5
    assert spec2.category == "saas"
    assert len(spec2.features) == 10


def test_sub_agent_factory_board(sub_agent_factory):
    """Test creating board member with factory."""
    board = sub_agent_factory("board", "board-test", specialization="governance")

    assert board.id == "board-test"
    assert board.specialization == "governance"


def test_sub_agent_factory_executive(sub_agent_factory):
    """Test creating executive with factory."""
    exec_agent = sub_agent_factory("executive", "exec-test", role_title="CFO", specialization="finance")

    assert exec_agent.id == "exec-test"
    assert exec_agent.role_title == "CFO"


def test_sub_agent_factory_ic(sub_agent_factory):
    """Test creating IC with factory."""
    ic = sub_agent_factory("ic", "ic-test", specialization="frontend-dev")

    assert ic.id == "ic-test"
    assert ic.specialization == "frontend-dev"


def test_sub_agent_factory_sme(sub_agent_factory):
    """Test creating SME with factory."""
    sme = sub_agent_factory("sme", "sme-test", specialization="scaling")

    assert sme.id == "sme-test"
    assert sme.specialization == "scaling"


# Integration Test Example


def test_complete_workflow_with_fixtures(
    standard_company, angel_investor, strong_proposal, ceo, backend_developer, simulation_clock
):
    """Test complete workflow using multiple fixtures.

    This demonstrates how fixtures enable testing complex scenarios
    without duplicating setup code.
    """
    # Company has team
    standard_company.add_sub_agent(ceo.id, "executive")
    standard_company.add_sub_agent(backend_developer.id, "employee")

    # Verify company structure
    assert len(standard_company.executive_ids) == 1
    assert len(standard_company.employee_ids) == 1

    # Investor evaluates proposal
    assert angel_investor.available_capital >= strong_proposal.amount_requested

    # Simulation clock advances
    result = simulation_clock.advance_cycle()
    assert result["cycle"] == 1
    assert simulation_clock.total_hours_elapsed == 24.0
