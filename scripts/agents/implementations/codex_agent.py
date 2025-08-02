"""Codex CLI agent implementation."""

import logging
import os
from typing import Dict, List

from ..core.cli_agent_wrapper import CLIAgentWrapper

logger = logging.getLogger(__name__)


class CodexAgent(CLIAgentWrapper):
    """OpenAI Codex CLI agent wrapper."""

    # Default model constants
    DEFAULT_OPENROUTER_MODEL = "qwen/qwen-2.5-coder-32b-instruct"
    DEFAULT_OPENAI_MODEL = "gpt-4"

    def __init__(self, agent_config=None):
        """Initialize Codex CLI agent.

        Args:
            agent_config: Optional AgentConfig instance for centralized configuration
        """
        # Get API keys
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")

        # Prefer OpenAI key for Codex, fall back to OpenRouter
        api_key = openai_key or openrouter_key

        # Get timeout from central config if available
        timeout = 300  # Default 5 minutes
        if agent_config:
            timeout = agent_config.get_subprocess_timeout()

        config = {
            "executable": "codex",
            "timeout": timeout,
            "env_vars": {
                "OPENAI_API_KEY": api_key,
            },
            "working_dir": os.getcwd(),
        }
        super().__init__("codex", config, agent_config)
        self.agent_config = agent_config

        # Get model configuration from config file
        self.model_config = agent_config.get_model_override("codex") if agent_config else {}

        # Track which provider we're using
        self.using_openrouter = not openai_key and openrouter_key

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Codex."""
        return "Codex"

    def get_model_config(self) -> Dict[str, any]:
        """Get Codex model configuration."""
        if self.using_openrouter:
            return {
                "model": self.model_config.get("model", self.DEFAULT_OPENROUTER_MODEL),
                "provider": "openrouter",
                "temperature": self.model_config.get("temperature", 0.3),
                "max_tokens": 8192,
            }
        else:
            return {"model": self.DEFAULT_OPENAI_MODEL, "provider": "openai", "temperature": 0.3, "max_tokens": 8192}

    def _build_command(self, prompt: str, context: Dict[str, str]) -> List[str]:
        """Build Codex CLI command."""
        # Build full prompt with context
        full_prompt = prompt
        if context.get("code"):
            full_prompt = f"Code Context:\n```\n{context['code']}\n```\n\nTask: {prompt}"

        # Codex uses approval modes for automation
        cmd = [
            self.executable,
            "--full-auto",  # Fully autonomous mode for CI/CD
            "--quiet",  # Quiet mode
        ]

        # Add model configuration
        if self.using_openrouter:
            # Use OpenRouter provider
            cmd.extend(["--provider", "https://openrouter.ai/api/v1"])
            cmd.extend(["--model", self.model_config.get("model", self.DEFAULT_OPENROUTER_MODEL)])
        else:
            # Use OpenAI directly
            cmd.extend(["--model", self.DEFAULT_OPENAI_MODEL])

        # Add the prompt as the last argument
        cmd.append(full_prompt)

        return cmd

    def _parse_output(self, output: str, error: str) -> str:
        """Parse Codex CLI output."""
        output = output.strip()

        # Strip any terminal formatting
        output = self._strip_ansi_codes(output)

        # Codex CLI may include metadata, extract the actual response
        lines = output.split("\n")

        # Filter out metadata lines
        filtered_lines = []
        skip_prefixes = ["Loading", "Connecting", "Using model:", "API:", "Session:"]

        for line in lines:
            if any(line.startswith(prefix) for prefix in skip_prefixes):
                continue
            filtered_lines.append(line)

        output = "\n".join(filtered_lines).strip()

        # Extract code blocks if present
        code_blocks = self._extract_code_blocks(output)
        if code_blocks:
            return "\n\n".join(code_blocks)

        return output

    def is_available(self) -> bool:
        """Check if Codex CLI is available."""
        if self._available is not None:
            return self._available

        try:
            import subprocess

            # Check if codex CLI exists
            result = subprocess.run(["which", "codex"], capture_output=True, timeout=5)

            if result.returncode != 0:
                logger.info("Codex CLI not found. Install with: npm i -g @openai/codex")
                self._available = False
                return False

            # Check if we have required API keys
            if not self.env_vars.get("OPENAI_API_KEY"):
                logger.warning("Codex CLI found but no API key configured")
                logger.info("Set OPENAI_API_KEY or OPENROUTER_API_KEY environment variable")
                self._available = False  # Codex requires API key to function
            else:
                self._available = True

        except Exception as e:
            logger.error(f"Error checking Codex availability: {e}")
            self._available = False

        return self._available

    def get_capabilities(self) -> List[str]:
        """Get Codex's capabilities."""
        return [
            "code_generation",
            "code_review",
            "multimodal",  # Supports screenshots/diagrams
            "sandboxed_execution",  # Can execute commands safely
            "interactive_development",  # Chat-driven development
            "code_explanation",
            "refactoring",
        ]

    def get_priority(self) -> int:
        """Codex has lower priority as it's primarily OpenAI-focused."""
        return 60

    def get_auth_command(self) -> List[str]:
        """Get authentication command for Codex."""
        # Codex uses environment variables for auth
        return None
