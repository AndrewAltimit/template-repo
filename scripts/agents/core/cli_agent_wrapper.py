"""Base wrapper for CLI-based AI agents."""

import asyncio
import logging
import os
import re
from abc import abstractmethod
from typing import Dict, List, Optional, Tuple

from .agent_interface import AIAgent
from .exceptions import AgentAuthenticationError, AgentExecutionError, AgentTimeoutError

logger = logging.getLogger(__name__)


class CLIAgentWrapper(AIAgent):
    """Base class for wrapping CLI-based AI agents."""

    def __init__(self, agent_name: str, config: Dict[str, any], agent_config=None):
        """Initialize CLI agent wrapper.

        Args:
            agent_name: Name of the agent
            config: Configuration dictionary with:
                - executable: Path to executable
                - args_template: Template for command arguments
                - timeout: Command timeout in seconds
                - env_vars: Environment variables to set
                - working_dir: Working directory for execution
            agent_config: Optional AgentConfig instance for security checks
        """
        self.agent_name = agent_name
        self.executable = config["executable"]
        self.args_template = config.get("args_template", [])
        self.timeout = config.get("timeout", 300)
        self.env_vars = config.get("env_vars", {})
        self.working_dir = config.get("working_dir", None)
        self._available = None
        self.agent_config = agent_config

    @abstractmethod
    def _build_command(self, prompt: str, context: Dict[str, str]) -> List[str]:
        """Build the command to execute.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Command as list of strings
        """
        pass

    @abstractmethod
    def _parse_output(self, output: str, error: str) -> str:
        """Parse the CLI output to extract the response.

        Args:
            output: stdout from the command
            error: stderr from the command

        Returns:
            Parsed response
        """
        pass

    async def _execute_with_timeout(self, cmd: List[str]) -> Tuple[str, str]:
        """Execute CLI command with timeout and capture output.

        Args:
            cmd: Command to execute

        Returns:
            Tuple of (stdout, stderr)

        Raises:
            AgentTimeoutError: If command exceeds timeout
            AgentExecutionError: If command fails
        """
        env = os.environ.copy()
        env.update(self.env_vars)

        logger.info(f"Executing {self.agent_name}: {' '.join(cmd)}")

        proc = None
        stdout_data = b""
        stderr_data = b""

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, cwd=self.working_dir
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            except asyncio.TimeoutError:
                # Graceful termination sequence
                logger.warning(f"{self.agent_name} command timed out, attempting graceful shutdown")

                # First try SIGTERM
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    # Force kill if still running
                    logger.warning(f"{self.agent_name} did not respond to SIGTERM, forcing kill")
                    proc.kill()
                    await proc.wait()

                # Capture any partial output
                if proc.stdout and not proc.stdout.at_eof():
                    try:
                        partial_stdout = await asyncio.wait_for(proc.stdout.read(), timeout=0.5)
                        stdout_data += partial_stdout
                    except Exception:
                        pass

                raise AgentTimeoutError(
                    self.agent_name, self.timeout, stdout_data.decode(errors="replace"), stderr_data.decode(errors="replace")
                )

            # Check return code
            if proc.returncode != 0:
                raise AgentExecutionError(
                    self.agent_name,
                    proc.returncode,
                    stdout_data.decode(errors="replace"),
                    stderr_data.decode(errors="replace"),
                )

            return stdout_data.decode(), stderr_data.decode()

        except (AgentTimeoutError, AgentExecutionError):
            raise
        except Exception as e:
            logger.error(f"{self.agent_name} command failed: {e}")
            raise AgentExecutionError(self.agent_name, -1, stdout_data.decode(errors="replace") if stdout_data else "", str(e))

    async def generate_code(self, prompt: str, context: Dict[str, str]) -> str:
        """Generate code using the CLI agent."""
        # Check security requirements if configured
        self._check_security_requirements()

        cmd = self._build_command(prompt, context)
        stdout, stderr = await self._execute_with_timeout(cmd)
        return self._parse_output(stdout, stderr)

    async def review_code(self, code: str, instructions: str) -> str:
        """Review code using the CLI agent."""
        context = {"code": code, "review_instructions": instructions}
        prompt = f"Review this code: {instructions}"
        return await self.generate_code(prompt, context)

    def is_available(self) -> bool:
        """Check if the CLI tool is available."""
        if self._available is not None:
            return self._available

        try:
            import subprocess

            result = subprocess.run([self.executable, "--version"], capture_output=True, timeout=5)
            self._available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            self._available = False

        return self._available

    def get_auth_command(self) -> Optional[List[str]]:
        """Get authentication command for this agent.

        Override in subclasses that need special authentication.

        Returns:
            Command to run for authentication, or None if not needed
        """
        return None

    async def authenticate(self) -> bool:
        """Authenticate the agent if required.

        Returns:
            True if authentication successful or not required
        """
        auth_cmd = self.get_auth_command()
        if not auth_cmd:
            return True

        try:
            stdout, stderr = await self._execute_with_timeout(auth_cmd)
            return True
        except (AgentTimeoutError, AgentExecutionError) as e:
            logger.error(f"Authentication failed for {self.agent_name}: {e}")
            raise AgentAuthenticationError(self.agent_name, "CLI authentication")

    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape codes from terminal output."""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def _extract_code_blocks(self, text: str) -> List[str]:
        """Extract code blocks from markdown-formatted text."""
        code_pattern = re.compile(r"```(?:[\w]*\n)?(.*?)```", re.DOTALL)
        matches = code_pattern.findall(text)
        return matches if matches else [text]

    def _check_security_requirements(self) -> None:
        """Check security requirements before executing commands.

        Raises:
            AgentExecutionError: If security requirements are not met
        """
        if not self.agent_config:
            return  # No config, no security checks

        security_config = self.agent_config.get_security_config()
        if security_config.get("require_sandbox", False):
            # Check if we're running in a sandbox environment
            if os.environ.get("AGENT_SANDBOX_MODE") != "true":
                raise AgentExecutionError(
                    self.agent_name,
                    -1,
                    "",
                    "Agent execution denied: Sandbox mode is required but not enabled. "
                    "Set AGENT_SANDBOX_MODE=true to enable sandbox mode.",
                )
