#!/usr/bin/env python3
"""Verify the containerized OpenRouter agents setup is complete and working."""

import logging
import os
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def check_environment():
    """Check environment variables and configuration."""
    logger.info("=== Environment Check ===")

    # Check OpenRouter API key
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if api_key:
        logger.info(f"✅ OPENROUTER_API_KEY is set: {api_key[:10]}...")
    else:
        logger.error("❌ OPENROUTER_API_KEY is not set")
        logger.info("   Please add to .env: OPENROUTER_API_KEY=your-key")
        return False

    # Check .agents.yaml
    agents_config = Path(".agents.yaml")
    if agents_config.exists():
        logger.info("✅ .agents.yaml configuration found")
        with open(agents_config) as f:
            content = f.read()
            if "opencode" in content and "codex" in content and "crush" in content:
                logger.info("✅ All containerized agents are configured")
            else:
                logger.warning("⚠️  Some agents may not be configured in .agents.yaml")
    else:
        logger.warning("⚠️  .agents.yaml not found - using defaults")
        logger.info("   Copy .agents.yaml.example to .agents.yaml to configure")

    return True


def check_docker_image():
    """Check if the openrouter-agents image is built."""
    logger.info("\n=== Docker Image Check ===")

    try:
        result = subprocess.run(
            ["docker", "images", "template-repo-openrouter-agents", "--format", "{{.Tag}}"], capture_output=True, text=True
        )

        if result.stdout.strip():
            logger.info("✅ openrouter-agents Docker image is built")
            return True
        else:
            logger.error("❌ openrouter-agents Docker image not found")
            logger.info("   Run: docker-compose build openrouter-agents")
            return False

    except Exception as e:
        logger.error(f"❌ Error checking Docker image: {e}")
        return False


def test_agent_availability():
    """Test if agents are available in the container."""
    logger.info("\n=== Agent Availability Test ===")

    agents = [("mods", "Crush/mods"), ("opencode", "OpenCode"), ("codex", "Codex")]

    all_available = True

    for cmd, name in agents:
        try:
            result = subprocess.run(
                ["docker-compose", "run", "--rm", "openrouter-agents", "which", cmd], capture_output=True, text=True
            )

            if result.returncode == 0:
                logger.info(f"✅ {name} CLI is available in container")
            else:
                logger.error(f"❌ {name} CLI not found in container")
                all_available = False

        except Exception as e:
            logger.error(f"❌ Error checking {name}: {e}")
            all_available = False

    return all_available


def test_simple_prompt():
    """Test a simple prompt with mods."""
    logger.info("\n=== Simple Prompt Test ===")

    try:
        result = subprocess.run(
            [
                "docker-compose",
                "run",
                "--rm",
                "-e",
                f"OPENROUTER_API_KEY={os.environ.get('OPENROUTER_API_KEY', '')}",
                "openrouter-agents",
                "mods",
                "--model",
                "openrouter/mistralai/mistral-7b-instruct",
                "--api",
                "https://openrouter.ai/api/v1",
                "--no-cache",
                "Say hello in one word",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            logger.info("✅ Simple prompt test passed")
            logger.info(f"   Response: {result.stdout.strip()}")
            return True
        else:
            logger.error("❌ Simple prompt test failed")
            logger.error(f"   Error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("❌ Simple prompt test timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Error running simple prompt test: {e}")
        return False


def test_python_integration():
    """Test Python integration with containerized agents."""
    logger.info("\n=== Python Integration Test ===")

    try:
        result = subprocess.run(
            [
                "docker-compose",
                "run",
                "--rm",
                "-e",
                f"OPENROUTER_API_KEY={os.environ.get('OPENROUTER_API_KEY', '')}",
                "openrouter-agents",
                "python",
                "scripts/agents/test_containerized_agents.py",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0 and "PASSED" in result.stdout:
            logger.info("✅ Python integration test passed")
            return True
        else:
            logger.error("❌ Python integration test failed")
            if result.stdout:
                logger.info("Output:")
                for line in result.stdout.split("\n")[-10:]:  # Last 10 lines
                    logger.info(f"  {line}")
            if result.stderr:
                logger.error("Error:")
                for line in result.stderr.split("\n")[-10:]:  # Last 10 lines
                    logger.error(f"  {line}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("❌ Python integration test timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Error running Python integration test: {e}")
        return False


def main():
    """Main verification function."""
    logger.info("Containerized OpenRouter Agents Setup Verification")
    logger.info("=" * 50)

    # Track overall success
    all_passed = True

    # Run checks
    if not check_environment():
        all_passed = False

    if not check_docker_image():
        all_passed = False
        logger.error("\n⚠️  Cannot continue without Docker image")
        return

    if not test_agent_availability():
        all_passed = False

    if os.environ.get("OPENROUTER_API_KEY"):
        if not test_simple_prompt():
            all_passed = False

        if not test_python_integration():
            all_passed = False
    else:
        logger.warning("\n⚠️  Skipping API tests - OPENROUTER_API_KEY not set")

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 50)

    if all_passed:
        logger.info("✅ All checks passed! Containerized agents are ready to use.")
        logger.info("\nYou can now:")
        logger.info("1. Run agents directly:")
        logger.info("   ./scripts/agents/run_containerized_agents.sh crush 'Your prompt'")
        logger.info("2. Use with monitors:")
        logger.info("   docker-compose run --rm openrouter-agents python scripts/agents/issue_monitor_multi_agent.py")
        logger.info("3. Test specific agents:")
        logger.info("   docker-compose run --rm openrouter-agents python scripts/agents/test_containerized_agents.py")
    else:
        logger.error("❌ Some checks failed. Please fix the issues above.")
        logger.info("\nCommon fixes:")
        logger.info("1. Set OPENROUTER_API_KEY in .env")
        logger.info("2. Build the container: docker-compose build openrouter-agents")
        logger.info("3. Copy .agents.yaml.example to .agents.yaml")
        sys.exit(1)


if __name__ == "__main__":
    main()
