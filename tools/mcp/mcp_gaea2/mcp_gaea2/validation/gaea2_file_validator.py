#!/usr/bin/env python3
"""
Gaea2 File Validator
Automated system to test if generated .terrain files actually open in Gaea2
"""

import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Gaea2FileValidator:
    """Validates Gaea2 terrain files by actually opening them in Gaea2"""

    def __init__(self, gaea_path: Optional[Path] = None):
        """
        Initialize the validator

        Args:
            gaea_path: Path to Gaea.Swarm.exe. If not provided, uses GAEA2_PATH env var
        """
        if gaea_path:
            self.gaea_path = gaea_path
        else:
            env_path = os.environ.get("GAEA2_PATH")
            if env_path:
                self.gaea_path = Path(env_path)
            else:
                raise EnvironmentError("GAEA2_PATH environment variable not set")

        if not self.gaea_path.exists():
            raise FileNotFoundError(f"Gaea2 executable not found at {self.gaea_path}")

        # Validation history
        self.validation_history: List[Dict[str, Any]] = []

        # Error patterns that indicate file loading failures
        self.error_patterns = {
            "file_corrupt": r"corrupt|damaged|invalid file",
            "missing_nodes": r"node.*not found|missing node",
            "invalid_properties": r"property.*invalid|unknown property",
            "version_mismatch": r"version.*not supported|incompatible version",
            "connection_error": r"connection.*invalid|port.*not found",
            "general_load_error": r"failed to load|cannot open|unable to read",
            "memory_error": r"out of memory|insufficient memory",
            "parse_error": r"parse error|syntax error|malformed",
        }

    def _get_validation_patterns(self, file_path: str) -> tuple:
        """Get success and failure patterns for validation."""
        success_patterns = [
            r"Opening.*" + os.path.basename(file_path).replace(".", r"\."),
            r"Loading devices",
            r"Activated.*processor",
            r"Preparing Gaea",
        ]
        failure_patterns = [
            r"corrupt|damaged",
            r"failed to load",
            r"cannot open",
            r"missing.*data",
            r"invalid file",
            r"error.*loading",
        ]
        return success_patterns, failure_patterns

    async def _wait_for_validation(self, process, timeout: float, error_detected: bool, success_detected: bool) -> tuple:
        """Wait for validation to complete with timeout handling."""
        wait_time = 0.0
        check_interval = 0.5
        post_opening_wait = 3.0
        opening_detected_time = None

        while wait_time < timeout:
            if error_detected:
                logger.info("Error detected, terminating validation")
                break
            if success_detected and not opening_detected_time:
                opening_detected_time = wait_time
                logger.info("Success pattern detected at %ss, waiting %ss to confirm...", wait_time, post_opening_wait)
            if opening_detected_time and (wait_time - opening_detected_time) >= post_opening_wait:
                logger.info("File opened successfully with no errors following")
                break
            if process.returncode is not None:
                break
            await asyncio.sleep(check_interval)
            wait_time += check_interval

        return wait_time, opening_detected_time

    def _determine_success(
        self,
        error_detected: bool,
        success_detected: bool,
        error_message: Optional[str],
        wait_time: float,
        timeout: float,
        stdout_data: List[str],
        return_code: Optional[int],
    ) -> tuple:
        """Determine final success status and error message."""
        if error_detected:
            return False, error_message or "File validation failed"
        if success_detected and not error_detected:
            return True, None
        if wait_time >= timeout:
            if any("Opening" in line for line in stdout_data):
                return True, None
            return False, "Validation timed out without clear success/failure"
        success = return_code == 0
        return success, "Process ended without clear result" if not success else None

    async def validate_file(self, file_path: str, timeout: int = 30, _capture_screenshot: bool = False) -> Dict[str, Any]:
        """
        Validate a single Gaea2 terrain file

        Args:
            file_path: Path to the .terrain file
            timeout: Maximum time to wait for validation (seconds)
            capture_screenshot: Whether to capture a screenshot if file opens

        Returns:
            Dictionary with validation results
        """
        start_time = datetime.now()

        if not os.path.exists(file_path):
            return {
                "success": False,
                "file_path": file_path,
                "error": "File not found",
                "duration": 0,
                "timestamp": start_time.isoformat(),
            }

        cmd = [
            str(self.gaea_path),
            "--Filename",
            str(file_path),
            "--validate",
            "--silent",
            "--timeout",
            str(timeout * 1000),
        ]

        logger.info("Validating file: %s", file_path)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(file_path),
            )

            stdout_data: List[str] = []
            stderr_data: List[str] = []
            success_detected = False
            error_detected = False
            error_message: Optional[str] = None

            success_patterns, failure_patterns = self._get_validation_patterns(file_path)

            async def read_stream(stream, data_list, is_stderr=False):
                nonlocal success_detected, error_detected, error_message
                while True:
                    try:
                        line = await asyncio.wait_for(stream.readline(), timeout=0.1)
                        if not line:
                            break
                        line_text = line.decode("utf-8", errors="replace").strip()
                        if not line_text:
                            continue
                        data_list.append(line_text)
                        logger.debug("%s: %s", "stderr" if is_stderr else "stdout", line_text)

                        for pattern in success_patterns:
                            if re.search(pattern, line_text, re.IGNORECASE):
                                success_detected = True
                                logger.info("Success pattern detected: %s", line_text)
                        for pattern in failure_patterns:
                            if re.search(pattern, line_text, re.IGNORECASE):
                                error_detected = True
                                error_message = line_text
                                logger.info("Error pattern detected: %s", line_text)
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        break

            stdout_task = asyncio.create_task(read_stream(process.stdout, stdout_data))
            stderr_task = asyncio.create_task(read_stream(process.stderr, stderr_data, True))

            wait_time, _ = await self._wait_for_validation(process, timeout, error_detected, success_detected)

            if process.returncode is None:
                logger.info("Terminating Gaea2 process")
                process.kill()
                await process.wait()

            stdout_task.cancel()
            stderr_task.cancel()
            try:
                await stdout_task
                await stderr_task
            except asyncio.CancelledError:
                pass

            stdout_text = "\n".join(stdout_data)
            stderr_text = "\n".join(stderr_data)

            success, error = self._determine_success(
                error_detected, success_detected, error_message, wait_time, timeout, stdout_data, process.returncode
            )
            error_info = self._parse_errors(stdout_text + stderr_text) if not success else None
            duration = (datetime.now() - start_time).total_seconds()

            result = {
                "success": success,
                "file_path": file_path,
                "return_code": process.returncode,
                "duration": duration,
                "timestamp": start_time.isoformat(),
                "stdout": stdout_text,
                "stderr": stderr_text,
                "error": error,
                "error_info": error_info,
                "success_detected": success_detected,
                "error_detected": error_detected,
            }

            self.validation_history.append(result)
            return result

        except Exception as e:
            logger.error("Error validating file %s: %s", file_path, e)
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e),
                "error_type": "exception",
                "duration": (datetime.now() - start_time).total_seconds(),
                "timestamp": start_time.isoformat(),
            }

    def _parse_errors(self, output: str) -> Dict[str, Any]:
        """Parse error messages from Gaea2 output"""
        error_info: Dict[str, Any] = {
            "error_types": [],
            "error_messages": [],
            "line_numbers": [],
        }

        # Check for known error patterns
        for error_type, pattern in self.error_patterns.items():
            if re.search(pattern, output, re.IGNORECASE):
                error_info["error_types"].append(error_type)

        # Extract error messages (lines containing ERROR, Error, or FAILED)
        error_lines = []
        for line in output.split("\n"):
            if any(marker in line for marker in ["ERROR", "Error", "FAILED", "Failed"]):
                error_lines.append(line.strip())

                # Try to extract line numbers
                line_match = re.search(r"line\s*(\d+)", line, re.IGNORECASE)
                if line_match:
                    error_info["line_numbers"].append(int(line_match.group(1)))

        error_info["error_messages"] = error_lines

        # Try to identify specific node/property issues
        node_match = re.search(
            r'node\s*["\']?(\w+)["\']?\s*(?:is\s*)?(?:invalid|not found|missing)',
            output,
            re.IGNORECASE,
        )
        if node_match:
            error_info["problematic_node"] = node_match.group(1)

        prop_pattern = r'property\s*["\']?(\w+)["\']?\s*' + r"(?:is\s*)?(?:invalid|unknown|not supported)"
        prop_match = re.search(prop_pattern, output, re.IGNORECASE)
        if prop_match:
            error_info["problematic_property"] = prop_match.group(1)

        return error_info

    async def validate_batch(self, file_paths: List[str], concurrent: int = 4, stop_on_error: bool = False) -> Dict[str, Any]:
        """
        Validate multiple files in batch

        Args:
            file_paths: List of file paths to validate
            concurrent: Number of concurrent validations
            stop_on_error: Stop batch if any validation fails

        Returns:
            Summary of batch validation results
        """
        logger.info("Starting batch validation of %s files", len(file_paths))

        results = []
        semaphore = asyncio.Semaphore(concurrent)

        async def validate_with_semaphore(file_path):
            async with semaphore:
                result = await self.validate_file(file_path)
                if stop_on_error and not result["success"]:
                    raise ValueError(f"Validation failed for {file_path}")
                return result

        # Run validations
        if stop_on_error:
            # Sequential processing with stop on error
            for file_path in file_paths:
                try:
                    result = await validate_with_semaphore(file_path)
                    results.append(result)
                except Exception as e:
                    logger.error("Batch stopped due to error: %s", e)
                    break
        else:
            # Concurrent processing
            tasks = [validate_with_semaphore(fp) for fp in file_paths]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions
            results = [r for r in results if isinstance(r, dict)]

        # Generate summary
        summary: Dict[str, Any] = {
            "total_files": len(file_paths),
            "validated": len(results),
            "successful": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "error_types": {},
            "common_errors": [],
            "results": results,
        }

        # Analyze error patterns
        for result in results:
            if not result["success"] and result.get("error_info"):
                for error_type in result["error_info"].get("error_types", []):
                    summary["error_types"][error_type] = summary["error_types"].get(error_type, 0) + 1

        # Find most common errors
        if summary["error_types"]:
            summary["common_errors"] = sorted(summary["error_types"].items(), key=lambda x: x[1], reverse=True)[:5]

        return summary

    async def validate_template(
        self,
        template_name: str,
        server_url: str = "http://localhost:8007",
        variations: int = 5,
    ) -> Dict[str, Any]:
        """
        Validate multiple variations of a template

        Args:
            template_name: Name of the template to test
            server_url: URL of the Gaea2 MCP server
            variations: Number of variations to test

        Returns:
            Validation results for the template
        """
        logger.info("Validating template: %s with %s variations", template_name, variations)

        # Directory for test files
        test_dir = Path(tempfile.mkdtemp(prefix=f"gaea2_test_{template_name}_"))

        try:
            generated_files = []

            # Generate variations
            for i in range(variations):
                project_name = f"test_{template_name}_var{i}_{datetime.now().strftime('%H%M%S')}"

                # Call MCP server to generate file
                import requests

                payload = {
                    "tool": "create_gaea2_from_template",
                    "parameters": {
                        "template_name": template_name,
                        "project_name": project_name,
                        "output_path": str(test_dir / f"{project_name}.terrain"),
                    },
                }

                response = requests.post(f"{server_url}/mcp/execute", json=payload, timeout=30)
                result = response.json()

                if result.get("success"):
                    file_path = result.get("saved_path") or result.get("project_path")
                    if file_path and os.path.exists(file_path):
                        generated_files.append(file_path)
                    else:
                        logger.error("Generated file not found: %s", file_path)
                else:
                    logger.error("Failed to generate variation %s: %s", i, result.get("error"))

            # Validate all generated files
            if generated_files:
                validation_results = await self.validate_batch(generated_files)

                # Add template info
                validation_results["template_name"] = template_name
                validation_results["variations_tested"] = len(generated_files)

                return validation_results
            return {
                "template_name": template_name,
                "error": "Failed to generate any test files",
                "success": False,
            }

        finally:
            # Cleanup test directory
            if test_dir.exists():
                shutil.rmtree(test_dir)

    def analyze_failures(self) -> Dict[str, Any]:
        """Analyze validation history to identify failure patterns"""
        if not self.validation_history:
            return {"error": "No validation history available"}

        failures = [r for r in self.validation_history if not r["success"]]

        if not failures:
            return {
                "total_validations": len(self.validation_history),
                "failures": 0,
                "patterns": [],
            }

        # Analyze patterns
        patterns: Dict[str, Any] = {
            "error_types": {},
            "problematic_nodes": [],
            "problematic_properties": [],
            "file_characteristics": {},
        }

        for failure in failures:
            if failure.get("error_info"):
                # Count error types
                for error_type in failure["error_info"].get("error_types", []):
                    patterns["error_types"][error_type] = patterns["error_types"].get(error_type, 0) + 1

                # Track problematic nodes
                if "problematic_node" in failure["error_info"]:
                    patterns["problematic_nodes"].append(failure["error_info"]["problematic_node"])

                # Track problematic properties
                if "problematic_property" in failure["error_info"]:
                    patterns["problematic_properties"].append(failure["error_info"]["problematic_property"])

        # Find most common issues
        analysis = {
            "total_validations": len(self.validation_history),
            "failures": len(failures),
            "failure_rate": len(failures) / len(self.validation_history),
            "most_common_errors": sorted(patterns["error_types"].items(), key=lambda x: x[1], reverse=True),
            "problematic_nodes": list(set(patterns["problematic_nodes"])),
            "problematic_properties": list(set(patterns["problematic_properties"])),
        }

        return analysis

    def generate_report(self, output_path: Optional[str] = None) -> str:
        """Generate a detailed validation report"""
        analysis = self.analyze_failures()

        report = f"""
Gaea2 File Validation Report
Generated: {datetime.now().isoformat()}

SUMMARY
=======
Total Validations: {analysis.get('total_validations', 0)}
Successful: {analysis.get('total_validations', 0) - analysis.get('failures', 0)}
Failed: {analysis.get('failures', 0)}
Failure Rate: {analysis.get('failure_rate', 0):.1%}

MOST COMMON ERRORS
==================
"""

        for error_type, count in analysis.get("most_common_errors", [])[:10]:
            report += f"- {error_type}: {count} occurrences\n"

        if analysis.get("problematic_nodes"):
            report += "\nPROBLEMATIC NODES\n==================\n"
            for node in analysis["problematic_nodes"]:
                report += f"- {node}\n"

        if analysis.get("problematic_properties"):
            report += "\nPROBLEMATIC PROPERTIES\n=======================\n"
            for prop in analysis["problematic_properties"]:
                report += f"- {prop}\n"

        # Add detailed failure log
        report += "\n\nDETAILED FAILURE LOG\n====================\n"
        failures = [r for r in self.validation_history if not r["success"]]
        for i, failure in enumerate(failures[:20]):  # First 20 failures
            report += f"\n{i+1}. File: {Path(failure['file_path']).name}\n"
            report += f"   Error: {failure.get('error', 'Unknown')}\n"
            if failure.get("error_info") and failure["error_info"].get("error_messages"):
                report += "   Messages:\n"
                for msg in failure["error_info"]["error_messages"][:3]:
                    report += f"     - {msg}\n"

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info("Report saved to: %s", output_path)

        return report


# Integration function for MCP server
async def validate_gaea2_file(file_path: str, timeout: int = 30) -> Dict[str, Any]:
    """MCP tool function to validate a Gaea2 file"""
    validator = Gaea2FileValidator()
    return await validator.validate_file(file_path, timeout)


async def validate_gaea2_batch(file_paths: List[str], concurrent: int = 4) -> Dict[str, Any]:
    """MCP tool function to validate multiple Gaea2 files"""
    validator = Gaea2FileValidator()
    return await validator.validate_batch(file_paths, concurrent)


async def test_gaea2_template(
    template_name: str, variations: int = 5, server_url: str = "http://localhost:8007"
) -> Dict[str, Any]:
    """MCP tool function to test a Gaea2 template with variations"""
    validator = Gaea2FileValidator()
    return await validator.validate_template(template_name, server_url, variations)


# CLI interface for testing
if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("Usage: gaea2_file_validator.py <file_path> [file_path2 ...]")
            print("       gaea2_file_validator.py --template <template_name>")
            sys.exit(1)

        validator = Gaea2FileValidator()

        if sys.argv[1] == "--template":
            # Test template
            template_name = sys.argv[2]
            results = await validator.validate_template(template_name)
            print(json.dumps(results, indent=2))
        else:
            # Validate files
            file_paths = sys.argv[1:]
            if len(file_paths) == 1:
                result = await validator.validate_file(file_paths[0])
            else:
                result = await validator.validate_batch(file_paths)

            print(json.dumps(result, indent=2))

            # Generate report
            report = validator.generate_report()
            print("\n" + report)

    asyncio.run(main())
