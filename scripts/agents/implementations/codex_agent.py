"""Codex CLI agent implementation."""

import logging
import os
from typing import Dict, List

from ..core.cli_agent_wrapper import CLIAgentWrapper

logger = logging.getLogger(__name__)


class CodexAgent(CLIAgentWrapper):
    """OpenAI Codex CLI agent wrapper."""

    def __init__(self):
        """Initialize Codex CLI agent."""
        # Get API keys
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")

        # Prefer OpenAI key for Codex, fall back to OpenRouter
        api_key = openai_key or openrouter_key

        config = {
            "executable": "codex",
            "timeout": 300,  # 5 minutes default
            "env_vars": {
                "OPENAI_API_KEY": api_key,
            },
            "working_dir": os.getcwd(),
        }
        super().__init__("codex", config)

        # Track which provider we're using
        self.using_openrouter = not openai_key and openrouter_key

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Codex."""
        return "Codex"

    def get_model_config(self) -> Dict[str, any]:
        """Get Codex model configuration."""
        if self.using_openrouter:
            return {
                "model": "qwen/qwen-2.5-coder-32b-instruct",
                "provider": "openrouter",
                "temperature": 0.3,
                "max_tokens": 8192,
            }
        else:
            return {"model": "gpt-4", "provider": "openai", "temperature": 0.3, "max_tokens": 8192}

    def _build_command(self, prompt: str, context: Dict[str, str]) -> List[str]:
        """Build Codex CLI command."""
        # Build full prompt with context
        full_prompt = prompt
        if context.get("code"):
            full_prompt = f"Code Context:\n```\n{context['code']}\n```\n\nTask: {prompt}"

        # Create temp file for complex prompts
        prompt_file = self._save_to_temp_file(full_prompt, suffix=".md")

        # Build command based on Codex CLI interface
        cmd = [self.executable, "--non-interactive", "--input", prompt_file]  # Non-interactive mode for automation

        # Add model configuration if using OpenRouter
        if self.using_openrouter:
            cmd.extend(["--api-endpoint", "https://openrouter.ai/api/v1"])
            cmd.extend(["--model", "qwen/qwen-2.5-coder-32b-instruct"])

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
                self._available = True  # CLI exists, just needs config
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
