"""Content Creation MCP Server - Manim animations and LaTeX compilation"""

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional, Set

from mcp_core.base_server import BaseMCPServer
from mcp_core.utils import ensure_directory, setup_logging

# Constants for preview DPI
PREVIEW_DPI_STANDARD = 150  # Standard resolution
PREVIEW_DPI_HIGH = 300  # High resolution

# Container-to-host path mapping configuration
# Container path /output maps to host path outputs/mcp-content/
CONTAINER_OUTPUT_PREFIX = "/output"
HOST_OUTPUT_PREFIX = "outputs/mcp-content"


class ContentCreationMCPServer(BaseMCPServer):
    """MCP Server for content creation - Manim animations and LaTeX documents"""

    def __init__(self, output_dir: str = "/app/output"):
        super().__init__(
            name="Content Creation MCP Server",
            version="2.0.0",
            port=8011,
        )
        self.logger = setup_logging("ContentCreationMCP")

        # Use environment variable if set
        self.output_dir = os.environ.get("MCP_OUTPUT_DIR", output_dir)
        self.logger.info("Using output directory: %s", self.output_dir)

        try:
            # Create output directories with error handling
            self.manim_output_dir = ensure_directory(os.path.join(self.output_dir, "manim"))
            self.latex_output_dir = ensure_directory(os.path.join(self.output_dir, "latex"))
            self.preview_output_dir = ensure_directory(os.path.join(self.output_dir, "previews"))
            self.logger.info("Successfully created output directories")
        except Exception as e:
            self.logger.error("Failed to create output directories: %s", e)
            # Use temp directory as fallback
            temp_dir = tempfile.mkdtemp(prefix="mcp_content_")
            self.output_dir = temp_dir
            self.manim_output_dir = ensure_directory(os.path.join(temp_dir, "manim"))
            self.latex_output_dir = ensure_directory(os.path.join(temp_dir, "latex"))
            self.preview_output_dir = ensure_directory(os.path.join(temp_dir, "previews"))
            self.logger.warning("Using fallback temp directory: %s", temp_dir)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _to_project_relative_path(self, container_path: str) -> str:
        """Convert container-internal path to project-relative path.

        Args:
            container_path: Path inside container (e.g., /output/latex/doc.pdf)

        Returns:
            Project-relative path for host filesystem (e.g., outputs/mcp-content/latex/doc.pdf)

        Note:
            Container path /output maps to host path outputs/mcp-content/
            This is defined by docker-compose volume mount: ./outputs/mcp-content:/output
        """
        if container_path.startswith(CONTAINER_OUTPUT_PREFIX):
            relative_part = container_path[len(CONTAINER_OUTPUT_PREFIX) :].lstrip("/")
            return f"{HOST_OUTPUT_PREFIX}/{relative_part}" if relative_part else HOST_OUTPUT_PREFIX
        # Return as-is if not in container output directory
        return container_path

    def _convert_paths_in_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert all container paths in result dictionary to project-relative paths.

        Args:
            result: Result dictionary that may contain output_path or preview_paths

        Returns:
            Result dictionary with paths converted to project-relative format
        """
        if "output_path" in result and result["output_path"]:
            result["output_path"] = self._to_project_relative_path(result["output_path"])

        if "preview_paths" in result and result["preview_paths"]:
            result["preview_paths"] = [self._to_project_relative_path(p) for p in result["preview_paths"]]

        if "pdf_path" in result and result["pdf_path"]:
            result["pdf_path"] = self._to_project_relative_path(result["pdf_path"])

        return result

    def _resolve_input_path(self, input_path: str) -> str:
        """Resolve input path with clear error messages for common issues.

        Args:
            input_path: Path provided by user (absolute or relative)

        Returns:
            Resolved absolute path

        Raises:
            FileNotFoundError: If the path doesn't exist, with helpful message

        Path Resolution Rules:
            1. Absolute paths (starting with /) are used as-is
            2. Relative paths are resolved relative to /app (project root in container)
            3. In container: /app is the project root (read-only mount)
            4. On host: relative paths are resolved from current working directory
        """
        # If already absolute, use as-is
        if os.path.isabs(input_path):
            resolved = input_path
        else:
            # Resolve relative to /app in container (project root)
            # This matches the docker-compose volume mount: .:/app:ro
            app_dir = os.environ.get("MCP_APP_DIR", "/app")
            resolved = os.path.join(app_dir, input_path)

        if not os.path.exists(resolved):
            # Provide helpful error message
            error_msg = f"Input file not found: {input_path}"
            if not os.path.isabs(input_path):
                error_msg += (
                    f"\n\nPath Resolution Info:"
                    f"\n  - Relative paths are resolved from project root (/app in container)"
                    f"\n  - Resolved path: {resolved}"
                    f"\n  - Use absolute paths starting with / for explicit locations"
                    f"\n  - Example: 'docs/file.tex' resolves to '/app/docs/file.tex'"
                )
            raise FileNotFoundError(error_msg)

        return resolved

    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """Extract page count from PDF using pdfinfo.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Number of pages, or 0 if unable to determine
        """
        try:
            result = subprocess.run(
                ["pdfinfo", pdf_path],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("Pages:"):
                        return int(line.split(":")[1].strip())
        except Exception as e:
            self.logger.warning("Failed to get PDF page count: %s", e)
        return 0

    def _get_file_size_kb(self, file_path: str) -> float:
        """Get file size in KB.

        Args:
            file_path: Path to file

        Returns:
            File size in KB, or 0 if unable to determine
        """
        try:
            return os.path.getsize(file_path) / 1024
        except Exception:
            return 0

    def _parse_page_spec(self, spec: str, total_pages: int) -> List[int]:
        """Parse page specification string into list of page numbers.

        Args:
            spec: Page specification like "1", "1,3,5", "1-10", "all", or "none"
            total_pages: Total number of pages in document

        Returns:
            List of 1-indexed page numbers

        Examples:
            "1" -> [1]
            "1,3,5" -> [1, 3, 5]
            "1-5" -> [1, 2, 3, 4, 5]
            "all" -> [1, 2, ..., total_pages]
            "none" -> []
        """
        if not spec or spec.lower() == "none":
            return []

        if spec.lower() == "all":
            return list(range(1, total_pages + 1))

        pages: Set[int] = set()

        for part in spec.split(","):
            part = part.strip()
            if "-" in part:
                # Range: "1-5"
                try:
                    start, end = part.split("-")
                    start_page = max(1, int(start.strip()))
                    end_page = min(total_pages, int(end.strip()))
                    pages.update(range(start_page, end_page + 1))
                except ValueError:
                    self.logger.warning("Invalid page range: %s", part)
            else:
                # Single page
                try:
                    page = int(part)
                    if 1 <= page <= total_pages:
                        pages.add(page)
                except ValueError:
                    self.logger.warning("Invalid page number: %s", part)

        return sorted(pages)

    def _export_pages_to_png(
        self,
        pdf_path: str,
        pages: List[int],
        dpi: int = PREVIEW_DPI_STANDARD,
        output_dir: Optional[str] = None,
    ) -> List[str]:
        """Export specific pages from PDF to PNG files.

        Args:
            pdf_path: Path to PDF file
            pages: List of 1-indexed page numbers to export
            dpi: Resolution for output images
            output_dir: Directory for output files (default: preview_output_dir)

        Returns:
            List of paths to generated PNG files
        """
        if output_dir is None:
            output_dir = self.preview_output_dir

        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        png_paths: List[str] = []

        for page in pages:
            output_base = os.path.join(output_dir, f"{base_name}_page{page}")
            try:
                self._run_subprocess_with_logging(
                    [
                        "pdftoppm",
                        "-png",
                        "-f",
                        str(page),
                        "-l",
                        str(page),
                        "-r",
                        str(dpi),
                        "-singlefile",
                        pdf_path,
                        output_base,
                    ],
                    check=True,
                )
                png_path = f"{output_base}.png"
                if os.path.exists(png_path):
                    png_paths.append(png_path)
            except Exception as e:
                self.logger.warning("Failed to export page %d: %s", page, e)

        return png_paths

    def _generate_previews_if_requested(
        self,
        output_path: str,
        output_format: str,
        preview_pages: str,
        page_count: int,
        preview_dpi: int,
        response_mode: str,
        result_data: Dict[str, Any],
    ) -> List[str]:
        """Generate preview images if requested and update result_data.

        Args:
            output_path: Path to the compiled PDF
            output_format: Output format (only 'pdf' generates previews)
            preview_pages: Page specification string
            page_count: Total number of pages
            preview_dpi: DPI for preview images
            response_mode: Response verbosity level (minimal/standard)
            result_data: Result dictionary to update with preview data

        Returns:
            List of preview paths (empty if no previews generated)
        """
        if output_format != "pdf" or preview_pages == "none":
            return []

        pages_to_export = self._parse_page_spec(preview_pages, page_count)
        if not pages_to_export:
            return []

        preview_paths = self._export_pages_to_png(output_path, pages_to_export, dpi=preview_dpi)
        if not preview_paths:
            return []

        if response_mode == "standard":
            result_data["preview_paths"] = preview_paths

        return preview_paths

    def _finalize_compile_result(
        self,
        result_data: Dict[str, Any],
        output_format: str,
        compile_time: float,
        response_mode: str,
    ) -> None:
        """Add extra metadata to compile result based on response mode.

        Args:
            result_data: Result dictionary to update
            output_format: Output format extension
            compile_time: Time taken to compile
            response_mode: Response verbosity level (minimal/standard)
        """
        if response_mode == "standard":
            result_data["format"] = output_format
            result_data["compile_time_seconds"] = round(compile_time, 2)

    def _run_latex_compilation(self, compiler: str, tex_file: str, working_dir: str, output_format: str) -> Optional[str]:
        """Run the LaTeX compilation process.

        Args:
            compiler: Compiler command (pdflatex or latex)
            tex_file: Path to the .tex file
            working_dir: Working directory for compilation
            output_format: Output format extension

        Returns:
            Path to output file if successful, None otherwise

        Note:
            We intentionally do NOT use -halt-on-error because many LaTeX documents
            have non-fatal errors (font substitutions, overfull hboxes, etc.) that
            still produce valid output. The success is determined by whether the
            output file is generated, not by the return code.

            We use -no-shell-escape to prevent potential RCE via \\write18 commands
            in untrusted LaTeX content. This is a security hardening measure.
        """
        cmd = [compiler, "-interaction=nonstopmode", "-no-shell-escape", tex_file]

        # Run compilation twice for references
        for i in range(2):
            result = self._run_subprocess_with_logging(cmd, cwd=working_dir)
            if result.returncode != 0 and i == 0:
                self.logger.warning("First compilation pass had warnings/errors (this is often normal)")

        # Handle PS output (requires dvips)
        if output_format == "ps" and result.returncode == 0:
            dvi_file = tex_file.replace(".tex", ".dvi")
            ps_file = tex_file.replace(".tex", ".ps")
            self._run_subprocess_with_logging(["dvips", dvi_file, "-o", ps_file], cwd=working_dir)

        output_file = tex_file.replace(".tex", f".{output_format}")
        return output_file if os.path.exists(output_file) else None

    def _build_compile_success_response(
        self,
        output_file: str,
        output_format: str,
        start_time: float,
        preview_pages: str,
        preview_dpi: int,
        response_mode: str,
    ) -> Dict[str, Any]:
        """Build success response after compilation.

        Args:
            output_file: Path to the compiled output file
            output_format: Output format extension
            start_time: Timestamp when compilation started
            preview_pages: Page specification for previews
            preview_dpi: DPI for preview images
            response_mode: Response verbosity level (minimal/standard)

        Returns:
            Success result dictionary
        """
        # Copy to output directory with unique name
        timestamp = int(time.time())
        output_name = f"document_{timestamp}_{os.getpid()}.{output_format}"
        output_path = os.path.join(self.latex_output_dir, output_name)
        shutil.copy(output_file, output_path)

        # Get metadata
        page_count = self._get_pdf_page_count(output_path) if output_format == "pdf" else 0
        file_size_kb = self._get_file_size_kb(output_path)
        compile_time = time.time() - start_time

        # Build response
        result_data: Dict[str, Any] = {
            "success": True,
            "output_path": output_path,
            "page_count": page_count,
            "file_size_kb": round(file_size_kb, 2),
        }

        # Generate previews if requested (modifies result_data in place)
        self._generate_previews_if_requested(
            output_path, output_format, preview_pages, page_count, preview_dpi, response_mode, result_data
        )

        # Add extra metadata and finalize response
        self._finalize_compile_result(result_data, output_format, compile_time, response_mode)
        return result_data

    def _cleanup_latex_temp_files(self, tex_file: str, working_dir: str, keep_intermediate_files: bool = False) -> None:
        """Clean up temporary LaTeX files after compilation.

        Args:
            tex_file: Path to the .tex file
            working_dir: Working directory containing temp files
            keep_intermediate_files: If True, keep .aux, .log, etc. for debugging.
                                     If False (default), remove entire temp directory.

        Note:
            The default behavior (keep_intermediate_files=False) removes the entire
            temp directory. Set keep_intermediate_files=True to preserve intermediate
            files like .aux, .log, .out for debugging compilation issues.
        """
        if keep_intermediate_files:
            # Only remove the source .tex file, keep aux/log for debugging
            base = tex_file[:-4]
            for ext in [".tex", ".out", ".toc", ".dvi", ".ps"]:
                try:
                    temp_file = base + ext
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception:
                    pass
            # Keep .aux and .log for debugging
            self.logger.debug("Keeping intermediate files in: %s", working_dir)
        else:
            # Default: clean up entire temp directory
            try:
                shutil.rmtree(working_dir)
            except Exception as e:
                self.logger.warning("Failed to clean up temp directory %s: %s", working_dir, e)

    def _convert_pdf_to_image(self, pdf_path: str, output_format: str, response_mode: str) -> Dict[str, Any]:
        """Convert PDF to PNG or SVG format.

        Args:
            pdf_path: Path to source PDF (may be project-relative or container path)
            output_format: Target format ('png' or 'svg')
            response_mode: Response verbosity level (minimal/standard)

        Returns:
            Result dictionary with success status and project-relative output path
        """
        # Handle both project-relative and container paths for input
        # If the path is project-relative, we need to get the actual basename
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_path = os.path.join(self.latex_output_dir, f"{base_name}.{output_format}")

        # For conversion, we need the actual container path for the PDF
        # If it's project-relative, convert back for the subprocess
        actual_pdf_path = pdf_path
        if pdf_path.startswith(HOST_OUTPUT_PREFIX):
            # Convert project-relative back to container path for subprocess
            relative_part = pdf_path[len(HOST_OUTPUT_PREFIX) :].lstrip("/")
            actual_pdf_path = f"{CONTAINER_OUTPUT_PREFIX}/{relative_part}"

        if output_format == "png":
            self._run_subprocess_with_logging(
                ["pdftoppm", "-png", "-singlefile", "-r", str(PREVIEW_DPI_HIGH), actual_pdf_path, output_path[:-4]],
                check=True,
            )
        elif output_format == "svg":
            self._run_subprocess_with_logging(["pdf2svg", actual_pdf_path, output_path], check=True)

        if not os.path.exists(output_path):
            return {"success": False, "error": f"Conversion to {output_format} failed"}

        result_data: Dict[str, Any] = {
            "success": True,
            "output_path": output_path,
        }

        if response_mode == "standard":
            result_data["format"] = output_format

        # Convert container paths to project-relative paths
        return self._convert_paths_in_result(result_data)

    def _run_subprocess_with_logging(
        self, cmd: list, cwd: Optional[str] = None, check: bool = False
    ) -> subprocess.CompletedProcess:
        """Run subprocess command with proper logging and error handling.

        Args:
            cmd: Command to run as list
            cwd: Working directory for command
            check: Whether to raise exception on non-zero return code

        Returns:
            CompletedProcess result
        """
        self.logger.info("Running command: %s", " ".join(cmd))
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
            if result.returncode != 0:
                self.logger.warning("Command failed with return code %s: %s", result.returncode, result.stderr)
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error("Command failed: %s", e)
            raise
        except FileNotFoundError:
            self.logger.error("Command not found: %s", " ".join(cmd))
            raise

    def _wrap_content_with_template(self, content: str, template: str) -> str:
        """Wrap content with LaTeX template if needed."""
        if template == "custom" or content.startswith("\\documentclass"):
            return content

        templates = {
            "article": "\\documentclass{{article}}\n\\begin{{document}}\n{content}\n\\end{{document}}",
            "report": "\\documentclass{{report}}\n\\begin{{document}}\n{content}\n\\end{{document}}",
            "book": "\\documentclass{{book}}\n\\begin{{document}}\n{content}\n\\end{{document}}",
            "beamer": "\\documentclass{{beamer}}\n\\begin{{document}}\n{content}\n\\end{{document}}",
        }
        if template in templates:
            return templates[template].format(content=content)
        return content

    def _extract_latex_error(self, log_file: str) -> str:
        """Extract error message from LaTeX log file."""
        if not os.path.exists(log_file):
            return "Compilation failed"

        with open(log_file, "r", encoding="utf-8") as f:
            log_content = f.read()
            if "! " in log_content:
                error_lines = [line for line in log_content.split("\n") if line.startswith("!")]
                if error_lines:
                    return "\n".join(error_lines[:5])
        return "Compilation failed"

    # =========================================================================
    # Tool Definitions
    # =========================================================================

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available content creation tools"""
        return {
            "create_manim_animation": {
                "description": "Create mathematical animations using Manim",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "script": {
                            "type": "string",
                            "description": "Python script for Manim animation",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["mp4", "gif", "png", "webm"],
                            "default": "mp4",
                            "description": "Output format for the animation",
                        },
                    },
                    "required": ["script"],
                },
            },
            "compile_latex": {
                "description": "Compile LaTeX documents to various formats",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "LaTeX document content (alternative to input_path)",
                        },
                        "input_path": {
                            "type": "string",
                            "description": "Path to .tex file to compile (alternative to content)",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["pdf", "dvi", "ps"],
                            "default": "pdf",
                            "description": "Output format",
                        },
                        "template": {
                            "type": "string",
                            "enum": ["article", "report", "book", "beamer", "custom"],
                            "default": "custom",
                            "description": "Document template (ignored if content has documentclass)",
                        },
                        "response_mode": {
                            "type": "string",
                            "enum": ["minimal", "standard"],
                            "default": "standard",
                            "description": "minimal: path only. standard: +previews and metadata",
                        },
                        "preview_pages": {
                            "type": "string",
                            "default": "none",
                            "description": "Pages to preview: 'none', '1', '1,3,5', '1-5', 'all'",
                        },
                        "preview_dpi": {
                            "type": "integer",
                            "default": 150,
                            "description": "DPI for preview images (72=low, 150=standard, 300=high)",
                        },
                    },
                    "required": [],
                },
            },
            "render_tikz": {
                "description": "Render TikZ diagrams as standalone images",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tikz_code": {
                            "type": "string",
                            "description": "TikZ code for the diagram",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["pdf", "png", "svg"],
                            "default": "pdf",
                            "description": "Output format for the diagram",
                        },
                        "response_mode": {
                            "type": "string",
                            "enum": ["minimal", "standard"],
                            "default": "standard",
                            "description": "minimal: path only. standard: +metadata",
                        },
                    },
                    "required": ["tikz_code"],
                },
            },
            "preview_pdf": {
                "description": "Generate PNG previews from an existing PDF file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pdf_path": {
                            "type": "string",
                            "description": "Path to PDF file to preview",
                        },
                        "pages": {
                            "type": "string",
                            "default": "1",
                            "description": "Pages to preview: '1', '1,3,5', '1-5', 'all'",
                        },
                        "dpi": {
                            "type": "integer",
                            "default": 150,
                            "description": "Resolution for preview images",
                        },
                        "response_mode": {
                            "type": "string",
                            "enum": ["minimal", "standard"],
                            "default": "standard",
                            "description": "minimal: paths only. standard: +metadata",
                        },
                    },
                    "required": ["pdf_path"],
                },
            },
        }

    # =========================================================================
    # Tool Implementations
    # =========================================================================

    async def create_manim_animation(
        self,
        script: str,
        output_format: str = "mp4",
    ) -> Dict[str, Any]:
        """Create Manim animation from Python script.

        Args:
            script: Python script containing Manim scene
            output_format: Output format (mp4, gif, png, webm)

        Returns:
            Dictionary with animation file path and metadata
        """
        try:
            # Create temporary file for script
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(script)
                script_path = f.name

            # Use configured output directory, not hardcoded path
            cmd = ["manim", "-pql", "--media_dir", self.manim_output_dir, script_path]

            # Parse class name from script
            class_match = re.search(r"class\s+(\w+)\s*\(", script)
            if class_match:
                class_name = class_match.group(1)
                cmd.append(class_name)

            # Run Manim
            result = self._run_subprocess_with_logging(cmd)

            # Clean up script file
            os.unlink(script_path)

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Manim execution failed with exit code {result.returncode}: {result.stderr}",
                }

            # Find output file in configured output directory
            output_files: List[str] = []
            if os.path.exists(self.manim_output_dir):
                for root, _, files in os.walk(self.manim_output_dir):
                    output_files.extend(os.path.join(root, f) for f in files if f.endswith(f".{output_format}"))

            result_data: Dict[str, Any] = {
                "success": True,
                "format": output_format,
                "output_path": output_files[0] if output_files else None,
            }

            # Convert container paths to project-relative paths
            return self._convert_paths_in_result(result_data)

        except FileNotFoundError:
            return {
                "success": False,
                "error": "Manim not found. Please install it first.",
            }
        except Exception as e:
            self.logger.error("Manim error: %s", str(e))
            return {"success": False, "error": str(e)}

    async def compile_latex(
        self,
        content: Optional[str] = None,
        input_path: Optional[str] = None,
        output_format: str = "pdf",
        template: str = "custom",
        response_mode: str = "standard",
        preview_pages: str = "none",
        preview_dpi: int = PREVIEW_DPI_STANDARD,
    ) -> Dict[str, Any]:
        """Compile LaTeX document to various formats.

        Args:
            content: LaTeX document content (alternative to input_path)
            input_path: Path to .tex file to compile (alternative to content)
            output_format: Output format (pdf, dvi, ps)
            template: Document template to use
            response_mode: Level of detail in response (minimal/standard)
            preview_pages: Which pages to generate previews for
            preview_dpi: Resolution for preview images

        Returns:
            Dictionary with compiled document path and metadata
        """
        start_time = time.time()

        # Validate inputs
        if content is None and input_path is None:
            return {"success": False, "error": "Must provide either 'content' or 'input_path'"}

        if content is not None and input_path is not None:
            return {"success": False, "error": "Provide only one of 'content' or 'input_path', not both"}

        # Read content from file if input_path provided
        working_dir = None
        symlink_warnings: List[str] = []
        if input_path is not None:
            try:
                resolved_path = self._resolve_input_path(input_path)
                with open(resolved_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Use the directory containing the .tex file as working directory
                # This allows relative paths for \include, \input, images, etc.
                working_dir = os.path.dirname(resolved_path)
            except FileNotFoundError as e:
                return {"success": False, "error": str(e)}
            except Exception as e:
                return {"success": False, "error": f"Failed to read input file: {e}"}

        compiler = "pdflatex" if output_format == "pdf" else "latex"

        # At this point content is guaranteed to be str (validated above)
        assert content is not None

        try:
            content = self._wrap_content_with_template(content, template)

            # Always use temp directory for compilation to handle read-only mounts
            tmpdir = tempfile.mkdtemp(prefix="mcp_latex_")
            tex_file = os.path.join(tmpdir, "document.tex")
            keep_intermediate_files = False  # Set True for debugging

            # If we had a working_dir (from input_path), symlink contents for relative includes
            if working_dir:
                for item in os.listdir(working_dir):
                    src = os.path.join(working_dir, item)
                    dst = os.path.join(tmpdir, item)
                    if not os.path.exists(dst):
                        try:
                            os.symlink(src, dst)
                        except OSError as e:
                            # Log warning instead of silently ignoring
                            warning_msg = f"Failed to symlink '{item}': {e}"
                            self.logger.warning(warning_msg)
                            symlink_warnings.append(warning_msg)
            working_dir = tmpdir

            try:
                with open(tex_file, "w", encoding="utf-8") as f:
                    f.write(content)

                output_file = self._run_latex_compilation(compiler, tex_file, working_dir, output_format)

                # Early return on compilation failure
                if output_file is None:
                    log_file = tex_file.replace(".tex", ".log")
                    return {"success": False, "error": self._extract_latex_error(log_file)}

                # Build success response
                result = self._build_compile_success_response(
                    output_file, output_format, start_time, preview_pages, preview_dpi, response_mode
                )

                # Add symlink warnings if any occurred
                if symlink_warnings:
                    result["symlink_warnings"] = symlink_warnings

                # Convert container paths to project-relative paths
                return self._convert_paths_in_result(result)

            finally:
                self._cleanup_latex_temp_files(tex_file, working_dir, keep_intermediate_files)

        except FileNotFoundError:
            return {"success": False, "error": f"{compiler} not found. Please install LaTeX."}
        except Exception as e:
            self.logger.error("LaTeX compilation error: %s", str(e))
            return {"success": False, "error": str(e)}

    async def render_tikz(
        self,
        tikz_code: str,
        output_format: str = "pdf",
        response_mode: str = "standard",
    ) -> Dict[str, Any]:
        """Render TikZ diagram as standalone image.

        Args:
            tikz_code: TikZ code for the diagram
            output_format: Output format (pdf, png, svg)
            response_mode: Level of detail in response (minimal/standard)

        Returns:
            Dictionary with rendered diagram path and metadata
        """
        # Wrap TikZ code in standalone document
        latex_content = f"""
\\documentclass[tikz,border=10pt]{{standalone}}
\\usepackage{{tikz}}
\\usetikzlibrary{{arrows.meta,positioning,shapes,calc}}
\\begin{{document}}
{tikz_code}
\\end{{document}}
        """

        # Compile to PDF first
        result = await self.compile_latex(
            content=latex_content,
            output_format="pdf",
            template="custom",
            response_mode="minimal",
        )

        if not result["success"]:
            return result

        pdf_path = result["output_path"]

        # Convert to requested format if needed
        if output_format != "pdf":
            try:
                return self._convert_pdf_to_image(pdf_path, output_format, response_mode)
            except Exception as e:
                return {"success": False, "error": f"Format conversion error: {str(e)}"}

        # Return PDF result
        if response_mode == "minimal":
            return {
                "success": True,
                "output_path": pdf_path,
            }
        return {
            "success": True,
            "output_path": pdf_path,
            "format": "pdf",
            "page_count": result.get("page_count", 1),
            "file_size_kb": result.get("file_size_kb", 0),
        }

    async def preview_pdf(
        self,
        pdf_path: str,
        pages: str = "1",
        dpi: int = PREVIEW_DPI_STANDARD,
        response_mode: str = "standard",
    ) -> Dict[str, Any]:
        """Generate PNG previews from an existing PDF file.

        Args:
            pdf_path: Path to PDF file to preview
            pages: Pages to preview ('1', '1,3,5', '1-5', 'all')
            dpi: Resolution for preview images
            response_mode: Level of detail (minimal: paths only, standard: +metadata)

        Returns:
            Dictionary with preview paths and metadata
        """
        if not os.path.exists(pdf_path):
            return {"success": False, "error": f"PDF file not found: {pdf_path}"}

        try:
            # Get page count
            page_count = self._get_pdf_page_count(pdf_path)
            if page_count == 0:
                return {"success": False, "error": "Could not determine PDF page count"}

            # Parse page specification
            pages_to_export = self._parse_page_spec(pages, page_count)
            if not pages_to_export:
                return {"success": False, "error": f"No valid pages in specification: {pages}"}

            # Export pages to PNG
            preview_paths = self._export_pages_to_png(pdf_path, pages_to_export, dpi=dpi)

            if not preview_paths:
                return {"success": False, "error": "Failed to generate previews"}

            result_data: Dict[str, Any] = {
                "success": True,
                "preview_paths": preview_paths,
            }

            # Add metadata for standard mode
            if response_mode == "standard":
                result_data["pdf_path"] = pdf_path
                result_data["page_count"] = page_count
                result_data["pages_exported"] = pages_to_export

            # Convert container paths to project-relative paths
            return self._convert_paths_in_result(result_data)

        except Exception as e:
            self.logger.error("PDF preview error: %s", str(e))
            return {"success": False, "error": str(e)}


def main():
    """Run the Content Creation MCP Server"""

    parser = argparse.ArgumentParser(description="Content Creation MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="Server mode (http or stdio)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("MCP_OUTPUT_DIR", "/app/output"),
        help="Output directory for generated content",
    )
    args = parser.parse_args()

    server = ContentCreationMCPServer(output_dir=args.output_dir)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
