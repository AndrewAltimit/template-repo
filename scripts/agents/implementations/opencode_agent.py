"""OpenCode AI agent implementation."""

import json
import logging
import os
from typing import Dict, List

from ..core.cli_agent_wrapper import CLIAgentWrapper

logger = logging.getLogger(__name__)


class OpenCodeAgent(CLIAgentWrapper):
    """OpenCode CLI agent wrapper."""

    # Default model constant
    DEFAULT_MODEL = "qwen/qwen-2.5-coder-32b-instruct"

    def __init__(self, agent_config=None):
        """Initialize OpenCode agent.

        Args:
            agent_config: Optional AgentConfig instance for centralized configuration
        """
        # Get OpenRouter configuration from environment or defaults
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")

        # Get model configuration from config file
        model_config = agent_config.get_model_override("opencode") if agent_config else {}
        model_name = model_config.get("model", self.DEFAULT_MODEL)

        # Get timeout from central config if available
        timeout = 300  # Default 5 minutes
        if agent_config:
            timeout = agent_config.get_subprocess_timeout()

        config = {
            "executable": "opencode",
            "timeout": timeout,
            "env_vars": {
                "OPENROUTER_API_KEY": openrouter_key,
                # OpenCode supports Models.dev integration
                "OPENCODE_MODEL": f"openrouter/{model_name}",
            },
            "working_dir": os.getcwd(),
        }
        super().__init__("opencode", config, agent_config)
        self.agent_config = agent_config
        self.model_config = model_config

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for OpenCode."""
        return "OpenCode"

    def get_model_config(self) -> Dict[str, any]:
        """Get OpenCode model configuration."""
        # Use model config from file or defaults
        return {
            "model": self.model_config.get("model", "qwen/qwen-2.5-coder-32b-instruct"),
            "provider": "openrouter",
            "temperature": self.model_config.get("temperature", 0.2),
            "max_tokens": 8192,
            "supports_openrouter": True,
        }

    def _build_command(self, prompt: str, context: Dict[str, str]) -> List[str]:
        """Build OpenCode CLI command."""
        # Build full prompt with context
        full_prompt = prompt
        if context.get("code"):
            full_prompt = f"Code Context:\n```\n{context['code']}\n```\n\nTask: {prompt}"

        # OpenCode supports non-interactive mode with -p flag
        cmd = [
            self.executable,
            "-p",  # Prompt flag for non-interactive mode
            full_prompt,
            "-q",  # Quiet flag to disable spinner
        ]

        # Add JSON format if needed
        if self._supports_json_output():
            cmd.extend(["-f", "json"])

        return cmd

    def _parse_output(self, output: str, error: str) -> str:
        """Parse OpenCode CLI output."""
        output = output.strip()

        # Try to parse as JSON if available
        if self._supports_json_output():
            try:
                result = json.loads(output)
                if isinstance(result, dict):
                    # Look for code or response field
                    return result.get("code", result.get("response", output))
            except json.JSONDecodeError:
                # Fall back to text parsing
                pass

        # Strip any terminal formatting
        output = self._strip_ansi_codes(output)

        # Extract code blocks if present
        code_blocks = self._extract_code_blocks(output)
        if code_blocks:
            return "\n\n".join(code_blocks)

        return output

    def _supports_json_output(self) -> bool:
        """Check if OpenCode supports JSON output format."""
        # This would be determined by testing or documentation
        # For now, assume it might support it
        return True

    def is_available(self) -> bool:
        """Check if OpenCode CLI is available."""
        if self._available is not None:
            return self._available

        try:
            import subprocess

            # Check if opencode CLI exists
            result = subprocess.run(["which", "opencode"], capture_output=True, timeout=5)

            if result.returncode != 0:
                logger.info("OpenCode CLI not found. Install with: curl -fsSL https://opencode.ai/install | bash")
                self._available = False
                return False

            # Try to run a simple test command
            result = subprocess.run([self.executable, "-p", "test", "-q"], capture_output=True, timeout=10)

            self._available = result.returncode == 0

            if not self._available:
                logger.warning("OpenCode CLI found but not working properly")

        except Exception as e:
            logger.error(f"Error checking OpenCode availability: {e}")
            self._available = False

        return self._available

    def get_capabilities(self) -> List[str]:
        """Get OpenCode's capabilities."""
        return [
            "code_generation",
            "code_review",
            "refactoring",
            "multi_session",  # OpenCode supports multiple sessions
            "lsp_integration",  # Language Server Protocol support
            "plan_mode",  # Planning before implementation
            "openrouter_models",  # 75+ models via OpenRouter
        ]

    def get_priority(self) -> int:
        """OpenCode has medium-high priority as an open-source alternative."""
        return 80

    def get_auth_command(self) -> List[str]:
        """Get authentication command for OpenCode."""
        # OpenCode uses 'opencode auth login' for authentication
        return [self.executable, "auth", "login"]
