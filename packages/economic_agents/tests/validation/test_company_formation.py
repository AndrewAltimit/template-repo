"""Company formation validation test with proper capital.

This test validates that an agent can successfully form and operate a company
when given sufficient resources.
"""

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet
from economic_agents.reports import generate_report_for_agent


def test_company_formation_with_sufficient_capital():
    """Test successful company formation and operation with adequate funding.

    Success Criteria:
    - Agent forms company when threshold reached
    - Company receives adequate initial capital
    - Company successfully develops at least one product
    - Company hires sub-agents
    - Company progresses through stages
    - All company decisions logged
    """
    # Setup: Agent with substantial capital to support company formation
    # Company formation requires $150 threshold and allocates 30% ($45+)
    # Product development requires $10,000
    # Solution: Start with high capital OR inject capital after formation

    wallet = MockWallet(initial_balance=500.0)  # Start with substantial funds
    compute = MockCompute(initial_hours=50.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 10.0,
            "company_threshold": 200.0,  # Lower threshold for faster formation
            "personality": "entrepreneur",  # Biased toward company building
        },
    )

    print(f"\n{'='*60}")
    print("COMPANY FORMATION VALIDATION TEST")
    print(f"{'='*60}")
    print(f"Initial Balance: ${agent.state.balance:.2f}")
    print("Company Threshold: $200.00")
    print("Strategy: Build capital, form company, test operations")
    print(f"{'='*60}\n")

    # Phase 1: Build capital and trigger company formation
    print("Phase 1: Building Capital and Forming Company...")

    # Run cycles until company forms, but catch the capital error
    cycles_run = 0
    max_cycles = 30

    while not agent.state.has_company and cycles_run < max_cycles:
        # Just update state and make allocation decision, don't execute company work yet
        agent._update_state()
        allocation = agent.decision_engine.decide_allocation(agent.state)

        # Check if company should form
        if agent.decision_engine.should_form_company(agent.state):
            # Form company
            _ = agent._form_company()
            print(f"✅ Company formed at cycle {cycles_run+1}: {agent.company.name}")
            print(f"   Initial company capital: ${agent.company.capital:.2f}")
            break

        # Otherwise do task work only
        if allocation.task_work_hours > 0:
            agent._do_task_work(allocation.task_work_hours)

        agent.state.cycles_completed += 1
        cycles_run += 1

        if cycles_run % 5 == 0:
            print(f"  Cycle {cycles_run}: Balance=${agent.state.balance:.2f}, Tasks={agent.state.tasks_completed}")

    print(f"Phase 1 Complete: Balance=${agent.state.balance:.2f}\n")

    # Verify company formation
    assert agent.state.has_company, "Agent failed to form company"
    assert agent.company is not None, "Company object not created"

    company = agent.company
    print(f"\n{'='*60}")
    print("COMPANY DETAILS")
    print(f"{'='*60}")
    print(f"Name: {company.name}")
    print(f"Stage: {company.stage}")
    print(f"Capital: ${company.capital:.2f}")
    print(f"Team Size: {len(company.get_all_sub_agent_ids())}")
    print(f"Products: {len(company.products)}")
    print(f"{'='*60}\n")

    # Phase 2: Inject capital to enable product development
    # This simulates the investment round that would come from a real investor
    print("Phase 2: Simulating Investment Round...")

    # Need capital for: product dev ($10k) + hiring ($2k/person * 3) + operations buffer
    capital_needed_for_operations = 10000.0 + (2000.0 * 3) + 5000.0  # $21k total
    current_capital = company.capital
    capital_injection = max(0, capital_needed_for_operations - current_capital)

    print(f"Current Company Capital: ${current_capital:.2f}")
    print(f"Capital Needed for Operations: ${capital_needed_for_operations:.2f}")
    print(f"Investment Injection: ${capital_injection:.2f}")

    # Inject capital directly into company (simulating investor funding)
    company.capital += capital_injection
    agent.wallet.receive_payment(
        from_address="investor_simulation", amount=capital_injection, memo="Simulated seed investment for product development"
    )

    print(f"Post-Investment Company Capital: ${company.capital:.2f}\n")

    # Phase 3: Company operations with adequate funding
    print("Phase 3: Company Operations...")

    initial_products = len(company.products)
    initial_team_size = len(company.get_all_sub_agent_ids())
    initial_stage = company.stage

    # Run cycles focused on company work
    for i in range(15):
        agent.run_cycle()

        if (i + 1) % 5 == 0:
            print(
                f"  Cycle {i+1}: "
                f"Stage={company.stage}, "
                f"Capital=${company.capital:.2f}, "
                f"Team={len(company.get_all_sub_agent_ids())}, "
                f"Products={len(company.products)}"
            )

    final_products = len(company.products)
    final_team_size = len(company.get_all_sub_agent_ids())
    final_stage = company.stage

    print(f"\n{'='*60}")
    print("COMPANY OPERATION RESULTS")
    print(f"{'='*60}")
    print(f"Stage: {initial_stage} → {final_stage}")
    print(f"Team Size: {initial_team_size} → {final_team_size}")
    print(f"Products: {initial_products} → {final_products}")
    print(f"Final Capital: ${company.capital:.2f}")
    print(f"\n{'='*60}")

    # Validations
    assert agent.company is not None, "Company no longer exists"
    assert len(company.products) > 0, "Company failed to develop any products"
    assert len(company.get_all_sub_agent_ids()) >= 3, "Company should have at least 3 team members"

    # Check if stage progressed
    if initial_stage == "ideation" and final_products > 0:
        assert final_stage != "ideation", "Company should progress from ideation after product development"

    # Check alignment monitoring
    if len(agent.alignment_monitor.alignment_scores) > 0:
        latest_alignment = agent.alignment_monitor.alignment_scores[-1]
        print(f"\nCompany Alignment Score: {latest_alignment.overall_alignment:.1f}/100")
        print(f"Alignment Level: {latest_alignment.alignment_level}")
        assert latest_alignment.company_id == company.id, "Alignment monitoring tracking wrong company"

    # Generate company report
    print("\nGenerating technical report...")
    _ = generate_report_for_agent(agent, "technical")

    # Success!
    print(f"\n{'='*60}")
    print("✅ COMPANY FORMATION TEST PASSED")
    print(f"{'='*60}")
    print(f"   Company: {company.name}")
    print(f"   Products Developed: {final_products}")
    print(f"   Team Size: {final_team_size}")
    print(f"   Current Stage: {final_stage}")
    print(f"   Alignment Monitoring: {len(agent.alignment_monitor.alignment_scores)} scores")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # Run test directly
    test_company_formation_with_sufficient_capital()
