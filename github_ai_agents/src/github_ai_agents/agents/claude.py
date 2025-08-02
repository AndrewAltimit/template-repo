"""Claude AI agent implementation."""

import logging
from typing import Any, Dict

from .base import CLIAgent

logger = logging.getLogger(__name__)


class ClaudeAgent(CLIAgent):
    """Claude AI agent for code generation."""

    def __init__(self, config=None):
        """Initialize Claude agent."""
        super().__init__("claude", "claude", timeout=600, config=config)

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Claude."""
        return "Claude"

    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code using Claude.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Generated code or response
        """
        # Use non-interactive flags from config if available
        if self.config:
            flags = self.config.get_non_interactive_flags("claude")
        else:
            flags = ["--print", "--dangerously-skip-permissions"]

        cmd = ["claude"] + flags + [prompt]
        stdout, stderr = await self._execute_command(cmd)
        return stdout.strip()

    def get_priority(self) -> int:
        """Get priority for Claude."""
        return 90  # Highest priority
