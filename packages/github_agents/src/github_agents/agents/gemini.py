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
        # Build command with explicit model selection via API key
        # Get model from config
        if self.config:
            model_config = self.config.get_model_config("gemini")
            model = model_config.get("default_model", "gemini-3-pro-preview")
        else:
            model = "gemini-3-pro-preview"

        # Note: gemini prompt reads from stdin when no prompt argument is provided
        # We need to use subprocess directly to pass stdin
        import asyncio
        import os

        env = os.environ.copy()
        env.update(self.env_vars)

        cmd = ["gemini", "prompt", "--model", model, "--output-format", "text"]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(input=prompt.encode("utf-8")), timeout=self.timeout)

            if proc.returncode != 0:
                from .base import AgentExecutionError

                raise AgentExecutionError(self.name, proc.returncode or -1, stdout.decode("utf-8"), stderr.decode("utf-8"))

            return stdout.decode("utf-8").strip()

        except asyncio.TimeoutError as exc:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()

            from .base import AgentTimeoutError

            raise AgentTimeoutError(self.name, self.timeout) from exc
        except FileNotFoundError as exc:
            from .base import AgentExecutionError

            raise AgentExecutionError(self.name, -1, "", "Executable 'gemini' not found") from exc

    def get_priority(self) -> int:
        """Get priority for Gemini."""
        return 90
