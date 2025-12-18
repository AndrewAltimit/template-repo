"""Gaea2 CLI automation for running projects

Updated for Gaea.Swarm.exe 2.2.6.0 CLI arguments.
"""

import asyncio
from datetime import datetime
import logging
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional

from mcp_gaea2.exceptions import Gaea2FileError


class Gaea2CLIAutomation:
    """Automate Gaea2 via command line interface

    Supports Gaea.Swarm.exe 2.2.6.0 with the following options:
    - --Filename: Path to terrain file (required)
    - --buildpath: Output directory
    - --resolution: Override build resolution
    - --profile: Build profile to use
    - --region: Specific region to build
    - --seed: Mutation seed for variations
    - --node: Target specific node
    - -v: Variable assignments (key:value)
    - --silent: Disable interactivity
    - --ignorecache: Force rebuild ignoring cache
    - --verbose: Enable diagnostic logging
    """

    def __init__(self, gaea_path: Optional[Path] = None):
        self.logger = logging.getLogger(__name__)
        self.gaea_path = gaea_path

        if not self.gaea_path:
            self.logger.warning("Gaea2 path not provided. CLI automation will be limited.")

    async def run_project(
        self,
        project_path: str,
        resolution: str = "1024",
        build_path: Optional[str] = None,
        profile: Optional[str] = None,
        region: Optional[str] = None,
        seed: Optional[int] = None,
        target_node: Optional[int] = None,
        variables: Optional[Dict[str, str]] = None,
        ignore_cache: bool = False,
        verbose: bool = False,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Run a Gaea2 project and generate terrain outputs

        Args:
            project_path: Path to the .terrain file
            resolution: Build resolution (512, 1024, 2048, 4096, 8192)
            build_path: Output directory (defaults to output_<project_name>)
            profile: Build profile name defined in the project
            region: Specific region to build
            seed: Mutation seed for terrain variations
            target_node: Specific node index to target
            variables: Dict of variable name:value pairs
            ignore_cache: Force rebuild ignoring baked cache
            verbose: Enable verbose diagnostic logging
            timeout: Maximum execution time in seconds

        Returns:
            Dict with success status, output files, and execution details
        """
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
            if build_path:
                output_dir = Path(build_path)
            else:
                output_dir = project_path_obj.parent / f"output_{project_path_obj.stem}"
            output_dir.mkdir(exist_ok=True)

            # Build command for Gaea.Swarm.exe 2.2.6.0
            cmd = [
                str(self.gaea_path),
                "--Filename",
                str(project_path_obj),
                "--resolution",
                resolution,
                "--buildpath",
                str(output_dir),
                "--silent",  # Required for automation
            ]

            # Add optional parameters
            if profile:
                cmd.extend(["--profile", profile])

            if region:
                cmd.extend(["--region", region])

            if seed is not None:
                cmd.extend(["--seed", str(seed)])

            if target_node is not None:
                cmd.extend(["--node", str(target_node)])

            if variables:
                for key, value in variables.items():
                    cmd.extend(["-v", f"{key}:{value}"])

            if ignore_cache:
                cmd.append("--ignorecache")

            if verbose:
                cmd.append("--verbose")

            self.logger.info("Running Gaea2 command: %s", " ".join(cmd))

            # Run the command
            start_time = datetime.now()

            # Gaea.Swarm.exe requires console access - piping breaks it
            # Run without capturing output to preserve console handle
            # Output files will be checked after execution
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=None,  # Don't pipe - let it use console
                stderr=None,
            )

            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "success": False,
                    "error": f"Process timed out after {timeout} seconds",
                }

            execution_time = (datetime.now() - start_time).total_seconds()

            # Check results - output not captured to preserve console access
            if process.returncode == 0:
                # Find generated files (check common output formats)
                output_files: list[Path] = []
                for ext in ["exr", "png", "tiff", "tif", "raw", "r16", "r32"]:
                    output_files.extend(output_dir.glob(f"*.{ext}"))

                return {
                    "success": True,
                    "output_dir": str(output_dir),
                    "output_files": [str(f) for f in output_files],
                    "file_count": len(output_files),
                    "execution_time": execution_time,
                    "note": "Console output not captured to preserve Gaea2 console access",
                }

            return {
                "success": False,
                "error": f"Gaea2 exited with code {process.returncode}",
                "execution_time": execution_time,
                "note": "Console output not captured - check Gaea2 console window",
            }

        except Exception as e:
            self.logger.error("Failed to run Gaea2 project: %s", str(e))
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
                check=False,
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
                check=False,
            )

            return {"success": True, "help_text": result.stdout}

        except Exception as e:
            return {"success": False, "error": str(e)}
