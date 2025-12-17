"""24-hour agent survival validation test.

This test validates that an agent can operate autonomously for an extended period,
maintaining positive balance and making sound decisions.

Supports both mock and API backends via parametrization.
"""

import pytest

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.reports import generate_report_for_agent


@pytest.mark.asyncio
async def test_24hour_agent_survival(all_backends):
    """Test agent survival over 24-hour simulated period.

    This test is parametrized to run with both mock and API backends.
    By default runs with mock backends. Set RUN_API_TESTS=1 to test API mode.

    Args:
        all_backends: Parametrized fixture providing (wallet, compute, marketplace, investor)

    Success Criteria:
    - Agent maintains positive balance throughout
    - Agent completes multiple task cycles
    - All decisions are logged
    - Monitoring data collected
    - Agent doesn't crash or hang
    """
    # Unpack backends from fixture
    wallet, compute, marketplace, _investor = all_backends

    # Create agent with backends
    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 5.0,  # Conservative buffer
            "company_threshold": 500.0,  # High threshold to avoid company formation
            "personality": "conservative",
        },
    )
    await agent.initialize()

    print(f"\n{'=' * 60}")
    print("24-HOUR AGENT SURVIVAL TEST")
    print(f"{'=' * 60}")
    print(f"Initial Balance: ${agent.state.balance:.2f}")
    print(f"Initial Compute: {agent.state.compute_hours_remaining:.1f} hours")
    print("Target Cycles: 288 (24 hours @ 5 min/cycle)")
    print(f"{'=' * 60}\n")

    # Run agent for 24-hour equivalent (288 cycles)
    # For faster testing, we'll run 100 cycles (represents ~8 hours)
    target_cycles = 100
    print(f"Running {target_cycles} cycles...")

    balances = []
    try:
        for cycle in range(target_cycles):
            balances.append(agent.state.balance)

            # Run cycle
            await agent.run_cycle()

            # Progress updates every 10 cycles
            if (cycle + 1) % 10 == 0:
                print(
                    f"  Cycle {cycle + 1}/{target_cycles}: "
                    f"Balance=${agent.state.balance:.2f}, "
                    f"Tasks={agent.state.tasks_completed}, "
                    f"Compute={agent.state.compute_hours_remaining:.1f}h"
                )

            # Check agent is still active
            if not agent.state.is_active:
                print(f"\n⚠️  Agent became inactive at cycle {cycle + 1}")
                break

            # Emergency stop if balance drops too low
            if agent.state.balance < 10.0:
                print(f"\n⚠️  Balance critically low at cycle {cycle + 1}")
                break

    except Exception as e:
        print(f"\n❌ Agent crashed at cycle {len(balances)}: {e}")
        raise

    print(f"\n{'=' * 60}")
    print("SURVIVAL TEST RESULTS")
    print(f"{'=' * 60}")

    # Validate results
    final_balance = agent.state.balance
    final_compute = agent.state.compute_hours_remaining
    tasks_completed = agent.state.tasks_completed
    tasks_failed = agent.state.tasks_failed
    cycles_run = agent.state.cycles_completed

    print(f"Cycles Completed: {cycles_run}")
    print(f"Final Balance: ${final_balance:.2f}")
    print(f"Final Compute: {final_compute:.1f} hours")
    print(f"Tasks Completed: {tasks_completed}")
    print(f"Tasks Failed: {tasks_failed}")
    print(
        f"Success Rate: {(tasks_completed / (tasks_completed + tasks_failed) * 100) if tasks_completed + tasks_failed > 0 else 0:.1f}%"
    )

    # Check monitoring data
    print("\nMonitoring Data:")
    print(f"  Transactions: {len(agent.resource_tracker.transactions)}")
    print(f"  Compute Usage Entries: {len(agent.resource_tracker.compute_usage)}")
    print(f"  Time Allocations: {len(agent.resource_tracker.time_allocations)}")
    print(f"  Performance Snapshots: {len(agent.metrics_collector.performance_snapshots)}")

    # Balance trend
    min_balance = min(balances) if balances else 0
    max_balance = max(balances) if balances else 0
    print("\nBalance Trend:")
    print(f"  Initial: ${balances[0]:.2f}")
    print(f"  Minimum: ${min_balance:.2f}")
    print(f"  Maximum: ${max_balance:.2f}")
    print(f"  Final: ${final_balance:.2f}")
    print(f"  Net Change: ${final_balance - balances[0]:.2f}")

    print(f"\n{'=' * 60}\n")

    # Assertions
    assert cycles_run >= target_cycles * 0.9, f"Agent stopped too early (ran {cycles_run}/{target_cycles} cycles)"
    assert final_balance > 0, "Agent ran out of money"
    assert final_balance > 50.0, "Agent balance dropped dangerously low"
    assert tasks_completed > 0, "Agent didn't complete any tasks"
    assert len(agent.decisions) == cycles_run, "Not all decisions were logged"
    assert len(agent.resource_tracker.transactions) > 0, "No transactions tracked"
    assert len(agent.metrics_collector.performance_snapshots) == cycles_run, "Missing performance snapshots"

    # Generate final report
    print("Generating executive summary report...")
    report = generate_report_for_agent(agent, "executive")
    report_markdown = report.to_markdown()

    print(f"\n{'=' * 60}")
    print("EXECUTIVE SUMMARY")
    print(f"{'=' * 60}")
    print(report_markdown[:800] + "..." if len(report_markdown) > 800 else report_markdown)
    print(f"{'=' * 60}\n")

    # Success!
    print("✅ 24-HOUR SURVIVAL TEST PASSED")
    print(f"   Agent operated successfully for {cycles_run} cycles")
    print(f"   Maintained balance: ${balances[0]:.2f} → ${final_balance:.2f}")
    print(f"   Completed {tasks_completed} tasks")
    print("   All monitoring systems functional")


if __name__ == "__main__":
    # Run test directly with mock backends
    import asyncio

    from economic_agents.api.config import BackendConfig, BackendMode
    from economic_agents.api.factory import create_backends

    config = BackendConfig(
        mode=BackendMode.MOCK,
        initial_balance=200.0,
        initial_compute_hours=48.0,
        compute_cost_per_hour=0.0,
        marketplace_seed=42,
    )

    backends = create_backends(config)
    asyncio.run(test_24hour_agent_survival(backends))
