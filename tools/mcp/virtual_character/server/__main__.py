"""
Main entry point for Virtual Character MCP Server.
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import uvicorn

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import must be after sys.path modification
# pylint: disable=wrong-import-position
from tools.mcp.virtual_character.server.server import VirtualCharacterMCPServer  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


def handle_signal(sig, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)


async def main():
    """Main entry point."""
    # Get configuration from environment or defaults
    port = int(os.getenv("VIRTUAL_CHARACTER_PORT", "8020"))
    host = os.getenv("VIRTUAL_CHARACTER_HOST", "0.0.0.0")

    # Create server instance
    logger.info(f"Starting Virtual Character MCP Server on {host}:{port}")
    server = VirtualCharacterMCPServer(port=port)

    # Run startup tasks
    await server.startup()

    # Setup signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Run the server
    config = uvicorn.Config(app=server.app, host=host, port=port, log_level="info", access_log=True)

    server_instance = uvicorn.Server(config)

    try:
        await server_instance.serve()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        # Run shutdown tasks
        await server.shutdown()
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
