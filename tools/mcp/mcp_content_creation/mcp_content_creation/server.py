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

    def _cleanup_latex_temp_files(self, tex_file: str, working_dir: str, cleanup_tex: bool) -> None:
        """Clean up temporary LaTeX files after compilation."""
        if cleanup_tex:
            base = tex_file[:-4]
            for ext in [".tex", ".aux", ".log", ".out", ".toc", ".dvi", ".ps"]:
                try:
                    temp_file = base + ext
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception:
                    pass
        else:
            try:
                shutil.rmtree(working_dir)
            except Exception:
                pass

    def _convert_pdf_to_image(self, pdf_path: str, output_format: str, response_mode: str) -> Dict[str, Any]:
        """Convert PDF to PNG or SVG format.

        Args:
            pdf_path: Path to source PDF
            output_format: Target format ('png' or 'svg')
            response_mode: Response verbosity level (minimal/standard)

        Returns:
            Result dictionary with success status and output path
        """
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_path = os.path.join(self.latex_output_dir, f"{base_name}.{output_format}")

        if output_format == "png":
            self._run_subprocess_with_logging(
                ["pdftoppm", "-png", "-singlefile", "-r", str(PREVIEW_DPI_HIGH), pdf_path, output_path[:-4]],
                check=True,
            )
        elif output_format == "svg":
            self._run_subprocess_with_logging(["pdf2svg", pdf_path, output_path], check=True)

        if not os.path.exists(output_path):
            return {"success": False, "error": f"Conversion to {output_format} failed"}

        result_data: Dict[str, Any] = {
            "success": True,
            "output_path": output_path,
        }

        if response_mode == "standard":
            result_data["format"] = output_format

        return result_data

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

            return {
                "success": True,
                "format": output_format,
                "output_path": output_files[0] if output_files else None,
            }

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
        if input_path is not None:
            if not os.path.exists(input_path):
                return {"success": False, "error": f"Input file not found: {input_path}"}
            try:
                with open(input_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Use the directory containing the .tex file as working directory
                # This allows relative paths for \include, \input, images, etc.
                working_dir = os.path.dirname(os.path.abspath(input_path))
            except Exception as e:
                return {"success": False, "error": f"Failed to read input file: {e}"}

        compiler = "pdflatex" if output_format == "pdf" else "latex"

        # At this point content is guaranteed to be str (validated above)
        assert content is not None

        try:
            content = self._wrap_content_with_template(content, template)

            # Use working_dir if provided (for input_path), otherwise use temp directory
            if working_dir:
                # Compile in place - create temp .tex file in the working directory
                tex_file = os.path.join(working_dir, f"_mcp_compile_{os.getpid()}.tex")
                cleanup_tex = True
            else:
                # Create temp directory for content-based compilation
                tmpdir = tempfile.mkdtemp(prefix="mcp_latex_")
                working_dir = tmpdir
                tex_file = os.path.join(tmpdir, "document.tex")
                cleanup_tex = False

            try:
                with open(tex_file, "w", encoding="utf-8") as f:
                    f.write(content)

                output_file = self._run_latex_compilation(compiler, tex_file, working_dir, output_format)

                # Early return on compilation failure
                if output_file is None:
                    log_file = tex_file.replace(".tex", ".log")
                    return {"success": False, "error": self._extract_latex_error(log_file)}

                # Build and return success response
                return self._build_compile_success_response(
                    output_file, output_format, start_time, preview_pages, preview_dpi, response_mode
                )

            finally:
                self._cleanup_latex_temp_files(tex_file, working_dir, cleanup_tex)

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
        else:
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

            return result_data

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
