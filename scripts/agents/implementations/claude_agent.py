"""Claude Code agent implementation."""

import logging
import os
from typing import Dict, List

from ..core.cli_agent_wrapper import CLIAgentWrapper

logger = logging.getLogger(__name__)


class ClaudeAgent(CLIAgentWrapper):
    """Claude Code CLI agent wrapper."""

    def __init__(self, agent_config=None):
        """Initialize Claude agent.

        Args:
            agent_config: Optional AgentConfig instance for centralized configuration
        """
        # Get timeout from central config if available
        timeout = 600  # Default 10 minutes
        if agent_config:
            timeout = agent_config.get_subprocess_timeout()

        config = {
            "executable": "claude",
            "timeout": timeout,
            "env_vars": {},
            "working_dir": os.getcwd(),
        }
        super().__init__("claude", config)
        self.agent_config = agent_config

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Claude."""
        return "Claude"

    def get_model_config(self) -> Dict[str, any]:
        """Get Claude model configuration."""
        return {"model": "claude-opus-4-20250514", "provider": "anthropic", "temperature": 0.2, "max_tokens": 8192}

    def _build_command(self, prompt: str, context: Dict[str, str]) -> List[str]:
        """Build Claude CLI command."""
        # Build full prompt with context
        full_prompt = prompt
        if context.get("code"):
            full_prompt = f"Here is the code:\n\n{context['code']}\n\n{prompt}"

        # Claude CLI expects the prompt as the last argument
        # For CI/CD autonomous operation, we need --dangerously-skip-permissions
        cmd = [
            self.executable,
            "--print",  # Non-interactive mode
            "--dangerously-skip-permissions",  # Required for autonomous CI/CD operation
            "--output-format",
            "text",  # Plain text output
            full_prompt,
        ]

        return cmd

    def _parse_output(self, output: str, error: str) -> str:
        """Parse Claude CLI output."""
        # Claude CLI with --print returns plain text output
        output = output.strip()

        # Extract code blocks if present
        code_blocks = self._extract_code_blocks(output)
        if code_blocks:
            return "\n\n".join(code_blocks)

        return output

    def is_available(self) -> bool:
        """Check if Claude CLI is available and authenticated."""
        if self._available is not None:
            return self._available

        try:
            import subprocess

            # Check if claude CLI exists
            result = subprocess.run(["which", "claude"], capture_output=True, timeout=5)

            if result.returncode != 0:
                logger.warning("Claude CLI not found in PATH")
                self._available = False
                return False

            # Check if authenticated (claude --version should work)
            result = subprocess.run(["claude", "--version"], capture_output=True, timeout=5)

            self._available = result.returncode == 0
            if not self._available:
                logger.warning("Claude CLI found but not authenticated")

        except Exception as e:
            logger.error(f"Error checking Claude availability: {e}")
            self._available = False

        return self._available

    def get_capabilities(self) -> List[str]:
        """Get Claude's capabilities."""
        return ["code_generation", "code_review", "refactoring", "debugging", "documentation", "architecture_design"]

    def get_priority(self) -> int:
        """Claude has highest priority as the primary agent."""
        return 100
