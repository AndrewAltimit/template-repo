"""Quick test for LLM decision engine with real Claude.

This is a minimal test to verify Claude integration is working.

Run with: python tests/manual/test_llm_quick.py
"""

import logging
import tempfile
import time
from pathlib import Path

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Quick test of LLM integration."""
    print("\n" + "=" * 60)
    print("  Quick LLM Integration Test")
    print("=" * 60 + "\n")

    # Create temp directory for logs (avoid permission issues)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create resources
        wallet = MockWallet(initial_balance=100.0)
        compute = MockCompute(initial_hours=50.0)
        marketplace = MockMarketplace()

        # Configure with LLM engine
        config = {
            "engine_type": "llm",
            "llm_timeout": 120,  # 2 minutes
            "fallback_enabled": True,
        }

        logger.info("Creating AutonomousAgent with LLM engine...")
        agent = AutonomousAgent(wallet, compute, marketplace, config)

        # Override log directories to use temp dir
        agent.resource_tracker.log_dir = Path(tmpdir) / "resources"
        agent.resource_tracker.log_dir.mkdir(parents=True, exist_ok=True)
        agent.metrics_collector.log_dir = Path(tmpdir) / "metrics"
        agent.metrics_collector.log_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"State: balance=${agent.state.balance:.2f}, " f"compute={agent.state.compute_hours_remaining:.1f}h")

        # Run one cycle
        print("\nCalling Claude for decision (will take 1-2 minutes)...\n")

        start = time.time()
        result = agent.run_cycle()
        elapsed = time.time() - start

        # Show results
        print(f"\n✅ Decision completed in {elapsed:.2f}s")
        print("\nAllocation:")
        print(f"  Task work: {result['allocation']['task_work_hours']:.2f}h")
        print(f"  Company work: {result['allocation']['company_work_hours']:.2f}h")
        print(f"\nReasoning: {result['allocation']['reasoning']}")
        print(f"Confidence: {result['allocation']['confidence']:.2f}")

        # Check decision history
        if hasattr(agent.decision_engine, "get_decisions"):
            decisions = agent.decision_engine.get_decisions()
            if decisions:
                print(f"\nDecision logged: {decisions[0].decision_id}")
                print(f"Fallback used: {decisions[0].fallback_used}")

        print("\n✅ Test passed!")


if __name__ == "__main__":
    main()
