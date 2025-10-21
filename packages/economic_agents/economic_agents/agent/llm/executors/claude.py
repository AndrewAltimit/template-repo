"""Claude Code CLI executor for autonomous decision-making."""

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class ClaudeExecutor:
    """Executor for Claude Code CLI in unattended mode.

    Uses Claude Code via CLI for autonomous decision-making with long timeouts
    to allow deep strategic reasoning.
    """

    def __init__(self, config: dict | None = None):
        """Initialize Claude executor.

        Args:
            config: Configuration dict with:
                - llm_timeout: Timeout in seconds (default: 900 = 15 minutes)
                - node_version: Node.js version (default: "22.16.0")
                - unattended: Always True for autonomous operation
        """
        self.config = config or {}
        self.node_version = self.config.get("node_version", "22.16.0")
        self.timeout = self.config.get("llm_timeout", 900)  # 15 minutes default
        self.unattended = True  # Always run in unattended mode for autonomous decisions

        logger.info(f"ClaudeExecutor initialized with timeout={self.timeout}s ({self.timeout/60:.1f} min)")

    def execute(self, prompt: str, timeout: Optional[int] = None) -> str:
        """Execute prompt via Claude Code CLI with long timeout.

        Args:
            prompt: The decision prompt for Claude
            timeout: Override default timeout in seconds (default: 900s = 15 minutes)

        Returns:
            Claude's text response (expected to be JSON)

        Raises:
            TimeoutError: If execution exceeds timeout
            RuntimeError: If Claude fails to execute
        """
        if timeout is None:
            timeout = self.timeout

        logger.info(f"Executing Claude with timeout={timeout}s ({timeout/60:.1f} min)")
        logger.debug(f"Prompt length: {len(prompt)} chars")

        try:
            # Build command to execute Claude Code CLI
            # Uses -p/--print for non-interactive output
            # Use $HOME instead of ~ to ensure proper expansion in subprocess
            command = (
                f"source $HOME/.nvm/nvm.sh && " f"nvm use {self.node_version} && " f"claude -p --dangerously-skip-permissions"
            )

            logger.debug("Executing Claude CLI in print mode")

            # Execute with prompt via stdin and timeout
            result = subprocess.run(
                ["bash", "-c", command],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True,
            )

            logger.info(f"Claude execution successful ({len(result.stdout)} chars)")
            return result.stdout

        except subprocess.TimeoutExpired:
            error_msg = f"Claude execution exceeded {timeout}s ({timeout/60:.1f} minutes)"
            logger.error(error_msg)
            raise TimeoutError(error_msg)

        except subprocess.CalledProcessError as e:
            error_msg = f"Claude execution failed: {e.stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error during Claude execution: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
