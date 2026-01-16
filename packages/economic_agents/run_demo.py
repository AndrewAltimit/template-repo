#!/usr/bin/env python3
"""Run a demo agent with live dashboard updates.

This script runs an autonomous agent that feeds data to the dashboard in real-time.
Start the dashboard first, then run this script to see live updates.

Usage:
    python run_demo.py [--cycles CYCLES] [--mode {survival,company}] [--backend {mock,api}]

Environment variables can override defaults (see DemoConfig.from_env for details):
    DEMO_MODE=company
    DEMO_INITIAL_BALANCE=25000
    DEMO_MAX_CYCLES=100
"""

import argparse
import asyncio
from typing import Optional

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.api.config import BackendConfig, BackendMode
from economic_agents.api.factory import create_backends
from economic_agents.dashboard.dependencies import dashboard_state
from economic_agents.demo_config import DemoConfig, DemoMode


async def run_demo_async(
    config: Optional[DemoConfig] = None,
    backend: str = "mock",
) -> None:
    """Run demo agent with dashboard integration.

    Args:
        config: Demo configuration (uses defaults if None)
        backend: 'mock' (in-memory) or 'api' (microservices)
    """
    if config is None:
        config = DemoConfig.for_mode(DemoMode.SURVIVAL)

    print("Starting Autonomous Economic Agent Demo")
    print("=" * 60)
    print(f"Mode: {config.mode.value.upper()}")
    print(f"Backend: {backend.upper()}")
    print(f"Running for {config.max_cycles} cycles")
    print("View live updates at: http://localhost:8501")
    print("=" * 60)

    # Show mode-specific information
    if config.mode == DemoMode.SURVIVAL:
        print(f"\nSurvival mode: Agent will focus on task completion")
        print(f"  Initial balance: ${config.initial_balance:.2f}")
        print(f"  Company threshold: ${config.company_threshold:.2f} (unreachable)")
    else:
        print(f"\nCompany mode: Agent will form and operate company")
        print(f"  Initial balance: ${config.initial_balance:.2f}")
        print(f"  Company threshold: ${config.company_threshold:.2f}")

    # Create backends using factory
    backend_mode = BackendMode.API if backend == "api" else BackendMode.MOCK
    backend_config = BackendConfig(
        mode=backend_mode,
        initial_balance=config.initial_balance,
        initial_compute_hours=config.initial_compute_hours,
        compute_cost_per_hour=config.compute_cost_per_hour,
        marketplace_seed=config.marketplace_seed,
    )

    if backend == "api":
        print("\nUsing API backends (microservices)")
        print("   Make sure services are running:")
        print("   docker-compose up wallet-api compute-api marketplace-api investor-api")
    else:
        print("\nUsing mock backends (in-memory)")

    try:
        wallet, compute, marketplace, _investor = create_backends(backend_config)
    except Exception as e:
        print(f"\nFailed to create backends: {e}")
        if backend == "api":
            print("\nMake sure API services are running!")
        raise

    # Use the factory method to ensure proper async initialization
    agent = await AutonomousAgent.create(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": config.survival_buffer_hours,
            "company_threshold": config.company_threshold,
        },
        dashboard_state=dashboard_state,
    )

    print(f"\nAgent initialized: {agent.agent_id}")
    print(f"   Initial balance: ${agent.state.balance:.2f}")
    print(f"   Compute hours: {agent.state.compute_hours_remaining:.1f}h")
    print("\nRunning cycles (press Ctrl+C to stop gracefully)...\n")

    try:
        for cycle in range(config.max_cycles):
            await agent.run_cycle()

            # Print progress
            status = "Company Work" if agent.state.has_company else "Task Work"
            print(
                f"Cycle {cycle + 1:3d}/{config.max_cycles}: "
                f"Balance=${agent.state.balance:7.2f} | "
                f"Compute={agent.state.compute_hours_remaining:5.1f}h | "
                f"{status}"
            )

            # Delay to make updates visible in dashboard
            await asyncio.sleep(config.cycle_delay_seconds)

            # Stop if agent runs out of resources
            if agent.state.balance <= 0 or agent.state.compute_hours_remaining <= 0:
                print("\nAgent ran out of resources!")
                break

    except KeyboardInterrupt:
        print("\n\nDemo stopped by user")

    # Final summary
    print("\n" + "=" * 60)
    print("Final Statistics:")
    print("=" * 60)
    print(f"Cycles completed:     {agent.state.cycles_completed}")
    print(f"Final balance:        ${agent.state.balance:.2f}")
    print(f"Compute remaining:    {agent.state.compute_hours_remaining:.1f}h")
    print(f"Tasks completed:      {agent.state.tasks_completed}")
    print(f"Company formed:       {'Yes' if agent.state.has_company else 'No'}")

    if agent.state.has_company and agent.company:
        print("\nCompany Details:")
        print(f"   Name:             {agent.company.name}")
        print(f"   Stage:            {agent.company.stage}")
        team_size = len(agent.company.board_member_ids) + len(agent.company.executive_ids) + len(agent.company.employee_ids)
        print(f"   Team size:        {team_size}")
        print(f"   Products:         {len(agent.company.products)}")

    print("\nTip: Refresh the dashboard at http://localhost:8501 to see final state")
    print("=" * 60)


def run_demo(
    config: Optional[DemoConfig] = None,
    backend: str = "mock",
) -> None:
    """Synchronous wrapper for run_demo_async.

    Args:
        config: Demo configuration (uses defaults if None)
        backend: 'mock' (in-memory) or 'api' (microservices)

    Raises:
        RuntimeError: If called from within an existing event loop.
    """
    try:
        asyncio.get_running_loop()
        raise RuntimeError("run_demo() cannot be called from an async context. Use 'await run_demo_async(...)' instead.")
    except RuntimeError as e:
        if "no running event loop" in str(e):
            # No loop running - safe to use asyncio.run()
            asyncio.run(run_demo_async(config, backend))
        else:
            raise


def main() -> None:
    """Parse arguments and run the demo."""
    parser = argparse.ArgumentParser(description="Run agent demo with live dashboard")
    parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        help="Maximum number of cycles to run (default: 50, or DEMO_MAX_CYCLES)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["survival", "company"],
        default=None,
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

    # Load config from environment, with CLI args taking precedence
    mode = DemoMode(args.mode) if args.mode else None
    config = DemoConfig.from_env(mode=mode)

    # CLI args override environment/defaults
    if args.cycles is not None:
        config = config.model_copy(update={"max_cycles": args.cycles})

    run_demo(config=config, backend=args.backend)


if __name__ == "__main__":
    main()
