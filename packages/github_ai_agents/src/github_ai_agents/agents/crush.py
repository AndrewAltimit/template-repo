"""Crush AI agent implementation."""

import logging
import os
from typing import Any, Dict, List

from .containerized import ContainerizedCLIAgent

logger = logging.getLogger(__name__)


class CrushAgent(ContainerizedCLIAgent):
    """Crush AI agent for code generation."""

    def __init__(self, config=None):
        """Initialize Crush agent."""
        # Use the actual Crush CLI from Charm Bracelet
        super().__init__(
            "crush",
            "crush",
            docker_service="openrouter-agents",
            timeout=300,
            config=config,
        )

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

        # Log the command for debugging
        logger.info(f"Executing Crush command with {len(cmd)} parts")
        logger.debug(f"Full command: {cmd}")

        # Set up environment variables for execution
        env = {}
        if api_key := self.env_vars.get("OPENROUTER_API_KEY"):
            env["OPENROUTER_API_KEY"] = api_key
            env["OPENAI_API_KEY"] = api_key  # Some tools expect this format

        # Execute command
        try:
            stdout, stderr = await self._execute_command(cmd, env)
            return stdout.strip()
        except Exception as e:
            # Log more details about the error
            logger.error(f"Crush execution failed: {e}")
            if hasattr(e, "stdout"):
                logger.error(f"Stdout: {e.stdout}")
            if hasattr(e, "stderr"):
                logger.error(f"Stderr: {e.stderr}")
            raise

    def _build_command(self, prompt: str) -> List[str]:
        """Build Crush CLI command."""
        # Crush usage: crush run -q "prompt"
        # -q = quiet mode (no spinner)
        # Note: -y/--yolo only works in interactive mode, not with run command
        args = ["run", "-q"]

        # Add any additional flags from config
        if self.config:
            flags = self.config.get_non_interactive_flags("crush")
            # Filter out flags we're already adding and unsupported flags
            # Crush doesn't support --non-interactive or --no-update
            filtered_flags = [f for f in flags if f not in ["run", "-q", "-y", "--yolo", "--non-interactive", "--no-update"]]
            args.extend(filtered_flags)

        # Add the prompt as the last argument
        args.append(prompt)

        # Return just the command args, not the full docker command
        # The parent class _execute_command will handle Docker wrapping
        cmd = [self.executable]  # self.executable is "crush"
        cmd.extend(args)
        return cmd

    def get_priority(self) -> int:
        """Get priority for Crush."""
        return 60
