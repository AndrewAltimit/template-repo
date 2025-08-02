"""Codex AI agent implementation."""

import logging
from typing import Any, Dict

from .base import CLIAgent

logger = logging.getLogger(__name__)


class CodexAgent(CLIAgent):
    """Codex AI agent for code generation."""

    def __init__(self):
        """Initialize Codex agent."""
        super().__init__("codex", "codex", timeout=300)

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Codex."""
        return "Codex"

    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code using Codex.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Generated code or response
        """
        # TODO: Implement Codex-specific logic
        cmd = ["codex", prompt]
        stdout, stderr = await self._execute_command(cmd)
        return stdout.strip()

    def get_priority(self) -> int:
        """Get priority for Codex."""
        return 70
