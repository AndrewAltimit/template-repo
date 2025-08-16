"""Blender subprocess execution manager."""

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from .status_manager import StatusManager

logger = logging.getLogger(__name__)


class BlenderExecutor:
    """Manages Blender subprocess execution."""

    def __init__(
        self,
        blender_path: str = "/opt/blender/blender",
        output_dir: str = "/app/outputs",
        base_dir: str = "/app",
    ):
        """Initialize Blender executor.

        Args:
            blender_path: Path to Blender executable
            output_dir: Directory for output files
            base_dir: Base working directory
        """
        self.blender_path = blender_path
        self.output_dir = Path(output_dir)
        self.base_dir = Path(base_dir)
        self.processes: Dict[str, asyncio.subprocess.Process] = {}  # Track running processes by job_id
        # In Docker, scripts are at /app/blender/scripts
        # Locally, they're at parent.parent/scripts
        # Check both locations
        docker_script_dir = Path("/app/blender/scripts")
        local_script_dir = Path(__file__).parent.parent / "scripts"

        if docker_script_dir.exists():
            self.script_dir = docker_script_dir
        else:
            self.script_dir = local_script_dir

        # Initialize status manager
        self.status_manager = StatusManager(output_dir)

        # Limit concurrent Blender processes to prevent resource exhaustion
        # Use half the CPU cores or minimum 1
        max_concurrent = max(1, (os.cpu_count() or 4) // 2)
        self.concurrency_limit = asyncio.Semaphore(max_concurrent)
        logger.info(f"Blender executor initialized with max {max_concurrent} concurrent processes")

        # Verify Blender installation
        if not Path(blender_path).exists():
            # Try to find Blender in PATH
            result = subprocess.run(["which", "blender"], capture_output=True, text=True)
            if result.returncode == 0:
                self.blender_path = result.stdout.strip()
            else:
                logger.warning(f"Blender not found at {blender_path}")

    async def execute_script(
        self,
        script_name: str,
        arguments: Dict[str, Any],
        job_id: str,
        background: bool = True,
    ) -> Dict[str, Any]:
        """Execute a Blender Python script.

        Args:
            script_name: Name of the script in scripts/ directory
            arguments: Arguments to pass to the script
            job_id: Unique job identifier
            background: Run Blender in background mode

        Returns:
            Execution result
        """
        logger.info(f"Executing script {script_name} for job {job_id}")
        logger.info(f"Script dir: {self.script_dir}")
        script_path = self.script_dir / script_name
        logger.info(f"Script path: {script_path}")

        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            files = list(self.script_dir.glob("*")) if self.script_dir.exists() else []
            logger.error(f"Available files in {self.script_dir}: {files or 'Directory does not exist'}")
            raise FileNotFoundError(f"Script not found: {script_path}")

        # Create temporary file for arguments in a directory accessible to Blender
        # Use the output directory which is persistent
        temp_dir = Path(self.output_dir) / "temp"
        temp_dir.mkdir(exist_ok=True)
        args_file = str(temp_dir / f"{job_id}_args.json")

        with open(args_file, "w") as f:
            json.dump(arguments, f)

        # Build Blender command
        cmd = [self.blender_path]

        if background:
            cmd.append("--background")

        # Add project file if specified (Blender loads .blend files directly)
        if "project" in arguments and Path(arguments["project"]).exists():
            cmd.append(arguments["project"])

        # Add Python script
        cmd.extend(["--python", str(script_path)])

        # Pass arguments file path and job_id as script arguments after --
        cmd.extend(["--", args_file, job_id])

        # Acquire semaphore to limit concurrent processes
        async with self.concurrency_limit:
            try:
                # Check if Blender exists
                if not Path(self.blender_path).exists():
                    raise FileNotFoundError(f"Blender not found at {self.blender_path}")

                # Update status using centralized manager
                self.status_manager.update_status(
                    job_id,
                    status="RUNNING",
                    progress=0,
                    message="Starting Blender process",
                )

                # Log the command for debugging
                logger.info(f"Running command: {' '.join(cmd)}")

                # Start process
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.base_dir),
                )

                # Store process reference and args file for cleanup
                self.processes[job_id] = process

                # Monitor process output and cleanup args file when done
                asyncio.create_task(self._monitor_process(process, job_id, args_file))

                return {"success": True, "job_id": job_id, "pid": process.pid}

            except Exception as e:
                logger.error(f"Failed to execute script: {e}")

                # Update status using centralized manager
                self.status_manager.update_status(job_id, status="FAILED", error=str(e))

                raise

            finally:
                # Args file cleanup moved to _monitor_process
                pass

    async def _monitor_process(self, process: asyncio.subprocess.Process, job_id: str, args_file: Optional[str] = None):
        """Monitor a running Blender process.

        Args:
            process: The subprocess to monitor
            job_id: Job identifier
            args_file: Temporary arguments file to cleanup when done
        """
        try:
            # Read output streams
            stdout, stderr = await process.communicate()

            # Log Blender output for debugging
            if stdout:
                logger.info(f"Blender stdout for job {job_id}: {stdout.decode()[:500]}")
            if stderr:
                logger.warning(f"Blender stderr for job {job_id}: {stderr.decode()[:500]}")

            # Check exit code
            if process.returncode == 0:
                # Success - update using centralized manager
                self.status_manager.update_status(
                    job_id,
                    status="COMPLETED",
                    progress=100,
                    message="Process completed successfully",
                )

                # Check for output file
                output_path = self.output_dir / f"{job_id}.png"
                if output_path.exists():
                    self.status_manager.update_status(job_id, status="COMPLETED", output_path=str(output_path))

            else:
                # Error - update using centralized manager
                error_msg = stderr.decode() if stderr else "Unknown error"
                self.status_manager.update_status(
                    job_id,
                    status="FAILED",
                    error=f"{error_msg} (exit code: {process.returncode})",
                )
                logger.error(f"Blender process failed: {error_msg}")

        except Exception as e:
            logger.error(f"Error monitoring process: {e}")
            self.status_manager.update_status(job_id, status="FAILED", error=str(e))

        finally:
            # Remove from active processes
            if job_id in self.processes:
                del self.processes[job_id]

            # Clean up arguments file
            if args_file and os.path.exists(args_file):
                try:
                    os.remove(args_file)
                    logger.debug(f"Cleaned up args file: {args_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup args file {args_file}: {e}")

    def kill_process(self, job_id: str) -> bool:
        """Kill a running Blender process.

        Args:
            job_id: Job identifier

        Returns:
            True if process was killed, False otherwise
        """
        if job_id in self.processes:
            process = self.processes[job_id]
            try:
                process.terminate()
                # Give it time to terminate gracefully
                asyncio.create_task(self._wait_and_kill(process))
                return True
            except Exception as e:
                logger.error(f"Failed to kill process: {e}")
                return False
        return False

    async def _wait_and_kill(self, process: asyncio.subprocess.Process):
        """Wait for process to terminate, then force kill if needed.

        Args:
            process: Process to kill
        """
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Force kill
            process.kill()
            await process.wait()

    def get_blender_version(self) -> Optional[str]:
        """Get installed Blender version.

        Returns:
            Version string or None if Blender not found
        """
        try:
            result = subprocess.run(
                [self.blender_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse version from output
                lines = result.stdout.split("\n")
                if lines:
                    return lines[0].replace("Blender", "").strip()
            return None
        except Exception as e:
            logger.error(f"Failed to get Blender version: {e}")
            return None

    def validate_installation(self) -> bool:
        """Validate Blender installation.

        Returns:
            True if Blender is properly installed
        """
        version = self.get_blender_version()
        if version:
            logger.info(f"Blender {version} found at {self.blender_path}")
            return True
        else:
            logger.error("Blender installation not found or invalid")
            return False
