"""OpenCode AI agent implementation."""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import CLIAgent

logger = logging.getLogger(__name__)


class OpenCodeAgent(CLIAgent):
    """OpenCode AI agent for code generation."""

    DEFAULT_MODEL = "qwen/qwen-2.5-coder-32b-instruct"

    def __init__(self, config=None) -> None:
        """Initialize OpenCode agent."""
        super().__init__("opencode", "opencode", timeout=300, config=config)

        # Set up environment variables
        if api_key := os.environ.get("OPENROUTER_API_KEY"):
            self.env_vars["OPENROUTER_API_KEY"] = api_key
            self.env_vars["OPENCODE_MODEL"] = f"openrouter/{self.DEFAULT_MODEL}"

        # Cache the project root
        self._project_root: Optional[Path] = None

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for OpenCode."""
        return "OpenCode"

    def _find_project_root(self) -> Optional[Path]:
        """Find project root by searching up for .git directory or docker-compose.yml."""
        if self._project_root:
            return self._project_root

        current = Path(__file__).resolve()

        # Search up the directory tree
        for parent in current.parents:
            # Check for .git directory (marks repo root)
            if (parent / ".git").is_dir():
                self._project_root = parent
                return parent

            # Check for docker-compose.yml
            if (parent / "docker-compose.yml").is_file():
                self._project_root = parent
                return parent

            # Stop at root directory
            if parent.parent == parent:
                break

        return None

    def is_available(self) -> bool:
        """Check if OpenCode is available locally or via Docker."""
        if self._available is not None:
            return self._available

        # Check if OpenCode is available locally
        if shutil.which(self.executable):
            try:
                result = subprocess.run([self.executable, "--version"], capture_output=True, timeout=5, text=True)
                if result.returncode == 0:
                    self._available = True
                    logger.info("OpenCode found locally")
                    return True
            except Exception:
                pass

        # Check if Docker container is available
        try:
            repo_root = self._find_project_root()
            if not repo_root:
                logger.debug("Could not find project root")
                self._available = False
                return False

            compose_file = repo_root / "docker-compose.yml"
            if not compose_file.exists():
                logger.debug("docker-compose.yml not found")
                self._available = False
                return False

            result = subprocess.run(
                ["docker-compose", "-f", str(compose_file), "config", "--services"],
                capture_output=True,
                timeout=5,
                text=True,
            )
            if result.returncode == 0 and "openrouter-agents" in result.stdout:
                self._available = True
                logger.info("OpenCode available via Docker container")
                return True
        except Exception as e:
            logger.debug(f"Docker check failed: {e}")

        self._available = False
        logger.warning("OpenCode not available locally or via Docker")
        return False

    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code using OpenCode.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Generated code or response
        """
        # Build full prompt with context
        full_prompt = prompt
        if code := context.get("code"):
            full_prompt = f"Code Context:\n```\n{code}\n```\n\nTask: {prompt}"

        # Build command
        cmd = self._build_command(full_prompt)

        # Execute command
        stdout, stderr = await self._execute_command(cmd)

        # Parse output
        return self._parse_output(stdout, stderr)

    def _build_command(self, prompt: str) -> List[str]:
        """Build OpenCode CLI command."""
        # Get flags from config or use defaults
        if self.config:
            flags = self.config.get_non_interactive_flags("opencode")
        else:
            flags = ["-q"]  # Default quiet mode

        # Check if running locally or via Docker
        if shutil.which(self.executable):
            cmd = [self.executable, "-p", prompt]
            cmd.extend(flags)
            return cmd
        else:
            # Use Docker
            repo_root = self._find_project_root()
            if not repo_root:
                raise RuntimeError("Could not find project root for docker-compose.yml")

            compose_file = repo_root / "docker-compose.yml"
            if not compose_file.exists():
                raise RuntimeError(f"docker-compose.yml not found at {compose_file}")

            cmd = [
                "docker-compose",
                "-f",
                str(compose_file),
                "run",
                "--rm",
                "-T",
            ]

            # Add environment variables
            if api_key := self.env_vars.get("OPENROUTER_API_KEY"):
                cmd.extend(["-e", f"OPENROUTER_API_KEY={api_key}"])

            cmd.extend(["openrouter-agents", "opencode", "-p", prompt])
            cmd.extend(flags)

            return cmd

    def _parse_output(self, output: str, error: str) -> str:
        """Parse OpenCode output."""
        output = output.strip()

        # Try to parse as JSON if it looks like JSON
        if output.startswith("{") and output.endswith("}"):
            try:
                data = json.loads(output)
                return str(data.get("code", data.get("response", output)))
            except json.JSONDecodeError:
                pass

        return output

    def get_capabilities(self) -> List[str]:
        """Get OpenCode capabilities."""
        return [
            "code_generation",
            "code_review",
            "refactoring",
            "multi_session",
            "lsp_integration",
            "plan_mode",
            "openrouter_models",
        ]

    def get_priority(self) -> int:
        """Get priority for OpenCode."""
        return 80  # High priority as open-source alternative
