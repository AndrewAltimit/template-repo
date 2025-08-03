"""Base class for containerized CLI agents."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .base import CLIAgent

logger = logging.getLogger(__name__)


class ContainerizedCLIAgent(CLIAgent):
    """Base class for CLI agents that can run in Docker containers."""

    def __init__(
        self, name: str, executable: str, docker_service: str = "openrouter-agents", timeout: int = 300, config=None
    ):
        """Initialize containerized CLI agent.

        Args:
            name: Name of the agent
            executable: Path to executable
            docker_service: Docker Compose service name
            timeout: Command timeout in seconds
            config: Optional AgentConfig instance
        """
        super().__init__(name, executable, timeout, config)
        self.docker_service = docker_service
        self._project_root: Optional[Path] = None
        self._use_docker: bool = False

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
        """Check if agent is available via Docker (preferred) or locally."""
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
                    if result.returncode == 0 and self.docker_service in result.stdout:
                        self._available = True
                        self._use_docker = True
                        logger.info(f"{self.name} available via Docker container (preferred)")
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
                    logger.info(f"{self.name} found locally (Docker not available)")
                    return True
            except Exception:
                pass

        self._available = False
        logger.warning(f"{self.name} not available via Docker or locally")
        return False

    def _build_docker_command(self, args: List[str], env_vars: Optional[Dict[str, str]] = None) -> List[str]:
        """Build Docker Compose command.

        Args:
            args: Arguments to pass to the executable
            env_vars: Environment variables to pass

        Returns:
            Complete Docker Compose command
        """
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
        if env_vars:
            for key, value in env_vars.items():
                cmd.extend(["-e", f"{key}={value}"])

        # Add service name and executable
        cmd.extend([self.docker_service, self.executable])

        # Add arguments
        cmd.extend(args)

        return cmd
