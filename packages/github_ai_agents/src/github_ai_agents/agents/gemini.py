"""Gemini AI agent implementation."""

import logging
from typing import Any, Dict

from .base import CLIAgent

logger = logging.getLogger(__name__)


class GeminiAgent(CLIAgent):
    """Gemini AI agent for code generation."""

    def __init__(self, config=None):
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
        # Build command with proper model selection
        cmd = ["gemini"]

        # Get model configuration
        if self.config:
            model_config = self.config.get_model_config("gemini")
            default_model = model_config.get("default_model", "gemini-2.5-pro")

            # Add model flag
            cmd.extend(["-m", default_model])

            # Add prompt flag
            cmd.extend(["-p", prompt])
        else:
            # Fallback to simple command
            cmd.append(prompt)

        stdout, stderr = await self._execute_command(cmd)
        return stdout.strip()

    def get_priority(self) -> int:
        """Get priority for Gemini."""
        return 85
