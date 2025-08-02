"""Crush AI agent implementation."""

import json
import logging
import os
from typing import Dict, List

from ..core.cli_agent_wrapper import CLIAgentWrapper

logger = logging.getLogger(__name__)


class CrushAgent(CLIAgentWrapper):
    """Crush CLI agent wrapper from Charm Bracelet."""

    # Default model constant
    DEFAULT_MODEL = "qwen/qwen-2.5-coder-32b-instruct"

    def __init__(self, agent_config=None):
        """Initialize Crush agent.

        Args:
            agent_config: Optional AgentConfig instance for centralized configuration
        """
        # Get API keys from environment
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")

        # Crush configuration path
        config_dir = os.path.expanduser("~/.config/crush")
        config_file = os.path.join(config_dir, "crush.json")

        # Get timeout from central config if available
        timeout = 300  # Default 5 minutes
        if agent_config:
            timeout = agent_config.get_subprocess_timeout()

        config = {
            "executable": "crush",
            "timeout": timeout,
            "env_vars": {
                "OPENROUTER_API_KEY": openrouter_key,
            },
            "working_dir": os.getcwd(),
        }
        super().__init__("crush", config, agent_config)
        self.agent_config = agent_config

        # Get model configuration from config file
        self.model_config = agent_config.get_model_override("crush") if agent_config else {}

        # Create Crush config if needed
        self._ensure_crush_config(config_file, openrouter_key)

    def _ensure_crush_config(self, config_file: str, api_key: str):
        """Ensure Crush configuration exists for OpenRouter."""
        if not os.path.exists(config_file) and api_key:
            os.makedirs(os.path.dirname(config_file), exist_ok=True)

            # Create a basic Crush config for OpenRouter
            crush_config = {
                "providers": {
                    "openrouter": {
                        "api_key": api_key,
                        "base_url": "https://openrouter.ai/api/v1",
                        "model": self.model_config.get("model", self.DEFAULT_MODEL),
                    }
                },
                "default_provider": "openrouter",
            }

            try:
                with open(config_file, "w") as f:
                    json.dump(crush_config, f, indent=2)
                logger.info(f"Created Crush config at {config_file}")
            except Exception as e:
                logger.warning(f"Failed to create Crush config: {e}")

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Crush."""
        return "Crush"

    def get_model_config(self) -> Dict[str, any]:
        """Get Crush model configuration."""
        return {
            "model": self.model_config.get("model", self.DEFAULT_MODEL),
            "provider": "openrouter",
            "temperature": self.model_config.get("temperature", 0.1),  # Lower temperature for Crush
            "max_tokens": 8192,
            "supports_multi_provider": True,
            "supports_mcp": True,  # Model Context Protocol
        }

    def _build_command(self, prompt: str, context: Dict[str, str]) -> List[str]:
        """Build Crush/mods CLI command."""
        # Build full prompt with context
        full_prompt = prompt
        if context.get("code"):
            full_prompt = f"Code Context:\n```\n{context['code']}\n```\n\nTask: {prompt}"

        # mods (Crush) expects the prompt as the last argument
        cmd = [
            self.executable,
            "--model",
            self.model_config.get("model", f"openrouter/{self.DEFAULT_MODEL}"),
            "--api",
            "https://openrouter.ai/api/v1",
            "--no-cache",  # Don't cache results in CI/CD
            full_prompt,
        ]

        return cmd

    def _parse_output(self, output: str, error: str) -> str:
        """Parse Crush CLI output."""
        output = output.strip()

        # Strip any terminal formatting
        output = self._strip_ansi_codes(output)

        # Crush may include session information, extract the actual response
        lines = output.split("\n")

        # Filter out session/status lines
        filtered_lines = []
        for line in lines:
            # Skip common status indicators
            if any(skip in line.lower() for skip in ["session", "connecting", "provider:", "model:"]):
                continue
            filtered_lines.append(line)

        output = "\n".join(filtered_lines).strip()

        # Extract code blocks if present
        code_blocks = self._extract_code_blocks(output)
        if code_blocks:
            return "\n\n".join(code_blocks)

        return output

    def is_available(self) -> bool:
        """Check if Crush CLI is available."""
        if self._available is not None:
            return self._available

        try:
            import subprocess

            # Check if crush CLI exists
            result = subprocess.run(["which", "crush"], capture_output=True, timeout=5)

            if result.returncode != 0:
                logger.info("Crush/mods CLI not found. Install with: go install github.com/charmbracelet/mods@latest")
                self._available = False
                return False

            # mods doesn't have a --version flag, test with help
            result = subprocess.run([self.executable, "--help"], capture_output=True, timeout=10)

            self._available = result.returncode == 0

            if not self._available:
                logger.warning("Crush/mods CLI found but not working properly")

        except Exception as e:
            logger.error(f"Error checking Crush availability: {e}")
            self._available = False

        return self._available

    def get_capabilities(self) -> List[str]:
        """Get Crush's capabilities."""
        return [
            "code_generation",
            "code_review",
            "multi_provider",  # Supports multiple LLM providers
            "mcp_support",  # Model Context Protocol
            "session_management",  # Session-based conversations
            "lsp_integration",  # Language Server Protocol
            "context_switching",  # Can switch models mid-session
        ]

    def get_priority(self) -> int:
        """Crush/mods has medium priority as a flexible multi-provider tool."""
        return 75

    def get_auth_command(self) -> List[str]:
        """Get authentication command for Crush."""
        # Crush uses configuration files for auth, no specific auth command
        return None
