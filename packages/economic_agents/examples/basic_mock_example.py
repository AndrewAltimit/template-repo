#!/usr/bin/env python3
"""Basic example using mock implementations.

This example shows the simplest way to create and run an autonomous agent
using mock implementations for all backend services.
"""

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet


def main():
    """Run basic agent with mock implementations."""
    print("=" * 60)
    print("Basic Mock Implementation Example")
    print("=" * 60)

    # Create mock implementations directly
    wallet = MockWallet(initial_balance=200.0)
    compute = MockCompute(initial_hours=48.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    # Create agent (high company threshold to focus on task work)
    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 10.0,
            "company_threshold": 10000.0,  # Very high - won't form company
        },
    )

    print(f"\nAgent ID: {agent.agent_id}")
    print(f"Initial balance: ${agent.state.balance:.2f}")
    print(f"Compute hours: {agent.state.compute_hours_remaining:.1f}h")

    # Run 10 cycles
    print("\nRunning 10 decision cycles...")
    agent.run(max_cycles=10)

    # Show results
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    print(f"Final balance: ${agent.state.balance:.2f}")
    print(f"Compute remaining: {agent.state.compute_hours_remaining:.1f}h")
    print(f"Tasks completed: {agent.state.tasks_completed}")
    print(f"Cycles completed: {agent.state.cycles_completed}")
    print(f"Company formed: {'Yes' if agent.state.has_company else 'No'}")


if __name__ == "__main__":
    main()
