"""Base classes for AI agents."""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for agent errors."""

    pass


class AgentNotAvailableError(AgentError):
    """Raised when an agent is not available."""

    def __init__(self, agent_name: str, reason: str = ""):
        self.agent_name = agent_name
        self.reason = reason
        super().__init__(f"Agent '{agent_name}' is not available: {reason}")


class AgentExecutionError(AgentError):
    """Raised when agent execution fails."""

    def __init__(self, agent_name: str, exit_code: int, stdout: str = "", stderr: str = ""):
        self.agent_name = agent_name
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Agent '{agent_name}' failed with exit code {exit_code}")


class AgentTimeoutError(AgentError):
    """Raised when agent execution times out."""

    def __init__(self, agent_name: str, timeout: int, stdout: str = "", stderr: str = ""):
        self.agent_name = agent_name
        self.timeout = timeout
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Agent '{agent_name}' timed out after {timeout}s")


class BaseAgent(ABC):
    """Abstract base class for AI agents."""

    def __init__(self, name: str, config=None):
        """Initialize base agent.

        Args:
            name: Name of the agent
            config: Optional AgentConfig instance
        """
        self.name = name
        self.config = config
        self._available: Optional[bool] = None

    @abstractmethod
    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code based on prompt and context.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Generated code or response
        """
        pass

    async def review_async(self, prompt: str) -> str:
        """Review code or issue without making changes.

        Args:
            prompt: The review prompt

        Returns:
            Review feedback as string
        """
        # Default implementation uses generate_code with a review context
        context = {"mode": "review", "no_code_generation": True}
        return await self.generate_code(prompt, context)

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the agent is available.

        Returns:
            True if agent is available, False otherwise
        """
        pass

    @abstractmethod
    def get_trigger_keyword(self) -> str:
        """Get the keyword used to trigger this agent.

        Returns:
            Trigger keyword (e.g., "Claude", "OpenCode")
        """
        pass

    def get_capabilities(self) -> List[str]:
        """Get agent capabilities.

        Returns:
            List of capability strings
        """
        return ["code_generation"]

    def get_priority(self) -> int:
        """Get agent priority for selection.

        Higher priority agents are preferred when multiple are available.

        Returns:
            Priority value (0-100)
        """
        return 50


class CLIAgent(BaseAgent):
    """Base class for CLI-based agents."""

    def __init__(self, name: str, executable: str, timeout: int = 300, config=None):
        """Initialize CLI agent.

        Args:
            name: Name of the agent
            executable: Path to executable
            timeout: Command timeout in seconds
            config: Optional AgentConfig instance
        """
        super().__init__(name, config)
        self.executable = executable
        # Use timeout from config if available
        if config:
            self.timeout = config.get_subprocess_timeout()
        else:
            self.timeout = timeout
        self.env_vars: Dict[str, str] = {}

    async def _execute_command(self, cmd: List[str], env: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
        """Execute a CLI command asynchronously.

        Args:
            cmd: Command to execute
            env: Environment variables

        Returns:
            Tuple of (stdout, stderr)

        Raises:
            AgentTimeoutError: If command times out
            AgentExecutionError: If command fails
        """
        if env is None:
            env = os.environ.copy()
            env.update(self.env_vars)

        logger.debug(f"Executing {self.name}: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
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
            raise AgentExecutionError(self.name, -1, "", f"Executable '{self.executable}' not found")

    def is_available(self) -> bool:
        """Check if CLI tool is available."""
        if self._available is not None:
            return self._available

        try:
            import subprocess

            # Note: This is a synchronous call because is_available() is called during
            # synchronous initialization. Converting to async would require major refactoring.
            # Using a short timeout to minimize blocking.
            result = subprocess.run([self.executable, "--version"], capture_output=True, timeout=2)
            self._available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._available = False

        return self._available
