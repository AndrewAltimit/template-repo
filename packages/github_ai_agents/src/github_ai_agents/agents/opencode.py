"""OpenCode AI agent implementation."""

import json
import logging
import os
from typing import Any, Dict, List

from .base import AgentExecutionError
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
            logger.info(f"OpenCode initialized with API key: {'*' * 10}{api_key[-4:]}")
        else:
            logger.warning("OPENROUTER_API_KEY not found in environment - OpenCode may not work properly")

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

        # Build command with prompt
        cmd = self._build_command(full_prompt)

        # Log the command being executed (show more for debugging)
        logger.info(f"Full prompt length: {len(full_prompt)} chars")
        logger.info(f"Executing OpenCode command with {len(cmd)} parts")
        # Log last few parts of command to see the actual prompt
        logger.info(f"Command ending: ...{' '.join(cmd[-5:])}")
        logger.debug(f"Full command: {cmd}")

        # Execute command directly
        try:
            stdout, stderr = await self._execute_command(cmd)
            # Parse output
            return self._parse_output(stdout, stderr)
        except AgentExecutionError as e:
            # Log the actual error output
            logger.error(f"OpenCode execution failed with exit code {e.exit_code}")
            if e.stdout:
                logger.error(f"OpenCode stdout: {e.stdout}")
            if e.stderr:
                logger.error(f"OpenCode stderr: {e.stderr}")
            # Re-raise the error with more context
            raise AgentExecutionError(
                self.name, e.exit_code, e.stdout, e.stderr or "No error output from opencode command"
            )

    def _build_command(self, prompt: str) -> List[str]:
        """Build OpenCode CLI command."""
        # OpenCode uses 'run' subcommand
        args = ["run"]

        # Add model flag if we have a model configured
        if self.DEFAULT_MODEL:
            args.extend(["-m", f"openrouter/{self.DEFAULT_MODEL}"])

        # OpenCode expects the message as the last positional argument
        # Since we're using asyncio.create_subprocess_exec (no shell),
        # we don't need to escape - just pass the prompt as-is
        # For debugging: log if multi-line prompt with Docker
        if self._use_docker and "\n" in prompt:
            logger.warning("Multi-line prompt detected with Docker - this may cause issues")
        args.append(prompt)

        # Use Docker if available (preferred), otherwise local
        if self._use_docker:
            # Build Docker command with environment variables
            env_vars = {}
            if api_key := self.env_vars.get("OPENROUTER_API_KEY"):
                env_vars["OPENROUTER_API_KEY"] = api_key
                env_vars["OPENCODE_MODEL"] = self.env_vars.get("OPENCODE_MODEL", self.DEFAULT_MODEL)
            else:
                logger.warning("No OPENROUTER_API_KEY found when building Docker command")
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
        logger.info(f"OpenCode raw output length: {len(output)}")
        logger.info(f"OpenCode raw output:\n{output[:1000]}...")
        if error:
            logger.info(f"OpenCode stderr: {error[:500]}...")

        # Check if output is empty
        if not output:
            logger.error("OpenCode returned empty output")
            if error:
                return f"Error: {error}"
            return "Error: OpenCode returned no output"

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
