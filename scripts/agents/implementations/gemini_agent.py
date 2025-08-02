"""Gemini CLI agent implementation."""

import logging
import os
from typing import Dict, List

from ..core.cli_agent_wrapper import CLIAgentWrapper
from ..core.exceptions import AgentExecutionError

logger = logging.getLogger(__name__)


class GeminiAgent(CLIAgentWrapper):
    """Gemini CLI agent wrapper."""

    def __init__(self):
        """Initialize Gemini agent."""
        config = {
            "executable": "gemini",
            "timeout": 90,  # 90 seconds for Pro model
            "env_vars": {},
            "working_dir": os.getcwd(),
        }
        super().__init__("gemini", config)

        # Model configuration
        self.pro_model = "gemini-2.5-pro"
        self.flash_model = "gemini-2.5-flash"
        self.current_model = self.pro_model

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Gemini."""
        return "Gemini"

    def get_model_config(self) -> Dict[str, any]:
        """Get Gemini model configuration."""
        return {
            "model": self.current_model,
            "provider": "google",
            "fallback_model": self.flash_model,
            "temperature": 0.3,
            "max_tokens": 8192,
        }

    def _build_command(self, prompt: str, context: Dict[str, str]) -> List[str]:
        """Build Gemini CLI command."""
        # Build full prompt with context
        full_prompt = prompt
        if context.get("code"):
            full_prompt = f"Code to analyze:\n\n{context['code']}\n\nTask: {prompt}"

        # Gemini CLI expects -p flag for prompt in non-interactive mode
        cmd = [self.executable, "-m", self.current_model, "-p", full_prompt]

        return cmd

    def _parse_output(self, output: str, error: str) -> str:
        """Parse Gemini CLI output."""
        # Clean output - remove "Loaded cached credentials" message if present
        lines = output.strip().split("\n")
        cleaned_lines = [line for line in lines if "Loaded cached credentials" not in line]
        output = "\n".join(cleaned_lines).strip()

        # Extract code blocks if present
        code_blocks = self._extract_code_blocks(output)
        if code_blocks and len(code_blocks) == 1:
            # If there's only one code block and it's the bulk of the response, return it
            if len(code_blocks[0]) > len(output) * 0.7:
                return code_blocks[0]

        return output

    async def generate_code(self, prompt: str, context: Dict[str, str]) -> str:
        """Generate code with fallback from Pro to Flash model."""
        # Try with Pro model first
        self.current_model = self.pro_model
        try:
            logger.info("Attempting Gemini Pro model...")
            return await super().generate_code(prompt, context)
        except AgentExecutionError as e:
            # Check if it's a quota error
            if "quota" in str(e).lower() or "api error" in str(e).lower():
                logger.warning("Gemini Pro quota exceeded, falling back to Flash model")
                # Fallback to Flash model
                self.current_model = self.flash_model
                self.timeout = 60  # Shorter timeout for Flash
                return await super().generate_code(prompt, context)
            else:
                raise

    def is_available(self) -> bool:
        """Check if Gemini CLI is available and authenticated."""
        if self._available is not None:
            return self._available

        try:
            import subprocess

            # Check if gemini CLI exists
            result = subprocess.run(["which", "gemini"], capture_output=True, timeout=5)

            if result.returncode != 0:
                logger.warning("Gemini CLI not found in PATH")
                self._available = False
                return False

            # Check if we can run a simple command
            # Note: Gemini CLI doesn't have a --version flag
            result = subprocess.run([self.executable, "-m", self.flash_model, "-p", "test"], capture_output=True, timeout=10)

            # If return code is 0 or the error is about authentication, consider it available
            if result.returncode == 0:
                self._available = True
            else:
                stderr = result.stderr.decode().lower()
                # Check for authentication error specifically
                if "authentication" in stderr or "credentials" in stderr:
                    logger.warning("Gemini CLI found but not authenticated. Run 'gemini' to authenticate.")
                    self._available = True  # CLI is available, just needs auth
                else:
                    self._available = False

        except Exception as e:
            logger.error(f"Error checking Gemini availability: {e}")
            self._available = False

        return self._available

    def get_capabilities(self) -> List[str]:
        """Get Gemini's capabilities."""
        return ["code_generation", "code_review", "second_opinion", "validation", "technical_analysis", "bug_detection"]

    def get_priority(self) -> int:
        """Gemini has high priority for reviews and validation."""
        return 90

    def get_auth_command(self) -> List[str]:
        """Get authentication command for Gemini."""
        # Gemini requires interactive authentication
        # This is just informational - actual auth must be done manually
        return None
