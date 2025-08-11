"""Blender subprocess execution manager."""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class BlenderExecutor:
    """Manages Blender subprocess execution."""

    def __init__(self, blender_path: str = "/opt/blender/blender", output_dir: str = "/app/outputs", base_dir: str = "/app"):
        """Initialize Blender executor.

        Args:
            blender_path: Path to Blender executable
            output_dir: Directory for output files
            base_dir: Base working directory
        """
        self.blender_path = blender_path
        self.output_dir = Path(output_dir)
        self.base_dir = Path(base_dir)
        self.processes = {}  # Track running processes by job_id
        self.script_dir = Path(__file__).parent.parent / "scripts"

        # Verify Blender installation
        if not Path(blender_path).exists():
            # Try to find Blender in PATH
            result = subprocess.run(["which", "blender"], capture_output=True, text=True)
            if result.returncode == 0:
                self.blender_path = result.stdout.strip()
            else:
                logger.warning(f"Blender not found at {blender_path}")

    async def execute_script(
        self, script_name: str, arguments: Dict[str, Any], job_id: str, background: bool = True
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
        script_path = self.script_dir / script_name

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        # Create temporary file for arguments
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(arguments, f)
            args_file = f.name

        # Build Blender command
        cmd = [self.blender_path]

        if background:
            cmd.append("--background")

        # Add project file if specified
        if "project" in arguments:
            cmd.extend(["--", arguments["project"]])

        # Add Python script
        cmd.extend(["--python", str(script_path)])

        # Pass arguments file path
        cmd.extend(["--", args_file, job_id])

        try:
            # Check if Blender exists
            if not Path(self.blender_path).exists():
                raise FileNotFoundError(f"Blender not found at {self.blender_path}")

            # Create status file
            status_file = self.output_dir / f"{job_id}.status"
            status_file.parent.mkdir(parents=True, exist_ok=True)
            status_file.write_text(json.dumps({"status": "RUNNING", "progress": 0, "message": "Starting Blender process"}))

            # Start process
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=str(self.base_dir)
            )

            # Store process reference
            self.processes[job_id] = process

            # Monitor process output
            asyncio.create_task(self._monitor_process(process, job_id, status_file))

            return {"success": True, "job_id": job_id, "pid": process.pid}

        except Exception as e:
            logger.error(f"Failed to execute script: {e}")

            # Update status file if it was created
            try:
                if "status_file" in locals() and status_file.exists():
                    status_file.write_text(json.dumps({"status": "FAILED", "error": str(e)}))
            except Exception:
                pass  # Ignore errors updating status

            raise

        finally:
            # Clean up arguments file
            if os.path.exists(args_file):
                os.remove(args_file)

    async def _monitor_process(self, process: asyncio.subprocess.Process, job_id: str, status_file: Path):
        """Monitor a running Blender process.

        Args:
            process: The subprocess to monitor
            job_id: Job identifier
            status_file: Path to status file
        """
        try:
            # Read output streams
            stdout, stderr = await process.communicate()

            # Check exit code
            if process.returncode == 0:
                # Success
                status_file.write_text(
                    json.dumps({"status": "COMPLETED", "progress": 100, "message": "Process completed successfully"})
                )

                # Check for output file
                output_path = self.output_dir / f"{job_id}.png"
                if output_path.exists():
                    status_data = json.loads(status_file.read_text())
                    status_data["output_path"] = str(output_path)
                    status_file.write_text(json.dumps(status_data))

            else:
                # Error
                error_msg = stderr.decode() if stderr else "Unknown error"
                status_file.write_text(json.dumps({"status": "FAILED", "error": error_msg, "exit_code": process.returncode}))
                logger.error(f"Blender process failed: {error_msg}")

        except Exception as e:
            logger.error(f"Error monitoring process: {e}")
            status_file.write_text(json.dumps({"status": "FAILED", "error": str(e)}))

        finally:
            # Remove from active processes
            if job_id in self.processes:
                del self.processes[job_id]

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
            result = subprocess.run([self.blender_path, "--version"], capture_output=True, text=True, timeout=5)
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
