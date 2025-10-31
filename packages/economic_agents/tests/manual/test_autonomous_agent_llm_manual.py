"""Manual test for AutonomousAgent with real Claude Code LLM integration.

This test requires:
1. Claude Code CLI installed (claude command available)
2. NVM installed with Node.js 22.16.0
3. Claude authentication configured

Run with: python tests/manual/test_autonomous_agent_llm_manual.py
"""

import asyncio
import logging
import sys
import time

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def print_separator(title: str):
    """Print a section separator."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


async def test_llm_agent_single_cycle():
    """Test AutonomousAgent with LLM engine for a single decision cycle."""
    print_separator("Test 1: Single LLM Decision Cycle")

    # Create resources
    wallet = MockWallet(initial_balance=100.0)
    compute = MockCompute(initial_hours=50.0)
    marketplace = MockMarketplace()

    # Configure agent with LLM engine
    config = {
        "engine_type": "llm",
        "llm_timeout": 120,  # 2 minutes for testing (not full 15)
        "fallback_enabled": True,
        "survival_buffer_hours": 24.0,
        "company_threshold": 100.0,
    }

    logger.info("Creating AutonomousAgent with LLM decision engine...")
    agent = AutonomousAgent(wallet, compute, marketplace, config)
    await agent.initialize()

    logger.info(
        f"Initial state: balance=${agent.state.balance:.2f}, "
        f"compute={agent.state.compute_hours_remaining:.1f}h, "
        f"mode={agent.state.mode}"
    )

    # Run one decision cycle
    print("\nRunning decision cycle with Claude Code CLI...")
    print("(This will take 1-2 minutes for Claude to respond)\n")

    start_time = time.time()
    try:
        result = await agent.run_cycle()
        elapsed = time.time() - start_time

        # Print results
        print(f"\n✅ Decision completed in {elapsed:.2f}s ({elapsed/60:.2f} min)")
        print("\nDecision Details:")
        print(f"  Task work: {result['allocation']['task_work_hours']:.2f}h")
        print(f"  Company work: {result['allocation']['company_work_hours']:.2f}h")
        print(f"  Reasoning: {result['allocation']['reasoning']}")
        print(f"  Confidence: {result['allocation']['confidence']:.2f}")

        if "task_result" in result:
            print(f"\nTask Result: {result['task_result']}")

        # Get decision history from LLM engine
        if hasattr(agent.decision_engine, "get_decisions"):
            decisions = agent.decision_engine.get_decisions()
            print(f"\nDecision History: {len(decisions)} decision(s)")

            for i, decision in enumerate(decisions):
                print(f"\nDecision {i+1}:")
                print(f"  ID: {decision.decision_id}")
                print(f"  Timestamp: {decision.timestamp}")
                print(f"  Execution time: {decision.execution_time_seconds:.2f}s")
                print(f"  Fallback used: {decision.fallback_used}")
                print(f"  Validation passed: {decision.validation_passed}")

        return True

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Test failed after {elapsed:.2f}s: {e}")
        logger.exception("Decision cycle failed")
        return False


async def test_llm_agent_multiple_cycles():
    """Test AutonomousAgent with LLM engine for multiple decision cycles."""
    print_separator("Test 2: Multiple LLM Decision Cycles")

    # Create resources
    wallet = MockWallet(initial_balance=200.0)
    compute = MockCompute(initial_hours=100.0)
    marketplace = MockMarketplace()

    # Configure agent with LLM engine
    config = {
        "engine_type": "llm",
        "llm_timeout": 120,  # 2 minutes per decision
        "fallback_enabled": True,
        "survival_buffer_hours": 24.0,
        "company_threshold": 150.0,
        "mode": "company",  # Company mode
    }

    logger.info("Creating AutonomousAgent with LLM engine (company mode)...")
    agent = AutonomousAgent(wallet, compute, marketplace, config)
    await agent.initialize()

    logger.info(
        f"Initial state: balance=${agent.state.balance:.2f}, "
        f"compute={agent.state.compute_hours_remaining:.1f}h, "
        f"mode={agent.state.mode}"
    )

    # Run 3 decision cycles
    num_cycles = 3
    print(f"\nRunning {num_cycles} decision cycles with Claude...")
    print("(This will take 3-6 minutes total)\n")

    start_time = time.time()
    try:
        decisions = await agent.run(max_cycles=num_cycles)
        elapsed = time.time() - start_time

        print(f"\n✅ Completed {len(decisions)} cycles in {elapsed:.2f}s ({elapsed/60:.2f} min)")
        print(f"   Average: {elapsed/len(decisions):.2f}s per cycle")

        # Print summary of each decision
        for i, decision in enumerate(decisions):
            print(f"\nCycle {i+1}:")
            print(f"  Task work: {decision['allocation']['task_work_hours']:.2f}h")
            print(f"  Company work: {decision['allocation']['company_work_hours']:.2f}h")
            print(f"  Reasoning: {decision['allocation']['reasoning'][:80]}...")
            print(f"  Confidence: {decision['allocation']['confidence']:.2f}")

        # Final agent state
        print("\nFinal Agent State:")
        print(f"  Balance: ${agent.state.balance:.2f}")
        print(f"  Compute remaining: {agent.state.compute_hours_remaining:.1f}h")
        print(f"  Tasks completed: {agent.state.tasks_completed}")
        print(f"  Company formed: {agent.state.has_company}")

        # Get LLM decision history
        if hasattr(agent.decision_engine, "get_decisions"):
            llm_decisions = agent.decision_engine.get_decisions()
            print(f"\nLLM Decision History: {len(llm_decisions)} decision(s)")

            fallback_count = sum(1 for d in llm_decisions if d.fallback_used)
            print(f"  Fallback used: {fallback_count}/{len(llm_decisions)}")

            avg_exec_time = sum(d.execution_time_seconds for d in llm_decisions) / len(llm_decisions)
            print(f"  Average execution time: {avg_exec_time:.2f}s")

        return True

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Test failed after {elapsed:.2f}s: {e}")
        logger.exception("Multiple cycles failed")
        return False


async def test_fallback_on_short_timeout():
    """Test that fallback kicks in when timeout is very short."""
    print_separator("Test 3: Fallback Behavior (Short Timeout)")

    # Create resources
    wallet = MockWallet(initial_balance=100.0)
    compute = MockCompute(initial_hours=50.0)
    marketplace = MockMarketplace()

    # Configure with very short timeout to trigger fallback
    config = {
        "engine_type": "llm",
        "llm_timeout": 5,  # 5 seconds - likely to timeout
        "fallback_enabled": True,
        "survival_buffer_hours": 24.0,
    }

    logger.info("Creating agent with 5-second timeout (should fallback)...")
    agent = AutonomousAgent(wallet, compute, marketplace, config)
    await agent.initialize()

    start_time = time.time()
    try:
        result = await agent.run_cycle()
        elapsed = time.time() - start_time

        print(f"\n✅ Decision completed in {elapsed:.2f}s")

        # Check if fallback was used
        if hasattr(agent.decision_engine, "get_decisions"):
            decisions = agent.decision_engine.get_decisions()
            if decisions:
                fallback_used = decisions[0].fallback_used
                print(f"\nFallback used: {fallback_used}")

                if fallback_used:
                    print("✅ Fallback mechanism worked correctly!")
                    print("\nFallback Decision:")
                    print(f"  Task work: {result['allocation']['task_work_hours']:.2f}h")
                    print(f"  Company work: {result['allocation']['company_work_hours']:.2f}h")
                    print(f"  Reasoning: {result['allocation']['reasoning']}")
                else:
                    print("⚠️  Claude responded faster than timeout - no fallback needed")

        return True

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ Test failed after {elapsed:.2f}s: {e}")
        logger.exception("Fallback test failed")
        return False


async def test_comparison_llm_vs_rule_based():
    """Compare decisions between LLM and rule-based engines."""
    print_separator("Test 4: LLM vs Rule-Based Comparison")

    # Same initial conditions
    initial_balance = 100.0
    initial_compute = 50.0

    # Test with rule-based engine
    print("Running with rule-based engine...")
    wallet_rb = MockWallet(initial_balance=initial_balance)
    compute_rb = MockCompute(initial_hours=initial_compute)
    marketplace_rb = MockMarketplace()

    config_rb = {
        "engine_type": "rule_based",
        "survival_buffer_hours": 24.0,
    }

    agent_rb = AutonomousAgent(wallet_rb, compute_rb, marketplace_rb, config_rb)
    await agent_rb.initialize()
    result_rb = await agent_rb.run_cycle()

    print("\nRule-Based Decision:")
    print(f"  Task work: {result_rb['allocation']['task_work_hours']:.2f}h")
    print(f"  Company work: {result_rb['allocation']['company_work_hours']:.2f}h")
    print(f"  Reasoning: {result_rb['allocation']['reasoning']}")

    # Test with LLM engine
    print("\nRunning with LLM engine (Claude)...")
    wallet_llm = MockWallet(initial_balance=initial_balance)
    compute_llm = MockCompute(initial_hours=initial_compute)
    marketplace_llm = MockMarketplace()

    config_llm = {
        "engine_type": "llm",
        "llm_timeout": 120,
        "fallback_enabled": True,
        "survival_buffer_hours": 24.0,
    }

    agent_llm = AutonomousAgent(wallet_llm, compute_llm, marketplace_llm, config_llm)
    await agent_llm.initialize()

    start_time = time.time()
    result_llm = await agent_llm.run_cycle()
    elapsed = time.time() - start_time

    print(f"\nLLM Decision (took {elapsed:.2f}s):")
    print(f"  Task work: {result_llm['allocation']['task_work_hours']:.2f}h")
    print(f"  Company work: {result_llm['allocation']['company_work_hours']:.2f}h")
    print(f"  Reasoning: {result_llm['allocation']['reasoning']}")
    print(f"  Confidence: {result_llm['allocation']['confidence']:.2f}")

    # Compare
    print("\nComparison:")
    task_diff = result_llm["allocation"]["task_work_hours"] - result_rb["allocation"]["task_work_hours"]
    company_diff = result_llm["allocation"]["company_work_hours"] - result_rb["allocation"]["company_work_hours"]

    print(f"  Task work difference: {task_diff:+.2f}h")
    print(f"  Company work difference: {company_diff:+.2f}h")

    if abs(task_diff) < 0.01 and abs(company_diff) < 0.01:
        print("  ⚠️  Decisions are identical (may indicate Claude using similar logic)")
    else:
        print("  ✅ Decisions differ (Claude showing autonomous reasoning)")

    return True


async def main():
    """Run all manual tests."""
    print("\n" + "=" * 80)
    print("  AutonomousAgent + LLM Integration Manual Tests")
    print("=" * 80)
    print("\nThese tests require Claude Code CLI to be installed and configured.")
    print("Tests will make real calls to Claude (may take several minutes).\n")

    response = input("Continue with tests? (y/n): ")
    if response.lower() != "y":
        print("Tests cancelled.")
        return

    results = []

    # Run tests
    print("\n" + "🚀 Starting manual tests...\n")

    results.append(("Single LLM Cycle", await test_llm_agent_single_cycle()))
    results.append(("Multiple LLM Cycles", await test_llm_agent_multiple_cycles()))
    results.append(("Fallback Behavior", await test_fallback_on_short_timeout()))
    results.append(("LLM vs Rule-Based", await test_comparison_llm_vs_rule_based()))

    # Summary
    print_separator("Test Summary")

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed_count}/{total} tests passed")

    if passed_count == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
