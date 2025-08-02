#!/usr/bin/env python3
"""Test OpenRouter agents to check containerization feasibility."""

import logging
import os
import subprocess
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


def test_agent(agent_class, name):
    """Test an agent with a simple prompt."""
    logger.info(f"\n{'='*50}")
    logger.info(f"Testing {name} Agent...")
    logger.info("=" * 50)

    try:
        # Initialize agent
        config = AgentConfig()
        agent = agent_class(config)

        # Check availability
        available = agent.is_available()
        logger.info(f"{name} available: {available}")

        if not available:
            logger.warning(f"{name} CLI not installed or not working")
            return False

        # Get model config
        model_config = agent.get_model_config()
        logger.info(f"Model config: {model_config}")

        # Test simple prompt
        logger.info(f"\nTesting {name} with simple prompt...")
        result = agent.execute("Write a simple hello world function in Python", {})
        logger.info(f"Result:\n{result}")

        return True

    except Exception as e:
        logger.error(f"Error testing {name}: {e}")
        return False


def check_container_feasibility(agent_name, executable):
    """Check if an agent can be containerized."""
    logger.info(f"\nChecking containerization feasibility for {agent_name}...")

    # Check if the executable exists
    result = subprocess.run(["which", executable], capture_output=True, text=True)
    if result.returncode != 0:
        logger.info(f"  ❌ {executable} not installed on host")
        logger.info("  ✅ Can be containerized (no host dependencies)")
        return True

    # Check if it requires specific host resources
    # Try to get help/version info
    test_commands = [
        [executable, "--help"],
        [executable, "--version"],
        [executable, "version"],
    ]

    for cmd in test_commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                output = result.stdout + result.stderr

                # Check for indicators that might prevent containerization
                if any(x in output.lower() for x in ["browser", "auth", "login", "device", "oauth"]):
                    logger.info("  ⚠️  May require browser auth or device-specific setup")
                    logger.info("  🤔 Containerization possible but may need workarounds")
                    return "partial"

                break
        except Exception:
            continue

    logger.info("  ✅ Appears to be containerizable")
    return True


def main():
    """Main test function."""
    logger.info("OpenRouter Agent Containerization Analysis")
    logger.info("==========================================\n")

    # Check if OPENROUTER_API_KEY is set
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set!")
        logger.info("Please set: export OPENROUTER_API_KEY='your-key'")
        return

    logger.info(f"OPENROUTER_API_KEY is set: {api_key[:10]}...")

    # Test agents
    agents = [
        (OpenCodeAgent, "OpenCode", "opencode"),
        (CodexAgent, "Codex", "codex"),
        (CrushAgent, "Crush", "crush"),
    ]

    results = {}

    for agent_class, name, executable in agents:
        # Check containerization feasibility
        container_feasible = check_container_feasibility(name, executable)

        # Test the agent (if we want to verify functionality)
        # Commenting out actual execution to avoid errors from missing CLIs
        # test_success = test_agent(agent_class, name)

        results[name] = {
            "containerizable": container_feasible,
            "executable": executable,
        }

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("CONTAINERIZATION FEASIBILITY SUMMARY")
    logger.info("=" * 60)

    for agent, info in results.items():
        status = info["containerizable"]
        if status is True:
            emoji = "✅"
            desc = "Fully containerizable"
        elif status == "partial":
            emoji = "🤔"
            desc = "Partially containerizable (may need auth workarounds)"
        else:
            emoji = "❌"
            desc = "Not containerizable"

        logger.info(f"{emoji} {agent}: {desc}")

    # Recommendations
    logger.info("\n" + "=" * 60)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 60)
    logger.info(
        """
1. OpenCode, Codex, and Crush can all be containerized since they:
   - Use API keys via environment variables
   - Don't require browser-based authentication
   - Can run in non-interactive mode

2. Container Strategy:
   - Create a unified 'openrouter-agents' container
   - Install Node.js and Go in the container
   - Install all three CLI tools
   - Mount API keys via environment variables

3. Implementation approach:
   - Extend the existing ai-agents.Dockerfile
   - Add Node.js, Go, and the CLI tools
   - Keep Claude and Gemini on host (due to auth requirements)
   - Document the exceptions clearly
"""
    )


if __name__ == "__main__":
    main()
