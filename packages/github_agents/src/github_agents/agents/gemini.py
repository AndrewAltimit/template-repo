"""Gemini AI agent implementation."""

import logging
from typing import Any, Dict, Optional

from .base import CLIAgent

logger = logging.getLogger(__name__)


class GeminiAgent(CLIAgent):
    """Gemini AI agent for code generation."""

    def __init__(self, config: Optional[Any] = None) -> None:
        """Initialize Gemini agent."""
        super().__init__("gemini", "gemini", timeout=300, config=config)

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Gemini."""
        return "Gemini"

    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code using Gemini.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Generated code or response
        """
        # Build command without model specification
        # Note: Gemini preview CLI uses best default model automatically
        # Specifying -m causes 404 errors
        cmd = ["gemini", "-p", prompt]

        stdout, _stderr = await self._execute_command(cmd)
        return stdout.strip()

    def get_priority(self) -> int:
        """Get priority for Gemini."""
        return 90
