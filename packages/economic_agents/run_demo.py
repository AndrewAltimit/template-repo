#!/usr/bin/env python3
"""Run a demo agent with live dashboard updates.

This script runs an autonomous agent that feeds data to the dashboard in real-time.
Start the dashboard first, then run this script to see live updates.

Usage:
    python run_demo.py [--cycles CYCLES] [--mode {survival,company}] [--backend {mock,api}]
"""

import argparse
import time

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.api.config import BackendConfig, BackendMode
from economic_agents.api.factory import create_backends
from economic_agents.dashboard.dependencies import dashboard_state


def run_demo(max_cycles: int = 50, mode: str = "survival", backend: str = "mock"):
    """Run demo agent with dashboard integration.

    Args:
        max_cycles: Number of cycles to run
        mode: 'survival' (no company) or 'company' (form company)
        backend: 'mock' (in-memory) or 'api' (microservices)
    """
    print("🤖 Starting Autonomous Economic Agent Demo")
    print("=" * 60)
    print(f"Mode: {mode.upper()}")
    print(f"Backend: {backend.upper()}")
    print(f"Running for {max_cycles} cycles")
    print("View live updates at: http://localhost:8501")
    print("=" * 60)

    # Configure based on mode
    if mode == "survival":
        # Agent focuses on survival, doesn't form company
        initial_balance = 100.0
        company_threshold = 50000.0  # Very high, won't reach
        print("\n📋 Survival mode: Agent will focus on task completion")
    else:
        # Agent has capital to operate a company
        initial_balance = 50000.0
        company_threshold = 150.0
        print("\n🏢 Company mode: Agent will form and operate company")

    # Create backends using factory
    backend_mode = BackendMode.API if backend == "api" else BackendMode.MOCK
    config = BackendConfig(
        mode=backend_mode,
        initial_balance=initial_balance,
        initial_compute_hours=100.0,
        compute_cost_per_hour=0.0,
        marketplace_seed=42,
    )

    if backend == "api":
        print("\n⚙️  Using API backends (microservices)")
        print("   Make sure services are running:")
        print("   docker-compose up wallet-api compute-api marketplace-api investor-api")
    else:
        print("\n⚙️  Using mock backends (in-memory)")

    try:
        wallet, compute, marketplace, investor = create_backends(config)
    except Exception as e:
        print(f"\n❌ Failed to create backends: {e}")
        if backend == "api":
            print("\nMake sure API services are running!")
        raise

    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 20.0,
            "company_threshold": company_threshold,
        },
        dashboard_state=dashboard_state,
    )

    print(f"\n✅ Agent initialized: {agent.agent_id}")
    print(f"   Initial balance: ${agent.state.balance:.2f}")
    print(f"   Compute hours: {agent.state.compute_hours_remaining:.1f}h")
    print("\nRunning cycles (press Ctrl+C to stop gracefully)...\n")

    try:
        for cycle in range(max_cycles):
            agent.run_cycle()

            # Print progress
            status = "🏢 Company Work" if agent.state.has_company else "💼 Task Work"
            print(
                f"Cycle {cycle + 1:3d}/{max_cycles}: "
                f"Balance=${agent.state.balance:7.2f} | "
                f"Compute={agent.state.compute_hours_remaining:5.1f}h | "
                f"{status}"
            )

            # Small delay to make updates visible
            time.sleep(0.5)

            # Stop if agent runs out of resources
            if agent.state.balance <= 0 or agent.state.compute_hours_remaining <= 0:
                print("\n⚠️  Agent ran out of resources!")
                break

    except KeyboardInterrupt:
        print("\n\n⏸️  Demo stopped by user")

    # Final summary
    print("\n" + "=" * 60)
    print("📊 Final Statistics:")
    print("=" * 60)
    print(f"Cycles completed:     {agent.state.cycles_completed}")
    print(f"Final balance:        ${agent.state.balance:.2f}")
    print(f"Compute remaining:    {agent.state.compute_hours_remaining:.1f}h")
    print(f"Tasks completed:      {agent.state.tasks_completed}")
    print(f"Company formed:       {'Yes ✅' if agent.state.has_company else 'No'}")

    if agent.state.has_company and agent.company:
        print("\n🏢 Company Details:")
        print(f"   Name:             {agent.company.name}")
        print(f"   Stage:            {agent.company.stage}")
        team_size = len(agent.company.board_member_ids) + len(agent.company.executive_ids) + len(agent.company.employee_ids)
        print(f"   Team size:        {team_size}")
        print(f"   Products:         {len(agent.company.products)}")

    print("\n💡 Tip: Refresh the dashboard at http://localhost:8501 to see final state")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run agent demo with live dashboard")
    parser.add_argument(
        "--cycles",
        type=int,
        default=50,
        help="Maximum number of cycles to run (default: 50)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["survival", "company"],
        default="survival",
        help="Demo mode: 'survival' (task work only) or 'company' (with company formation)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["mock", "api"],
        default="mock",
        help="Backend type: 'mock' (in-memory, default) or 'api' (microservices)",
    )
    args = parser.parse_args()

    run_demo(max_cycles=args.cycles, mode=args.mode, backend=args.backend)
