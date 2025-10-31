"""Full pipeline validation: Monitoring → Dashboard → Reports.

This test validates the complete data flow from agent operations through
monitoring, dashboard updates, and report generation.
"""

import pytest
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.dashboard.dependencies import DashboardState
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet
from economic_agents.reports import generate_report_for_agent


@pytest.mark.asyncio
async def test_full_monitoring_dashboard_reports_pipeline():
    """Test complete pipeline: Agent → Monitoring → Dashboard → Reports.

    Success Criteria:
    - Agent operations tracked by all monitoring components
    - Dashboard state updated in real-time
    - Dashboard provides access to monitoring data
    - All 4 report types generated successfully
    - Data consistency across all systems
    """
    print(f"\n{'='*60}")
    print("FULL PIPELINE VALIDATION TEST")
    print(f"{'='*60}")
    print("Testing: Agent → Monitoring → Dashboard → Reports")
    print(f"{'='*60}\n")

    # Setup: Agent connected to dashboard
    wallet = MockWallet(initial_balance=300.0)
    compute = MockCompute(initial_hours=40.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)
    dashboard_state = DashboardState()

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 10.0,
            "company_threshold": 10000.0,  # Very high threshold to avoid company formation
            "personality": "balanced",
        },
        dashboard_state=dashboard_state,  # Connect dashboard
    )
    await agent.initialize()

    print("✅ Agent created with dashboard connection")
    print(f"   Initial Balance: ${agent.state.balance:.2f}")
    print(f"   Dashboard Connected: {dashboard_state is not None}\n")

    # Verify dashboard received monitoring components
    print("Step 1: Verify Dashboard Integration")
    print(f"{'='*60}")
    assert dashboard_state.resource_tracker is agent.resource_tracker
    assert dashboard_state.metrics_collector is agent.metrics_collector
    assert dashboard_state.alignment_monitor is agent.alignment_monitor
    print("✅ Dashboard has references to all monitoring components\n")

    # Run agent for multiple cycles
    print("Step 2: Run Agent and Collect Data")
    print(f"{'='*60}")
    cycles_to_run = 10
    print(f"Running {cycles_to_run} cycles...")

    for i in range(cycles_to_run):
        await agent.run_cycle()
        if (i + 1) % 3 == 0:
            print(f"  Cycle {i+1}: Balance=${agent.state.balance:.2f}, Tasks={agent.state.tasks_completed}")

    print(f"✅ Agent ran {cycles_to_run} cycles successfully\n")

    # Verify monitoring data collection
    print("Step 3: Verify Monitoring Data Collection")
    print(f"{'='*60}")

    # Resource tracking
    transactions = agent.resource_tracker.transactions
    compute_usage = agent.resource_tracker.compute_usage
    time_allocations = agent.resource_tracker.time_allocations

    print("Resource Tracker:")
    print(f"  - Transactions: {len(transactions)}")
    print(f"  - Compute Usage Entries: {len(compute_usage)}")
    print(f"  - Time Allocations: {len(time_allocations)}")

    assert len(transactions) > 0, "No transactions tracked"
    assert len(compute_usage) > 0, "No compute usage tracked"
    assert len(time_allocations) == cycles_to_run, f"Expected {cycles_to_run} allocations, got {len(time_allocations)}"

    # Metrics collection
    snapshots = agent.metrics_collector.performance_snapshots

    print("\nMetrics Collector:")
    print(f"  - Performance Snapshots: {len(snapshots)}")

    assert len(snapshots) == cycles_to_run, f"Expected {cycles_to_run} snapshots, got {len(snapshots)}"

    # Check latest snapshot
    latest_snapshot = snapshots[-1]
    print(f"  - Latest Snapshot Balance: ${latest_snapshot.agent_balance:.2f}")
    print(f"  - Latest Snapshot Tasks: {latest_snapshot.tasks_completed}")

    assert latest_snapshot.agent_balance == agent.state.balance, "Snapshot balance mismatch"
    assert latest_snapshot.tasks_completed == agent.state.tasks_completed, "Snapshot tasks mismatch"

    print("✅ All monitoring data collected correctly\n")

    # Verify dashboard state updates
    print("Step 4: Verify Dashboard State")
    print(f"{'='*60}")

    dashboard_agent_state = dashboard_state.get_agent_state()

    print("Dashboard Agent State:")
    print(f"  - Agent ID: {dashboard_agent_state.get('agent_id', 'N/A')}")
    print(f"  - Balance: ${dashboard_agent_state.get('balance', 0):.2f}")
    print(f"  - Tasks Completed: {dashboard_agent_state.get('tasks_completed', 0)}")
    print(f"  - Cycles Completed: {dashboard_agent_state.get('cycles_completed', 0)}")

    assert dashboard_agent_state["agent_id"] == agent.agent_id
    assert dashboard_agent_state["balance"] == agent.state.balance
    assert dashboard_agent_state["tasks_completed"] == agent.state.tasks_completed
    # Cycles completed should match agent's internal count (may differ slightly from loop count)
    assert dashboard_agent_state["cycles_completed"] == agent.state.cycles_completed

    print("✅ Dashboard state reflects current agent state\n")

    # Access monitoring data through dashboard
    print("Step 5: Access Monitoring Data via Dashboard")
    print(f"{'='*60}")

    dashboard_resource_tracker = dashboard_state.resource_tracker
    dashboard_metrics = dashboard_state.metrics_collector

    print("Data accessible through dashboard:")
    print(f"  - Transactions: {len(dashboard_resource_tracker.transactions)}")
    print(f"  - Performance Snapshots: {len(dashboard_metrics.performance_snapshots)}")

    assert len(dashboard_resource_tracker.transactions) == len(transactions)
    assert len(dashboard_metrics.performance_snapshots) == len(snapshots)

    print("✅ Monitoring data accessible through dashboard\n")

    # Generate all report types
    print("Step 6: Generate All Report Types")
    print(f"{'='*60}")

    report_types = ["executive", "technical", "audit", "governance"]
    reports = {}

    for report_type in report_types:
        print(f"Generating {report_type} report...")
        report = generate_report_for_agent(agent, report_type)
        reports[report_type] = report
        print(f"  ✅ {report_type.capitalize()} report: {len(report.to_markdown())} chars")

    print(f"\n✅ All {len(reports)} report types generated successfully\n")

    # Verify report content
    print("Step 7: Verify Report Content")
    print(f"{'='*60}")

    # Executive summary
    exec_report = reports["executive"]
    assert "key_metrics" in exec_report.content
    assert "decisions" in agent.agent_id or agent.agent_id in exec_report.title
    print("✅ Executive summary contains key metrics")

    # Technical report
    tech_report = reports["technical"]
    assert "performance_metrics" in tech_report.content
    assert "decision_log" in tech_report.content
    assert len(tech_report.content["decision_log"]) > 0
    print("✅ Technical report contains performance data and decisions")

    # Audit trail
    audit_report = reports["audit"]
    assert "transactions" in audit_report.content
    assert "decisions" in audit_report.content
    assert len(audit_report.content["transactions"]) > 0
    print("✅ Audit trail contains transaction history")

    # Governance analysis
    gov_report = reports["governance"]
    assert "accountability_challenges" in gov_report.content
    assert "recommendations" in gov_report.content
    print("✅ Governance analysis contains policy recommendations")

    print(f"\n{'='*60}")
    print("PIPELINE VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Agent executed {cycles_to_run} cycles")
    print(f"✅ Monitoring captured {len(transactions)} transactions")
    print(f"✅ Dashboard updated {cycles_to_run} times")
    print(f"✅ Generated {len(reports)} report types")
    print("✅ Data consistency verified across all systems")
    print(f"{'='*60}\n")

    print("✅✅✅ FULL PIPELINE TEST PASSED ✅✅✅")
    print("   All components integrated and functioning correctly")
    print("   Data flows seamlessly: Agent → Monitoring → Dashboard → Reports\n")


if __name__ == "__main__":
    # Run test directly
    import asyncio

    asyncio.run(test_full_monitoring_dashboard_reports_pipeline())
