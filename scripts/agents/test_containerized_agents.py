#!/usr/bin/env python3
"""Test containerized OpenRouter agents (OpenCode, Codex, Crush)."""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agents.core.config_loader import AgentConfig  # noqa: E402
from scripts.agents.implementations.codex_agent import CodexAgent  # noqa: E402
from scripts.agents.implementations.crush_agent import CrushAgent  # noqa: E402
from scripts.agents.implementations.opencode_agent import OpenCodeAgent  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_agent_async(agent_class, name, test_prompt):
    """Test an agent with a simple prompt asynchronously."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing {name} Agent...")
    logger.info("=" * 60)

    try:
        # Initialize agent
        config = AgentConfig()
        agent = agent_class(config)

        # Check availability
        available = agent.is_available()
        logger.info(f"{name} available: {available}")

        if not available:
            logger.warning(f"{name} CLI not installed or not working")
            return False, f"{name} not available"

        # Get model config
        model_config = agent.get_model_config()
        logger.info(f"Model config: {model_config}")

        # Test simple prompt
        logger.info(f"\nTesting {name} with prompt: {test_prompt}")
        result = await agent.generate_code(test_prompt, {})
        logger.info(f"Result:\n{result}")

        return True, result

    except Exception as e:
        logger.error(f"Error testing {name}: {e}")
        import traceback

        traceback.print_exc()
        return False, str(e)


async def main():
    """Main test function."""
    logger.info("Containerized OpenRouter Agent Test")
    logger.info("===================================\n")

    # Check if OPENROUTER_API_KEY is set
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set!")
        logger.info("Please set: export OPENROUTER_API_KEY='your-key'")
        return

    logger.info(f"OPENROUTER_API_KEY is set: {api_key[:10]}...")

    # Test prompts for each agent
    test_cases = [
        (OpenCodeAgent, "OpenCode", "Write a Python function to calculate fibonacci numbers"),
        (CodexAgent, "Codex", "Create a simple REST API endpoint in Python using Flask"),
        (CrushAgent, "Crush", "Write a bash script to backup files to a remote server"),
    ]

    results = {}

    # Run tests
    for agent_class, name, prompt in test_cases:
        success, result = await test_agent_async(agent_class, name, prompt)
        results[name] = {"success": success, "result": result[:200] if success else result}

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    all_passed = True
    for agent, info in results.items():
        status = "✅ PASSED" if info["success"] else "❌ FAILED"
        logger.info(f"{agent}: {status}")
        if not info["success"]:
            logger.info(f"  Error: {info['result']}")
            all_passed = False

    if all_passed:
        logger.info("\n🎉 All containerized agents are working correctly!")
        logger.info("\nYou can now use these agents with:")
        logger.info("  docker-compose run --rm openrouter-agents python scripts/agents/run_agents.py")
    else:
        logger.info("\n⚠️  Some agents failed. Check the errors above.")

    # Test integration with github_ai_agents package
    logger.info("\n" + "=" * 60)
    logger.info("GITHUB_AI_AGENTS PACKAGE INTEGRATION TEST")
    logger.info("=" * 60)

    try:
        from github_ai_agents.monitors import IssueMonitor

        monitor = IssueMonitor()
        available_agents = list(monitor.agents.keys())

        logger.info(f"Available agents in github_ai_agents package: {available_agents}")

        # Check if our containerized agents are available
        containerized = ["opencode", "codex", "crush"]
        for agent_name in containerized:
            if agent_name in available_agents:
                logger.info(f"✅ {agent_name} is integrated with github_ai_agents package")
            else:
                logger.info(f"❌ {agent_name} is NOT integrated with github_ai_agents package")

    except Exception as e:
        logger.error(f"Failed to test github_ai_agents integration: {e}")


if __name__ == "__main__":
    asyncio.run(main())
