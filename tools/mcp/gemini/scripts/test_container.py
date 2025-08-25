#!/usr/bin/env python3
"""Test script for containerized Gemini MCP server"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Direct import of the integration module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path setup to avoid E402
# pylint: disable=wrong-import-position
from gemini_integration import GeminiIntegration  # noqa: E402

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_container_mode():
    """Test Gemini integration in container mode"""

    # Configure for container mode
    config = {
        "enabled": True,
        "use_container": True,
        "container_image": "google/gemini-cli:latest",  # Use simple container for testing
        "timeout": 60,
        "yolo_mode": False,  # Interactive mode for testing
    }

    gemini = GeminiIntegration(config)

    print("🧪 Testing Gemini MCP in Container Mode")
    print("=" * 50)
    print("")

    # Test 1: Simple query
    print("Test 1: Simple Query")
    print("-" * 30)

    result = await gemini.consult_gemini(
        query="What is 2 + 2?", context="This is a simple math test", comparison_mode=False, force_consult=True
    )

    print(f"Status: {result.get('status')}")
    if result.get("status") == "success":
        print(f"Response: {result.get('response', '')[:200]}...")
        print(f"Execution time: {result.get('execution_time', 0):.2f}s")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    print("")

    # Test 2: Multi-line query
    print("Test 2: Multi-line Query")
    print("-" * 30)

    multiline_query = """Please analyze the following Python code:

def factorial(n):
    if n == 0:
        return 1
    else:
        return n * factorial(n - 1)

Is this implementation correct? What are its limitations?"""

    result = await gemini.consult_gemini(query=multiline_query, context="", comparison_mode=True, force_consult=True)

    print(f"Status: {result.get('status')}")
    if result.get("status") == "success":
        print(f"Response: {result.get('response', '')[:200]}...")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    print("")
    print("✅ Container mode tests completed")


async def test_direct_mode():
    """Test Gemini integration in direct mode (host)"""

    # Configure for direct mode
    config = {
        "enabled": True,
        "use_container": False,
        "cli_command": "gemini",
        "timeout": 60,
    }

    gemini = GeminiIntegration(config)

    print("")
    print("🧪 Testing Gemini MCP in Direct Mode (Host)")
    print("=" * 50)
    print("")

    result = await gemini.consult_gemini(
        query="What is the capital of France?", context="", comparison_mode=False, force_consult=True
    )

    print(f"Status: {result.get('status')}")
    if result.get("status") == "success":
        print(f"Response: {result.get('response', '')[:200]}...")
        print(f"Execution time: {result.get('execution_time', 0):.2f}s")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    print("")
    print("✅ Direct mode test completed")


async def main():
    """Main test function"""

    # Check if container image exists
    print("🔍 Checking for container image...")
    check_cmd = await asyncio.create_subprocess_exec(
        "docker",
        "image",
        "inspect",
        "google/gemini-cli:latest",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await check_cmd.wait()

    if check_cmd.returncode != 0:
        print("⚠️  Container image 'google/gemini-cli:latest' not found")
        print("Building container image...")

        # Try to build/pull the image
        build_cmd = await asyncio.create_subprocess_exec(
            "docker", "pull", "google/gemini-cli:latest", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await build_cmd.communicate()

        if build_cmd.returncode != 0:
            print("Could not pull official image, will build local version")
            # The build command from run_gemini_container.sh
            print("Please run: ./tools/cli/containers/run_gemini_container.sh")
            print("")
            print("Falling back to direct mode test only...")
            await test_direct_mode()
            return
    else:
        print("✅ Container image found")

    print("")

    # Test container mode
    await test_container_mode()

    # Also test direct mode if available
    print("")
    print("Testing direct mode for comparison...")
    await test_direct_mode()


if __name__ == "__main__":
    asyncio.run(main())
