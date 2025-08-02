#!/usr/bin/env python3
"""Test script for the multi-agent system."""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agents.core.config_loader import AgentConfig  # noqa: E402
from scripts.agents.implementations import ClaudeAgent, GeminiAgent  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_claude_agent():
    """Test Claude agent functionality."""
    logger.info("Testing Claude agent...")

    agent = ClaudeAgent()

    # Check availability
    if not agent.is_available():
        logger.error("Claude agent is not available. Please ensure Claude CLI is installed and authenticated.")
        return False

    logger.info(f"Claude agent available: {agent.is_available()}")
    logger.info(f"Trigger keyword: {agent.get_trigger_keyword()}")
    logger.info(f"Model config: {agent.get_model_config()}")
    logger.info(f"Capabilities: {agent.get_capabilities()}")

    # Test code generation
    try:
        logger.info("Testing code generation...")
        prompt = "Write a Python function that calculates the fibonacci sequence up to n terms"
        response = await agent.generate_code(prompt, {})
        logger.info(f"Generated code:\n{response}")

        # Test code review
        logger.info("\nTesting code review...")
        code = """
def fibonacci(n):
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib
"""
        review = await agent.review_code(code, "Check for efficiency and edge cases")
        logger.info(f"Code review:\n{review}")

        return True

    except Exception as e:
        logger.error(f"Error testing Claude agent: {e}")
        return False


async def test_gemini_agent():
    """Test Gemini agent functionality."""
    logger.info("Testing Gemini agent...")

    agent = GeminiAgent()

    # Check availability
    if not agent.is_available():
        logger.warning("Gemini agent is not available. Please ensure Gemini CLI is installed and authenticated.")
        logger.info("Install with: npm install -g @google/gemini-cli")
        logger.info("Authenticate with: gemini")
        return False

    logger.info(f"Gemini agent available: {agent.is_available()}")
    logger.info(f"Trigger keyword: {agent.get_trigger_keyword()}")
    logger.info(f"Model config: {agent.get_model_config()}")
    logger.info(f"Capabilities: {agent.get_capabilities()}")

    # Test code generation
    try:
        logger.info("Testing code generation...")
        prompt = "Write a Python function that checks if a string is a palindrome"
        response = await agent.generate_code(prompt, {})
        logger.info(f"Generated code:\n{response}")

        # Test code review
        logger.info("\nTesting code review...")
        code = """
def is_palindrome(s):
    return s == s[::-1]
"""
        review = await agent.review_code(code, "Review for edge cases and improvements")
        logger.info(f"Code review:\n{review}")

        return True

    except Exception as e:
        logger.error(f"Error testing Gemini agent: {e}")
        return False


async def test_config_loader():
    """Test configuration loader."""
    logger.info("\nTesting configuration loader...")

    config = AgentConfig()

    logger.info(f"Config path: {config.config_path}")
    logger.info(f"Enabled agents: {config.get_enabled_agents()}")
    logger.info(f"Issue creation priorities: {config.get_agent_priority('issue_creation')}")
    logger.info(f"PR review priorities: {config.get_agent_priority('pr_reviews')}")
    logger.info(f"OpenRouter config: {config.get_openrouter_config()}")

    return True


async def main():
    """Run all tests."""
    logger.info("Starting multi-agent system tests...\n")

    # Test configuration
    config_ok = await test_config_loader()

    # Test Claude agent
    claude_ok = await test_claude_agent()

    # Test Gemini agent
    gemini_ok = await test_gemini_agent()

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("Test Summary:")
    logger.info(f"Configuration loader: {'✅ PASS' if config_ok else '❌ FAIL'}")
    logger.info(f"Claude agent: {'✅ PASS' if claude_ok else '❌ FAIL'}")
    logger.info(f"Gemini agent: {'✅ PASS' if gemini_ok else '❌ FAIL'}")

    all_pass = config_ok and claude_ok
    if gemini_ok:
        all_pass = all_pass and gemini_ok

    return all_pass


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
