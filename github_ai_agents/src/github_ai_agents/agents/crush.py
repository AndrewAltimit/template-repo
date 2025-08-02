"""Crush (mods) AI agent implementation."""

import logging
from typing import Any, Dict

from .base import CLIAgent

logger = logging.getLogger(__name__)


class CrushAgent(CLIAgent):
    """Crush AI agent for code generation."""

    def __init__(self):
        """Initialize Crush agent."""
        super().__init__("crush", "mods", timeout=300)

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Crush."""
        return "Crush"

    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code using Crush.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Generated code or response
        """
        # TODO: Implement Crush-specific logic
        cmd = ["mods", prompt]
        stdout, stderr = await self._execute_command(cmd)
        return stdout.strip()

    def get_priority(self) -> int:
        """Get priority for Crush."""
        return 60
