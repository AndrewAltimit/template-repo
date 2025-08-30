"""
Improvements to make Virtual Character MCP more robust and work out of the box.
This file contains the improved initialization code that should be integrated into server.py
"""

import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ImprovedVirtualCharacterServer:
    """Improvements for automatic connection and robustness"""

    def __init__(self, port: int = 8020, auto_connect: bool = True):
        # ... existing init code ...

        # Default configuration for auto-connect
        self.default_backend = "vrchat_remote"
        self.default_config = {
            "remote_host": "127.0.0.1",  # VRChat on same machine
            "vrchat_recv_port": 9000,  # CLEARER NAME: Port where VRChat receives
            "vrchat_send_port": 9001,  # CLEARER NAME: Port where VRChat sends
            "use_vrcemote": True,  # Most avatars use VRCEmote system
        }
        self.auto_connect = auto_connect
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3

    async def startup_auto_connect(self):
        """Auto-connect to default backend on server startup."""
        # Wait for server to fully initialize
        await asyncio.sleep(2)

        if not self.auto_connect:
            logger.info("Auto-connect disabled. Use set_backend() to connect manually.")
            return

        try:
            logger.info(f"Auto-connecting to {self.default_backend} backend...")
            logger.info(
                f"Configuration: VRChat at {self.default_config['remote_host']}:" f"{self.default_config['vrchat_recv_port']}"
            )

            result = await self.set_backend(self.default_backend, self.default_config)

            if result["success"]:
                logger.info(f"✓ Successfully auto-connected to {self.default_backend}")

                # Validate the connection works
                test_result = await self.validate_connection()
                if test_result:
                    logger.info("✓ Connection validated - OSC messages reaching VRChat")
                else:
                    logger.warning("⚠ Connection established but validation failed")
                    logger.info("Check that VRChat OSC is enabled and avatar supports VRCEmote")
            else:
                logger.warning(f"Failed to auto-connect: {result.get('error', 'Unknown error')}")
                logger.info("You can manually connect using set_backend()")

        except Exception as e:
            logger.error(f"Error during auto-connect: {e}")
            logger.info("You can manually connect using set_backend()")

    async def validate_connection(self) -> bool:
        """Validate that OSC messages actually reach VRChat."""
        if not self.current_backend:
            return False

        try:
            # Send a neutral reset to test connection
            from tools.mcp.virtual_character.models.canonical import CanonicalAnimationData, EmotionType, GestureType

            test_animation = CanonicalAnimationData(
                timestamp=0,
                emotion=EmotionType.NEUTRAL,
                gesture=GestureType.NONE,
            )

            success = await self.current_backend.send_animation_data(test_animation)

            if success:
                # Check if we can get stats (indicates healthy connection)
                stats = await self.current_backend.get_statistics()
                return stats.get("osc_messages_sent", 0) > 0

            return False

        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            return False

    async def monitor_connection(self):
        """Background task to monitor and auto-reconnect if needed."""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds

            if self.current_backend and self.auto_connect:
                try:
                    health = await self.current_backend.health_check()
                    if not health.get("connected", False):
                        logger.warning("Connection lost, attempting reconnect...")
                        await self.auto_reconnect()
                except Exception as e:
                    logger.error(f"Health check failed: {e}")
                    await self.auto_reconnect()

    async def auto_reconnect(self):
        """Attempt to reconnect to the backend."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached. Manual intervention required.")
            return

        self.reconnect_attempts += 1
        logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")

        # Try to reconnect with stored config
        if self.backend_name and self.config:
            result = await self.set_backend(self.backend_name, self.config)
            if result["success"]:
                logger.info("✓ Successfully reconnected")
                self.reconnect_attempts = 0
            else:
                logger.error(f"Reconnection failed: {result.get('error')}")

    def get_improved_port_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert clearer port names to internal format.
        Supports both old and new naming conventions.
        """
        improved_config = config.copy()

        # Support new clearer names
        if "vrchat_recv_port" in config:
            improved_config["osc_in_port"] = config["vrchat_recv_port"]
        if "vrchat_send_port" in config:
            improved_config["osc_out_port"] = config["vrchat_send_port"]

        # Default to sensible values if not specified
        if "osc_in_port" not in improved_config:
            improved_config["osc_in_port"] = 9000  # VRChat receives here
        if "osc_out_port" not in improved_config:
            improved_config["osc_out_port"] = 9001  # VRChat sends here

        return improved_config


# Startup function to be called in main
async def initialize_with_auto_connect(server):
    """Initialize server with auto-connect and monitoring."""
    # Start auto-connect
    asyncio.create_task(server.startup_auto_connect())

    # Start connection monitor
    asyncio.create_task(server.monitor_connection())

    logger.info("Virtual Character MCP Server initialized with auto-connect")
    logger.info("Default configuration:")
    logger.info("  - Backend: vrchat_remote")
    logger.info("  - VRChat Host: 127.0.0.1")
    logger.info("  - VRChat Receive Port: 9000")
    logger.info("  - VRChat Send Port: 9001")
    logger.info("  - VRCEmote System: Enabled")
