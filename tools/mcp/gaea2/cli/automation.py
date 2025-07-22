"""Gaea2 CLI automation for running projects"""

import asyncio
import json  # noqa: F401
import logging
import os  # noqa: F401
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import Gaea2FileError


class Gaea2CLIAutomation:
    """Automate Gaea2 via command line interface"""

    def __init__(self, gaea_path: Optional[Path] = None):
        self.logger = logging.getLogger(__name__)
        self.gaea_path = gaea_path

        if not self.gaea_path:
            self.logger.warning("Gaea2 path not provided. CLI automation will be limited.")

    async def run_project(
        self,
        project_path: str,
        resolution: str = "1024",
        output_format: str = "exr",
        bake_only: Optional[List[str]] = None,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Run a Gaea2 project and generate terrain outputs"""

        if not self.gaea_path:
            return {"success": False, "error": "Gaea2 executable path not configured"}

        project_path_obj = Path(project_path)
        if not project_path_obj.exists():
            raise Gaea2FileError(
                f"Project file not found: {project_path_obj}",
                file_path=str(project_path_obj),
            )

        try:
            # Prepare output directory
            output_dir = project_path_obj.parent / f"output_{project_path_obj.stem}"
            output_dir.mkdir(exist_ok=True)

            # Build command
            cmd = [
                str(self.gaea_path),
                str(project_path_obj),
                f"--resolution={resolution}",
                f"--format={output_format}",
                f"--output={output_dir}",
                "--silent",  # Minimize console output
            ]

            # Add specific nodes to bake if provided
            if bake_only:
                cmd.extend([f"--bake={node}" for node in bake_only])
            else:
                cmd.append("--bakeall")  # Bake all nodes

            self.logger.info(f"Running Gaea2 command: {' '.join(cmd)}")

            # Run the command
            start_time = datetime.now()

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "success": False,
                    "error": f"Process timed out after {timeout} seconds",
                }

            execution_time = (datetime.now() - start_time).total_seconds()

            # Check results
            if process.returncode == 0:
                # Find generated files
                output_files = list(output_dir.glob(f"*.{output_format}"))

                return {
                    "success": True,
                    "output_dir": str(output_dir),
                    "output_files": [str(f) for f in output_files],
                    "execution_time": execution_time,
                    "stdout": stdout.decode("utf-8", errors="ignore"),
                    "stderr": stderr.decode("utf-8", errors="ignore"),
                }
            else:
                return {
                    "success": False,
                    "error": f"Gaea2 exited with code {process.returncode}",
                    "stdout": stdout.decode("utf-8", errors="ignore"),
                    "stderr": stderr.decode("utf-8", errors="ignore"),
                    "execution_time": execution_time,
                }

        except Exception as e:
            self.logger.error(f"Failed to run Gaea2 project: {str(e)}")
            return {"success": False, "error": str(e)}

    async def validate_installation(self) -> Dict[str, Any]:
        """Validate Gaea2 installation"""

        if not self.gaea_path:
            return {"valid": False, "error": "Gaea2 path not configured"}

        if not self.gaea_path.exists():
            return {
                "valid": False,
                "error": f"Gaea2 executable not found at {self.gaea_path}",
            }

        try:
            # Try to get version
            result = subprocess.run(
                [str(self.gaea_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            return {
                "valid": True,
                "path": str(self.gaea_path),
                "version": (result.stdout.strip() if result.returncode == 0 else "Unknown"),
            }

        except Exception as e:
            return {"valid": False, "error": f"Failed to validate Gaea2: {str(e)}"}

    def get_cli_help(self) -> Dict[str, Any]:
        """Get Gaea2 CLI help information"""

        if not self.gaea_path:
            return {"success": False, "error": "Gaea2 path not configured"}

        try:
            result = subprocess.run(
                [str(self.gaea_path), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            return {"success": True, "help_text": result.stdout}

        except Exception as e:
            return {"success": False, "error": str(e)}
