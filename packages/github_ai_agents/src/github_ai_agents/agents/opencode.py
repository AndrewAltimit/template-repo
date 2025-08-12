"""OpenCode AI agent implementation."""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Tuple

from .base import AgentExecutionError, AgentTimeoutError
from .containerized import ContainerizedCLIAgent

logger = logging.getLogger(__name__)


class OpenCodeAgent(ContainerizedCLIAgent):
    """OpenCode AI agent for code generation."""

    DEFAULT_MODEL = "qwen/qwen-2.5-coder-32b-instruct"

    def __init__(self, config=None) -> None:
        """Initialize OpenCode agent."""
        super().__init__(
            "opencode",
            "opencode",
            docker_service="openrouter-agents",
            timeout=300,
            config=config,
        )

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

        # Build command (without prompt - will use stdin)
        cmd = self._build_command()

        # Log the command being executed
        logger.info(f"Full prompt length: {len(full_prompt)} chars")
        logger.info(f"Executing OpenCode via stdin with command: {' '.join(cmd[-5:])}")
        logger.debug(f"Full command: {cmd}")

        # Execute command with stdin
        try:
            stdout, stderr = await self._execute_command_with_stdin(cmd, full_prompt)
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
                self.name,
                e.exit_code,
                e.stdout,
                e.stderr or "No error output from opencode command",
            )

    def _build_command(self) -> List[str]:
        """Build OpenCode CLI command for stdin usage."""
        # OpenCode uses 'run' subcommand
        args = ["run"]

        # Add model flag if we have a model configured
        if self.DEFAULT_MODEL:
            args.extend(["-m", f"openrouter/{self.DEFAULT_MODEL}"])

        # Don't add prompt here - we'll use stdin instead

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

    async def _execute_command_with_stdin(self, cmd: List[str], stdin_input: str) -> Tuple[str, str]:
        """Execute command with stdin input.

        Args:
            cmd: Command to execute (already includes docker-compose if using Docker)
            stdin_input: Input to pass via stdin

        Returns:
            Tuple of (stdout, stderr)
        """
        # cmd is already the full command (including docker-compose if applicable)
        # Just execute it with stdin
        return await self._execute_stdin(cmd, stdin_input)

    async def _execute_stdin(self, cmd: List[str], stdin_input: str) -> Tuple[str, str]:
        """Execute command with stdin using asyncio."""
        logger.debug(f"Executing {self.name} with stdin")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=stdin_input.encode("utf-8")),
                    timeout=self.timeout,
                )

                stdout_str = stdout.decode("utf-8", errors="replace")
                stderr_str = stderr.decode("utf-8", errors="replace")

                if proc.returncode != 0:
                    raise AgentExecutionError(self.name, proc.returncode or -1, stdout_str, stderr_str)

                return stdout_str, stderr_str

            except asyncio.TimeoutError:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

                raise AgentTimeoutError(self.name, self.timeout)

        except FileNotFoundError:
            raise AgentExecutionError(self.name, -1, "", f"Executable not found in command: {cmd}")

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
