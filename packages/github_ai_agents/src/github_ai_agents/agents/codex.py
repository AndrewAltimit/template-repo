"""Codex AI agent implementation."""

import logging
import os
from typing import Any, Dict, List

from .containerized import ContainerizedCLIAgent

logger = logging.getLogger(__name__)


class CodexAgent(ContainerizedCLIAgent):
    """Codex AI agent for code generation."""

    def __init__(self, config=None):
        """Initialize Codex agent."""
        # Use the actual Codex CLI from @openai/codex npm package
        super().__init__("codex", "codex", docker_service="openrouter-agents", timeout=300, config=config)

        # Set up environment variables
        if api_key := os.environ.get("OPENROUTER_API_KEY"):
            self.env_vars["OPENROUTER_API_KEY"] = api_key

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
        # Build command
        cmd = self._build_command(prompt)

        # Execute command
        stdout, stderr = await self._execute_command(cmd)
        return stdout.strip()

    def _build_command(self, prompt: str) -> List[str]:
        """Build Codex CLI command."""
        # Codex CLI usage: codex exec [OPTIONS] [PROMPT]
        # Use exec subcommand for non-interactive execution
        args = ["exec"]

        # Add any flags from config
        if self.config:
            flags = self.config.get_non_interactive_flags("codex")
            args.extend(flags)

        # Add the prompt
        args.append(prompt)

        # Use Docker if available (preferred), otherwise local
        if self._use_docker:
            # Build Docker command with environment variables
            env_vars = {}
            # Codex likely needs OPENAI_API_KEY for authentication
            if api_key := os.environ.get("OPENAI_API_KEY"):
                env_vars["OPENAI_API_KEY"] = api_key
            elif api_key := self.env_vars.get("OPENROUTER_API_KEY"):
                # Try using OpenRouter key as OpenAI key
                env_vars["OPENAI_API_KEY"] = api_key
            return self._build_docker_command(args, env_vars)
        else:
            # Use local executable
            cmd = [self.executable]
            cmd.extend(args)
            return cmd

    def get_priority(self) -> int:
        """Get priority for Codex."""
        return 70
