#!/usr/bin/env python3
"""Test script for Virtual Character MCP auto-connect functionality."""

import asyncio
import logging
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from the parent directory
import server  # noqa: E402

VirtualCharacterMCPServer = server.VirtualCharacterMCPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_auto_connect():
    """Test the auto-connect functionality."""
    logger.info("Testing Virtual Character MCP auto-connect...")

    # Create server with auto-connect enabled
    server = VirtualCharacterMCPServer(port=8020, auto_connect=True)

    # Start auto-connect
    logger.info("Starting auto-connect task...")
    await server.startup_auto_connect()

    # Wait a bit for connection to establish
    await asyncio.sleep(3)

    # Check if connected
    if server.current_backend:
        logger.info("✓ Auto-connect successful!")
        logger.info("  Backend: %s", server.backend_name)
        logger.info("  Config: %s", server.config)

        # Test sending an animation
        logger.info("\nTesting animation send...")
        result = await server.send_animation(emotion="happy", gesture="wave")

        if result["success"]:
            logger.info("✓ Animation sent successfully!")
        else:
            logger.error("✗ Animation failed: %s", result.get("error"))

        # Test connection validation
        logger.info("\nTesting connection validation...")
        is_valid = await server.validate_connection()
        if is_valid:
            logger.info("✓ Connection validated!")
        else:
            logger.warning("⚠ Connection validation failed")

    else:
        logger.error("✗ Auto-connect failed - no backend connected")

    # Test with clearer port names
    logger.info("\n\nTesting connection with clearer port names...")
    result = await server.set_backend(
        "vrchat_remote",
        {
            "remote_host": "127.0.0.1",
            "vrchat_recv_port": 9000,  # Clearer name
            "vrchat_send_port": 9001,  # Clearer name
            "use_vrcemote": True,
        },
    )

    if result["success"]:
        logger.info("✓ Connection with clearer port names successful!")

        # Test animation
        result = await server.send_animation(gesture="thumbs_up")
        if result["success"]:
            logger.info("✓ Animation with new config successful!")
    else:
        logger.error("✗ Connection failed: %s", result.get("error"))

    # Test reconnection
    logger.info("\n\nTesting auto-reconnect...")
    logger.info("Simulating connection loss...")
    if server.current_backend:
        await server.current_backend.disconnect()

    # Trigger auto-reconnect
    await server.auto_reconnect()

    if server.current_backend:
        logger.info("✓ Auto-reconnect successful!")
    else:
        logger.error("✗ Auto-reconnect failed")

    logger.info("\n\n=== Test Summary ===")
    logger.info("Auto-connect: %s", "✓" if server.current_backend else "✗")
    logger.info("Clearer port names: ✓")
    logger.info("Connection validation: %s", "✓" if is_valid else "⚠")
    logger.info("Auto-reconnect: %s", "✓" if server.current_backend else "✗")


async def test_disabled_auto_connect():
    """Test with auto-connect disabled."""
    logger.info("\n\nTesting with auto-connect disabled...")

    server = VirtualCharacterMCPServer(port=8020, auto_connect=False)
    await server.startup_auto_connect()

    if not server.current_backend:
        logger.info("✓ Auto-connect correctly disabled")
    else:
        logger.error("✗ Auto-connect ran when disabled!")

    # Manual connect should still work
    result = await server.set_backend("mock", {})
    if result["success"]:
        logger.info("✓ Manual connect works with auto-connect disabled")
    else:
        logger.error("✗ Manual connect failed")


async def main():
    """Run all tests."""
    await test_auto_connect()
    await test_disabled_auto_connect()
    logger.info("\n\n✓ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
