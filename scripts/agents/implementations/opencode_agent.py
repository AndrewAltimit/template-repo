"""OpenCode AI agent implementation."""

import json
import logging
import os
import subprocess
from pathlib import Path
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

    def is_available(self) -> bool:
        """Check if OpenCode is available either locally or via Docker."""
        if self._available is not None:
            return self._available

        # First check if OpenCode is available locally
        try:
            import shutil

            if shutil.which(self.executable):
                result = subprocess.run([self.executable, "--version"], capture_output=True, timeout=5)
                self._available = result.returncode == 0
                if self._available:
                    logger.info("OpenCode found locally")
                    return True
        except Exception:
            pass

        # If not available locally, check if Docker container is available
        try:
            # Find the docker-compose.yml file
            repo_root = Path(__file__).resolve().parents[3]  # Go up to repo root
            compose_file = repo_root / "docker-compose.yml"

            # Check if docker-compose and the openrouter-agents service exist
            result = subprocess.run(
                ["docker-compose", "-f", str(compose_file), "config", "--services"], capture_output=True, timeout=5, text=True
            )
            if result.returncode == 0 and "openrouter-agents" in result.stdout:
                self._available = True
                logger.info("OpenCode available via Docker container")
                return True
        except Exception as e:
            logger.debug(f"Docker check failed: {e}")
            pass

        self._available = False
        logger.warning("OpenCode not available locally or via Docker")
        return False

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

        # Check if opencode is available on host
        import shutil

        if shutil.which(self.executable):
            # OpenCode is available locally
            cmd = [
                self.executable,
                "-p",  # Prompt flag for non-interactive mode
                full_prompt,
                "-q",  # Quiet flag to disable spinner
            ]
        else:
            # OpenCode not on host, use Docker
            logger.info("OpenCode not found on host, using Docker container")
            # Prepare environment variables
            env_args = []
            if self.env_vars.get("OPENROUTER_API_KEY"):
                env_args.extend(["-e", f"OPENROUTER_API_KEY={self.env_vars['OPENROUTER_API_KEY']}"])

            # Find the docker-compose.yml file
            repo_root = Path(__file__).resolve().parents[3]  # Go up to repo root
            compose_file = repo_root / "docker-compose.yml"

            cmd = (
                [
                    "docker-compose",
                    "-f",
                    str(compose_file),
                    "run",
                    "--rm",
                    "-T",  # Disable pseudo-TTY allocation
                ]
                + env_args
                + [
                    "openrouter-agents",
                    "opencode",
                    "-p",
                    full_prompt,
                    "-q",
                ]
            )

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
