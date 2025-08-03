"""Crush (mods) AI agent implementation."""

import logging
import os
from typing import Any, Dict, List

from .containerized import ContainerizedCLIAgent

logger = logging.getLogger(__name__)


class CrushAgent(ContainerizedCLIAgent):
    """Crush AI agent for code generation."""

    def __init__(self, config=None):
        """Initialize Crush agent."""
        super().__init__("crush", "mods", docker_service="openrouter-agents", timeout=300, config=config)

        # Set up environment variables
        if api_key := os.environ.get("OPENROUTER_API_KEY"):
            self.env_vars["OPENROUTER_API_KEY"] = api_key

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
        # Build command
        cmd = self._build_command(prompt)

        # Execute command
        stdout, stderr = await self._execute_command(cmd)
        return stdout.strip()

    def _build_command(self, prompt: str) -> List[str]:
        """Build Crush/mods CLI command."""
        # Get flags from config or use defaults
        if self.config:
            flags = self.config.get_non_interactive_flags("crush")
        else:
            flags = []

        # Prepare arguments
        args = list(flags)
        args.append(prompt)

        # Use Docker if available (preferred), otherwise local
        if self._use_docker:
            # Build Docker command with environment variables
            env_vars = {}
            if api_key := self.env_vars.get("OPENROUTER_API_KEY"):
                env_vars["OPENROUTER_API_KEY"] = api_key
            return self._build_docker_command(args, env_vars)
        else:
            # Use local executable
            cmd = [self.executable]  # self.executable is "mods"
            cmd.extend(args)
            return cmd

    def get_priority(self) -> int:
        """Get priority for Crush."""
        return 60
