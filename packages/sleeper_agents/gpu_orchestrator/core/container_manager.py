"""Docker container management for GPU job execution."""

import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional

from docker.errors import DockerException, NotFound
from docker.models.containers import Container

from core.config import settings
import docker

logger = logging.getLogger(__name__)


class ContainerManager:
    """Manages Docker containers for GPU job execution."""

    def __init__(self):
        """Initialize Docker client."""
        try:
            self.client = docker.from_env()
            self.client.ping()
            logger.info("Docker client initialized successfully")
        except DockerException as e:
            logger.error("Failed to initialize Docker client: %s", e)
            raise

    def start_container(
        self,
        job_id: str,
        job_type: str,
        command: list[str],
        environment: Optional[Dict[str, str]] = None,
    ) -> str:
        """Start a GPU-enabled container for job execution.

        Args:
            job_id: Unique job identifier
            job_type: Type of job (for container naming)
            command: Command to execute in container
            environment: Additional environment variables

        Returns:
            Container ID

        Raises:
            DockerException: If container fails to start
        """
        container_name = f"sleeper-{job_type}-{job_id[:8]}"

        # Base environment
        env = {
            "CUDA_VISIBLE_DEVICES": "0",
            "NVIDIA_VISIBLE_DEVICES": "all",
            "NVIDIA_DRIVER_CAPABILITIES": "compute,utility",
            "HF_HOME": "/models/huggingface_cache",
            "TRANSFORMERS_CACHE": "/models/transformers_cache",
            "SLEEPER_CACHE": "/models/sleeper_cache",
        }

        if environment:
            env.update(environment)

        try:
            # Get the sleeper-eval-gpu image
            # In production, this would use docker-compose, but for direct control we use the API
            container: Container = self.client.containers.run(
                image="sleeper-agents:gpu",
                command=command,
                name=container_name,
                detach=True,
                remove=False,  # Don't auto-remove so we can get logs
                environment=env,
                volumes={
                    settings.models_volume: {"bind": "/models", "mode": "rw"},
                    settings.results_volume: {"bind": "/results", "mode": "rw"},
                    str(Path.cwd().parent.absolute()): {"bind": "/app", "mode": "rw"},  # Mount source code
                },
                working_dir="/app",
                runtime="nvidia",  # Enable GPU
                device_requests=[docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])],  # type: ignore  # All GPUs
                stdin_open=True,
                tty=True,
            )

            logger.info("Started container %s for job %s", container.id, job_id)
            return container.id  # type: ignore

        except DockerException as e:
            logger.error("Failed to start container for job %s: %s", job_id, e)
            raise

    def get_container_status(self, container_id: str) -> str:
        """Get container status.

        Args:
            container_id: Docker container ID

        Returns:
            Container status (running, exited, etc.)

        Raises:
            NotFound: If container not found
        """
        try:
            container = self.client.containers.get(container_id)
            return container.status  # type: ignore
        except NotFound:
            logger.warning("Container %s not found", container_id)
            raise

    def stop_container(self, container_id: str, timeout: int = 10):
        """Stop a running container.

        Args:
            container_id: Docker container ID
            timeout: Seconds to wait before killing

        Raises:
            NotFound: If container not found
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info("Stopped container %s", container_id)
        except NotFound:
            logger.warning("Container %s not found", container_id)
            raise

    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """Get container logs.

        Args:
            container_id: Docker container ID
            tail: Number of lines to retrieve

        Returns:
            Log output as string

        Raises:
            NotFound: If container not found
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode("utf-8", errors="replace")  # type: ignore
        except NotFound:
            logger.warning("Container %s not found", container_id)
            raise

    async def stream_container_logs(
        self,
        container_id: str,
        follow: bool = True,
    ) -> AsyncGenerator[str, None]:
        """Stream container logs asynchronously.

        Args:
            container_id: Docker container ID
            follow: Continue streaming until container stops

        Yields:
            Log lines

        Raises:
            NotFound: If container not found
        """
        try:
            container = self.client.containers.get(container_id)

            for line in container.logs(stream=True, follow=follow, timestamps=True):
                decoded_line = line.decode("utf-8", errors="replace").strip()
                yield decoded_line

                # Small async pause to prevent blocking
                await asyncio.sleep(0.01)

        except NotFound:
            logger.warning("Container %s not found", container_id)
            raise

    def cleanup_container(self, container_id: str, force: bool = True):
        """Remove a stopped container.

        Args:
            container_id: Docker container ID
            force: Force removal even if running

        Raises:
            NotFound: If container not found
        """
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            logger.info("Removed container %s", container_id)
        except NotFound:
            logger.warning("Container %s not found", container_id)

    def get_container_exit_code(self, container_id: str) -> Optional[int]:
        """Get container exit code.

        Args:
            container_id: Docker container ID

        Returns:
            Exit code or None if still running

        Raises:
            NotFound: If container not found
        """
        try:
            container = self.client.containers.get(container_id)
            container.reload()

            if container.status == "exited":
                return container.attrs["State"]["ExitCode"]  # type: ignore
            return None

        except NotFound:
            logger.warning("Container %s not found", container_id)
            raise

    def get_gpu_info(self) -> Dict:
        """Get GPU information using nvidia-smi.

        Returns:
            Dict with GPU stats (memory, utilization, count)
        """
        try:
            # Run nvidia-smi in a container to get GPU info
            result = self.client.containers.run(
                image="nvidia/cuda:11.8.0-base-ubuntu22.04",
                command="nvidia-smi --query-gpu=memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits",
                remove=True,
                runtime="nvidia",
                device_requests=[docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])],  # type: ignore
            )

            output = result.decode("utf-8").strip()
            lines = output.split("\n")

            gpus = []
            for line in lines:
                parts = line.split(",")
                if len(parts) == 3:
                    mem_total, mem_used, util = map(float, parts)
                    gpus.append({"memory_total_mb": mem_total, "memory_used_mb": mem_used, "utilization": util})

            return {"gpu_count": len(gpus), "gpus": gpus, "gpu_available": len(gpus) > 0}

        except Exception as e:
            logger.error("Failed to get GPU info: %s", e)
            return {"gpu_count": 0, "gpus": [], "gpu_available": False}
