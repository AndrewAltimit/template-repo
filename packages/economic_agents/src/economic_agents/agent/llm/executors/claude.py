"""Claude Code CLI executor for autonomous decision-making."""

import logging
import re
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Allowed Node.js versions (semantic versioning format)
ALLOWED_NODE_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


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

        Raises:
            ValueError: If node_version is not a valid semantic version
        """
        self.config = config or {}
        node_version = self.config.get("node_version", "22.16.0")

        # Validate node_version to prevent command injection
        if not ALLOWED_NODE_VERSION_PATTERN.match(node_version):
            raise ValueError(f"Invalid node_version: {node_version}. Must be semantic version format (e.g., '22.16.0')")

        self.node_version = node_version
        self.timeout = self.config.get("llm_timeout", 900)  # 15 minutes default
        self.unattended = True  # Always run in unattended mode for autonomous decisions

        logger.info("ClaudeExecutor initialized with timeout=%ds (%.1f min)", self.timeout, self.timeout / 60)

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

        logger.info("Executing Claude with timeout=%ds (%.1f min)", timeout, timeout / 60)
        logger.debug("Prompt length: %s chars", len(prompt))

        try:
            # Build command to execute Claude Code CLI
            # Uses -p/--print for non-interactive output
            # Use $HOME instead of ~ to ensure proper expansion in subprocess
            command = f"source $HOME/.nvm/nvm.sh && nvm use {self.node_version} && claude -p --dangerously-skip-permissions"

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

            logger.info("Claude execution successful (%d chars)", len(result.stdout))
            return result.stdout

        except subprocess.TimeoutExpired as exc:
            error_msg = f"Claude execution exceeded {timeout}s ({timeout / 60:.1f} minutes)"
            logger.error("Claude execution exceeded %ds (%.1f minutes)", timeout, timeout / 60)
            raise TimeoutError(error_msg) from exc

        except subprocess.CalledProcessError as e:
            error_msg = f"Claude execution failed: {e.stderr}"
            logger.error("Claude execution failed: %s", e.stderr)
            raise RuntimeError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error during Claude execution: {e}"
            logger.error("Unexpected error during Claude execution: %s", e)
            raise RuntimeError(error_msg) from e
