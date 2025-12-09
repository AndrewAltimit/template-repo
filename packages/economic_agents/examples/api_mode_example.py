#!/usr/bin/env python3
"""Example using API mode with microservices.

This example shows how to use the agent with API-based backend services
instead of mock implementations. The agent interacts with real FastAPI
microservices running on localhost.

Prerequisites:
    - Start all API services first:
      docker-compose up wallet-api compute-api marketplace-api investor-api
    - Or use the provided start script:
      ./scripts/start_api_services.sh
"""

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.api.config import APIConfig, BackendConfig, BackendMode
from economic_agents.api.factory import create_backends


def main():
    """Run agent with API backend implementations."""
    print("=" * 60)
    print("API Mode Example")
    print("=" * 60)

    # Configure API mode
    api_config = APIConfig(
        wallet_api_url="http://localhost:8001",
        compute_api_url="http://localhost:8002",
        marketplace_api_url="http://localhost:8003",
        investor_api_url="http://localhost:8004",
    )

    backend_config = BackendConfig(
        mode=BackendMode.API,
        api_config=api_config,
        api_key="example_agent_key",  # Replace with actual API key
        initial_balance=200.0,
        initial_compute_hours=48.0,
        compute_cost_per_hour=0.0,
        marketplace_seed=42,
    )

    # Create all backends using factory
    wallet, compute, marketplace, _investor = create_backends(backend_config)

    print("\nBackend mode: API")
    print(f"Wallet API: {api_config.wallet_api_url}")
    print(f"Compute API: {api_config.compute_api_url}")
    print(f"Marketplace API: {api_config.marketplace_api_url}")
    print(f"Investor API: {api_config.investor_api_url}")

    # Create agent (same code as mock mode!)
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
    print(f"Compute hours: {agent.state.compute_hours_remaining:.1f}h")

    # Run 10 cycles (interacting with APIs)
    print("\nRunning 10 decision cycles via API...")
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
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure all API services are running:")
        print("  docker-compose up wallet-api compute-api marketplace-api investor-api")
