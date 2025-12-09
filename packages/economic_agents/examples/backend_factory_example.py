#!/usr/bin/env python3
"""Example showing backend factory pattern for easy mode switching.

This example demonstrates how the backend factory makes it trivial to switch
between mock and API implementations using configuration.
"""

import os

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.api.config import BackendConfig, BackendMode
from economic_agents.api.factory import create_backends


def run_with_mode(mode: str):
    """Run agent with specified backend mode.

    Args:
        mode: Either 'mock' or 'api'
    """
    print("=" * 60)
    print(f"Backend Factory Example - {mode.upper()} Mode")
    print("=" * 60)

    # Configure backend mode
    if mode == "mock":
        config = BackendConfig(
            mode=BackendMode.MOCK,
            initial_balance=200.0,
            initial_compute_hours=48.0,
            compute_cost_per_hour=0.0,
            marketplace_seed=42,
        )
    else:
        # API mode - could also use BackendConfig.from_env()
        config = BackendConfig.from_env()

    # Create backends - same code for both modes!
    wallet, compute, marketplace, _investor = create_backends(config)

    print(f"\nBackend mode: {config.mode.value}")
    print(f"Wallet type: {type(wallet).__name__}")
    print(f"Compute type: {type(compute).__name__}")
    print(f"Marketplace type: {type(marketplace).__name__}")

    # Create agent - identical code regardless of mode
    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={
            "survival_buffer_hours": 10.0,
            "company_threshold": 150.0,
        },
    )

    print(f"\nAgent ID: {agent.agent_id}")
    print(f"Initial balance: ${agent.state.balance:.2f}")

    # Run 5 cycles
    print(f"\nRunning 5 cycles in {mode} mode...")
    agent.run(max_cycles=5)

    # Results
    print(f"\nFinal balance: ${agent.state.balance:.2f}")
    print(f"Tasks completed: {agent.state.tasks_completed}")
    print("=" * 60 + "\n")


def environment_based_example():
    """Show using environment variables for configuration."""
    print("=" * 60)
    print("Environment-Based Configuration Example")
    print("=" * 60)

    # Set environment variables
    os.environ["BACKEND_MODE"] = "mock"
    os.environ["INITIAL_BALANCE"] = "250.0"
    os.environ["INITIAL_COMPUTE_HOURS"] = "100.0"

    # Load config from environment
    config = BackendConfig.from_env()

    print("\nConfiguration loaded from environment:")
    print(f"  Mode: {config.mode.value}")
    print(f"  Initial balance: ${config.initial_balance:.2f}")
    print(f"  Initial compute: {config.initial_compute_hours:.1f}h")

    # Create backends
    wallet, compute, marketplace, _investor = create_backends(config)

    # Create agent
    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 10.0, "company_threshold": 150.0},
    )

    print("\nAgent created with environment-based config")
    print(f"Balance: ${agent.state.balance:.2f}")
    print("=" * 60 + "\n")


def main():
    """Run examples."""
    # Example 1: Mock mode
    run_with_mode("mock")

    # Example 2: Environment-based config
    environment_based_example()

    # Example 3: API mode (commented out - requires services running)
    # run_with_mode("api")

    print("\n💡 Key Takeaway:")
    print("The backend factory pattern allows switching between mock and API")
    print("implementations with just a configuration change. The agent code")
    print("remains identical regardless of which backend you use!")


if __name__ == "__main__":
    main()
