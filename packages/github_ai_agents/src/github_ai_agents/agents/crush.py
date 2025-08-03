"""Crush (mods) AI agent implementation."""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import CLIAgent

logger = logging.getLogger(__name__)


class CrushAgent(CLIAgent):
    """Crush AI agent for code generation."""

    def __init__(self, config=None):
        """Initialize Crush agent."""
        super().__init__("crush", "mods", timeout=300, config=config)

        # Set up environment variables
        if api_key := os.environ.get("OPENROUTER_API_KEY"):
            self.env_vars["OPENROUTER_API_KEY"] = api_key

        # Cache the project root
        self._project_root: Optional[Path] = None
        self._use_docker: bool = False  # Track whether to use Docker

    def get_trigger_keyword(self) -> str:
        """Get trigger keyword for Crush."""
        return "Crush"

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
        """Check if Crush/mods is available via Docker (preferred) or locally."""
        if self._available is not None:
            return self._available

        # PREFER DOCKER: Check if Docker container is available first
        try:
            repo_root = self._find_project_root()
            if repo_root:
                compose_file = repo_root / "docker-compose.yml"
                if compose_file.exists():
                    result = subprocess.run(
                        ["docker-compose", "-f", str(compose_file), "config", "--services"],
                        capture_output=True,
                        timeout=5,
                        text=True,
                    )
                    if result.returncode == 0 and "openrouter-agents" in result.stdout:
                        self._available = True
                        self._use_docker = True
                        logger.info("Crush/mods available via Docker container (preferred)")
                        return True
        except Exception as e:
            logger.debug(f"Docker check failed: {e}")

        # Fall back to local if Docker not available
        if shutil.which(self.executable):
            try:
                result = subprocess.run([self.executable, "--version"], capture_output=True, timeout=5, text=True)
                if result.returncode == 0:
                    self._available = True
                    self._use_docker = False
                    logger.info("Crush/mods found locally (Docker not available)")
                    return True
            except Exception:
                pass

        self._available = False
        logger.warning("Crush/mods not available via Docker or locally")
        return False

    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate code using Crush.

        Args:
            prompt: The task or question
            context: Additional context

        Returns:
            Generated code or response
        """
        # Build command
        cmd = self._build_command(prompt)

        # Execute command
        stdout, stderr = await self._execute_command(cmd)
        return stdout.strip()

    def _build_command(self, prompt: str) -> List[str]:
        """Build Crush/mods CLI command."""
        # Get flags from config or use defaults
        if self.config:
            flags = self.config.get_non_interactive_flags("crush")
        else:
            flags = []

        # Use Docker if available (preferred), otherwise local
        if self._use_docker:
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

            # Note: mods is the actual executable name, crush is the alias
            cmd.extend(["openrouter-agents", "mods"])
            cmd.extend(flags)
            cmd.append(prompt)

            return cmd
        else:
            # Use local executable
            cmd = [self.executable]  # self.executable is "mods"
            cmd.extend(flags)
            cmd.append(prompt)
            return cmd

    def get_priority(self) -> int:
        """Get priority for Crush."""
        return 60
