"""OpenCode AI agent implementation."""

import json
import logging
import os
from typing import Any, Dict, List

from .containerized import ContainerizedCLIAgent

logger = logging.getLogger(__name__)


class OpenCodeAgent(ContainerizedCLIAgent):
    """OpenCode AI agent for code generation."""

    DEFAULT_MODEL = "qwen/qwen-2.5-coder-32b-instruct"

    def __init__(self, config=None) -> None:
        """Initialize OpenCode agent."""
        super().__init__("opencode", "opencode", docker_service="openrouter-agents", timeout=300, config=config)

        # Set up environment variables
        if api_key := os.environ.get("OPENROUTER_API_KEY"):
            self.env_vars["OPENROUTER_API_KEY"] = api_key
            self.env_vars["OPENCODE_MODEL"] = self.DEFAULT_MODEL

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for OpenCode."""
        return "OpenCode"

    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code using OpenCode.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Generated code or response
        """
        # Build full prompt with context
        full_prompt = prompt
        if code := context.get("code"):
            full_prompt = f"Code Context:\n```\n{code}\n```\n\nTask: {prompt}"

        # Build command
        cmd = self._build_command(full_prompt)

        # Execute command
        stdout, stderr = await self._execute_command(cmd)

        # Parse output
        return self._parse_output(stdout, stderr)

    def _build_command(self, prompt: str) -> List[str]:
        """Build OpenCode CLI command."""
        # Get flags from config or use defaults
        if self.config:
            flags = self.config.get_non_interactive_flags("opencode")
        else:
            flags = ["--non-interactive"]  # Default non-interactive mode

        # Build command with proper order
        args = []
        args.extend(flags)
        args.extend(["-p", prompt])

        # Use Docker if available (preferred), otherwise local
        if self._use_docker:
            # Build Docker command with environment variables
            env_vars = {}
            if api_key := self.env_vars.get("OPENROUTER_API_KEY"):
                env_vars["OPENROUTER_API_KEY"] = api_key
            return self._build_docker_command(args, env_vars)
        else:
            # Use local executable
            cmd = [self.executable]
            cmd.extend(args)
            return cmd

    def _parse_output(self, output: str, error: str) -> str:
        """Parse OpenCode output."""
        output = output.strip()

        # Log the raw output for debugging
        logger.debug(f"OpenCode raw output: {output[:500]}...")
        if error:
            logger.debug(f"OpenCode stderr: {error[:500]}...")

        # Try to parse as JSON if it looks like JSON
        if output.startswith("{") and output.endswith("}"):
            try:
                data = json.loads(output)
                return str(data.get("code", data.get("response", output)))
            except json.JSONDecodeError:
                pass

        return output

    def get_capabilities(self) -> List[str]:
        """Get OpenCode capabilities."""
        return [
            "code_generation",
            "code_review",
            "refactoring",
            "multi_session",
            "lsp_integration",
            "plan_mode",
            "openrouter_models",
        ]

    def get_priority(self) -> int:
        """Get priority for OpenCode."""
        return 80  # High priority as open-source alternative
