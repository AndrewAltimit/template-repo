"""Content Creation MCP Server - Manim animations and LaTeX compilation"""

import base64
import io
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional  # noqa: F401

from ..core.base_server import BaseMCPServer
from ..core.utils import ensure_directory, setup_logging

# Constants for image processing
JPEG_QUALITY_HIGH = 85
JPEG_QUALITY_LOW = 70
MAX_IMAGE_SIZE_JPEG = 100000  # 100KB limit for JPEG
MAX_IMAGE_SIZE_PNG = 200000  # 200KB limit for PNG
PREVIEW_DPI = 72  # Lower resolution for previews
FIRST_PAGE = "1"  # PDF page numbers
LAST_PAGE = "1"


class ContentCreationMCPServer(BaseMCPServer):
    """MCP Server for content creation - Manim animations and LaTeX documents"""

    def __init__(self, output_dir: str = "/app/output"):
        super().__init__(
            name="Content Creation MCP Server",
            version="1.0.0",
            port=8011,  # New port for content creation server
        )
        self.logger = setup_logging("ContentCreationMCP")

        # Use environment variable if set
        self.output_dir = os.environ.get("MCP_OUTPUT_DIR", output_dir)
        self.logger.info(f"Using output directory: {self.output_dir}")

        try:
            # Create output directories with error handling
            self.manim_output_dir = ensure_directory(os.path.join(self.output_dir, "manim"))
            self.latex_output_dir = ensure_directory(os.path.join(self.output_dir, "latex"))
            self.logger.info("Successfully created output directories")
        except Exception as e:
            self.logger.error(f"Failed to create output directories: {e}")
            # Use temp directory as fallback
            import tempfile

            temp_dir = tempfile.mkdtemp(prefix="mcp_content_")
            self.output_dir = temp_dir
            self.manim_output_dir = ensure_directory(os.path.join(temp_dir, "manim"))
            self.latex_output_dir = ensure_directory(os.path.join(temp_dir, "latex"))
            self.logger.warning(f"Using fallback temp directory: {temp_dir}")

    def _process_image_for_feedback(self, image_path: str) -> Dict[str, Any]:
        """Process image for visual feedback with compression and format conversion

        Args:
            image_path: Path to the image file (PNG)

        Returns:
            Dictionary with visual feedback data or error information
        """
        try:
            from PIL import Image
        except ImportError:
            self.logger.warning("Pillow (PIL) is not installed. Visual feedback unavailable.")
            return {"error": "Pillow (PIL) is not installed, visual feedback unavailable."}

        try:
            with Image.open(image_path) as img:
                # Convert RGBA to RGB if necessary for JPEG
                if img.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "RGBA":
                        background.paste(img, mask=img.split()[3])
                    else:
                        background.paste(img, mask=img.split()[1])
                    img = background

                # Save as JPEG with compression for smaller size
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=JPEG_QUALITY_HIGH, optimize=True)
                img_data = buffer.getvalue()

                # If still too large, try more compression
                if len(img_data) > MAX_IMAGE_SIZE_JPEG:
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=JPEG_QUALITY_LOW, optimize=True)
                    img_data = buffer.getvalue()

                img_base64 = base64.b64encode(img_data).decode("utf-8")
                return {
                    "format": "jpeg",
                    "encoding": "base64",
                    "data": img_base64,
                    "size_kb": len(img_data) / 1024,
                }

        except Exception as e:
            self.logger.warning(f"Failed to process image for visual feedback: {e}")
            return {"error": str(e)}

    def _run_subprocess_with_logging(
        self, cmd: list, cwd: Optional[str] = None, check: bool = False
    ) -> subprocess.CompletedProcess:
        """Run subprocess command with proper logging and error handling

        Args:
            cmd: Command to run as list
            cwd: Working directory for command
            check: Whether to raise exception on non-zero return code

        Returns:
            CompletedProcess result
        """
        self.logger.info(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
            if result.returncode != 0:
                self.logger.warning(f"Command failed with return code {result.returncode}: {result.stderr}")
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {e}")
            raise
        except FileNotFoundError:
            self.logger.error(f"Command not found: {' '.join(cmd)}")
            raise

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
                        "quality": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "fourk"],
                            "default": "medium",
                            "description": "Rendering quality",
                        },
                        "preview": {
                            "type": "boolean",
                            "default": False,
                            "description": "Generate preview frame instead of full animation",
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
                            "description": "LaTeX document content",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["pdf", "dvi", "ps"],
                            "default": "pdf",
                            "description": "Output format",
                        },
                        "template": {
                            "type": "string",
                            "enum": ["article", "report", "book", "beamer", "custom"],
                            "default": "article",
                            "description": "Document template to use",
                        },
                        "visual_feedback": {
                            "type": "boolean",
                            "default": True,
                            "description": "Return PNG preview image for visual verification",
                        },
                    },
                    "required": ["content"],
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
                    },
                    "required": ["tikz_code"],
                },
            },
        }

    async def create_manim_animation(
        self,
        script: str,
        output_format: str = "mp4",
        quality: str = "medium",
        preview: bool = False,
    ) -> Dict[str, Any]:
        """Create Manim animation from Python script

        Args:
            script: Python script containing Manim scene
            output_format: Output format (mp4, gif, png, webm)
            quality: Rendering quality (low, medium, high, fourk)
            preview: Generate preview frame only

        Returns:
            Dictionary with animation file path and metadata
        """
        try:
            # Create temporary file for script
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(script)
                script_path = f.name

            # Build Manim command
            quality_flags = {
                "low": "-ql",
                "medium": "-qm",
                "high": "-qh",
                "fourk": "-qk",
            }

            cmd = [
                "manim",
                "render",
                "--media_dir",
                self.manim_output_dir,
                quality_flags.get(quality, "-qm"),
                "--format",
                output_format,
            ]

            if preview:
                cmd.append("-s")  # Save last frame

            cmd.append(script_path)

            # Run Manim
            result = self._run_subprocess_with_logging(cmd)

            # Clean up script file
            os.unlink(script_path)

            if result.returncode == 0:
                # Find output file - check both media and videos directories
                for search_dir in ["media", "videos", ""]:
                    search_path = os.path.join(self.manim_output_dir, search_dir) if search_dir else self.manim_output_dir
                    if os.path.exists(search_path):
                        # Search for output file
                        for root, dirs, files in os.walk(search_path):
                            for file in files:
                                if file.endswith(f".{output_format}") and "partial_movie_files" not in root:
                                    output_path = os.path.join(root, file)
                                    # Copy to a stable location
                                    final_path = os.path.join(
                                        self.manim_output_dir,
                                        f"animation_{os.getpid()}.{output_format}",
                                    )
                                    shutil.copy(output_path, final_path)

                                    return {
                                        "success": True,
                                        "output_path": final_path,
                                        "format": output_format,
                                        "quality": quality,
                                        "preview": preview,
                                    }

                return {
                    "success": False,
                    "error": "Output file not found after rendering",
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or "Animation creation failed",
                    "stdout": result.stdout,
                }

        except FileNotFoundError:
            return {
                "success": False,
                "error": "Manim not found. Please install it first.",
            }
        except Exception as e:
            self.logger.error(f"Manim error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def compile_latex(
        self,
        content: str,
        format: str = "pdf",
        template: str = "article",
        visual_feedback: bool = True,
    ) -> Dict[str, Any]:
        """Compile LaTeX document to various formats

        Args:
            content: LaTeX document content
            format: Output format (pdf, dvi, ps)
            template: Document template to use
            visual_feedback: Whether to return PNG preview image

        Returns:
            Dictionary with compiled document path and metadata
        """
        try:
            # Add template wrapper if not custom
            if template != "custom" and not content.startswith("\\documentclass"):
                templates = {
                    "article": "\\documentclass{{article}}\n\\begin{{document}}\n{content}\n\\end{{document}}",
                    "report": "\\documentclass{{report}}\n\\begin{{document}}\n{content}\n\\end{{document}}",
                    "book": "\\documentclass{{book}}\n\\begin{{document}}\n{content}\n\\end{{document}}",
                    "beamer": "\\documentclass{{beamer}}\n\\begin{{document}}\n{content}\n\\end{{document}}",
                }
                if template in templates:
                    content = templates[template].format(content=content)

            # Create temporary directory
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write LaTeX file
                tex_file = os.path.join(tmpdir, "document.tex")
                with open(tex_file, "w") as f:
                    f.write(content)

                # Choose compiler based on format
                if format == "pdf":
                    compiler = "pdflatex"
                else:
                    compiler = "latex"

                cmd = [compiler, "-interaction=nonstopmode", tex_file]

                # Run compilation (twice for references)
                for i in range(2):
                    result = self._run_subprocess_with_logging(cmd, cwd=tmpdir)
                    if result.returncode != 0 and i == 0:
                        # First compilation might fail due to references
                        self.logger.warning("First compilation pass had warnings")

                # Convert DVI to PS if needed
                if format == "ps" and result.returncode == 0:
                    dvi_file = os.path.join(tmpdir, "document.dvi")
                    ps_file = os.path.join(tmpdir, "document.ps")
                    self._run_subprocess_with_logging(["dvips", dvi_file, "-o", ps_file])

                # Check for output
                output_file = os.path.join(tmpdir, f"document.{format}")
                if os.path.exists(output_file):
                    # Copy to output directory
                    output_path = os.path.join(self.latex_output_dir, f"document_{os.getpid()}.{format}")
                    shutil.copy(output_file, output_path)

                    # Also copy log file for debugging
                    log_file = os.path.join(tmpdir, "document.log")
                    if os.path.exists(log_file):
                        log_path = output_path.replace(f".{format}", ".log")
                        shutil.copy(log_file, log_path)

                    result_data = {
                        "success": True,
                        "output_path": output_path,
                        "format": format,
                        "template": template,
                        "log_path": log_path if os.path.exists(log_file) else None,
                    }

                    # Generate visual feedback if requested and format is PDF
                    if visual_feedback and format == "pdf":
                        try:
                            # Convert first page of PDF to PNG with lower resolution
                            png_path = output_path.replace(".pdf", "_preview.png")
                            self._run_subprocess_with_logging(
                                [
                                    "pdftoppm",
                                    "-png",
                                    "-f",
                                    FIRST_PAGE,
                                    "-l",
                                    LAST_PAGE,
                                    "-r",
                                    str(PREVIEW_DPI),
                                    "-singlefile",
                                    output_path,
                                    png_path[:-4],  # Remove .png extension
                                ],
                                check=True,
                            )

                            # Process the PNG image for visual feedback
                            if os.path.exists(png_path):
                                feedback_result = self._process_image_for_feedback(png_path)
                                if "error" in feedback_result:
                                    result_data["visual_feedback_error"] = feedback_result["error"]
                                else:
                                    result_data["visual_feedback"] = feedback_result
                        except Exception as e:
                            self.logger.warning(f"Failed to generate visual feedback: {e}")
                            result_data["visual_feedback_error"] = str(e)

                    return result_data

                # Extract error from log file
                log_file = os.path.join(tmpdir, "document.log")
                error_msg = "Compilation failed"
                if os.path.exists(log_file):
                    with open(log_file, "r") as f:
                        log_content = f.read()
                        # Look for error messages
                        if "! " in log_content:
                            error_lines = [line for line in log_content.split("\n") if line.startswith("!")]
                            if error_lines:
                                error_msg = "\n".join(error_lines[:5])

                return {"success": False, "error": error_msg}

        except FileNotFoundError:
            return {
                "success": False,
                "error": f"{compiler} not found. Please install LaTeX.",
            }
        except Exception as e:
            self.logger.error(f"LaTeX compilation error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def render_tikz(self, tikz_code: str, output_format: str = "pdf", visual_feedback: bool = True) -> Dict[str, Any]:
        """Render TikZ diagram as standalone image

        Args:
            tikz_code: TikZ code for the diagram
            output_format: Output format (pdf, png, svg)
            visual_feedback: Whether to return image data for visual verification

        Returns:
            Dictionary with rendered diagram path and optional visual data
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

        # First compile to PDF
        result = await self.compile_latex(latex_content, format="pdf", template="custom")

        if not result["success"]:
            return result

        pdf_path = result["output_path"]

        # Convert to requested format if needed
        if output_format != "pdf":
            try:
                base_name = os.path.splitext(os.path.basename(pdf_path))[0]
                output_path = os.path.join(self.latex_output_dir, f"{base_name}.{output_format}")

                if output_format == "png":
                    # Use pdftoppm for PNG conversion
                    self._run_subprocess_with_logging(
                        ["pdftoppm", "-png", "-singlefile", pdf_path, output_path[:-4]],
                        check=True,
                    )
                elif output_format == "svg":
                    # Use pdf2svg for SVG conversion
                    self._run_subprocess_with_logging(["pdf2svg", pdf_path, output_path], check=True)

                if os.path.exists(output_path):
                    result_data = {
                        "success": True,
                        "output_path": output_path,
                        "format": output_format,
                        "source_pdf": pdf_path,
                    }

                    # Add visual feedback for PNG format
                    if visual_feedback and output_format == "png":
                        feedback_result = self._process_image_for_feedback(output_path)
                        if "error" in feedback_result:
                            result_data["visual_feedback_error"] = feedback_result["error"]
                        else:
                            result_data["visual_feedback"] = feedback_result

                    # Add visual feedback for SVG format (as text)
                    elif visual_feedback and output_format == "svg":
                        try:
                            with open(output_path, "r") as svg_file:
                                svg_content = svg_file.read()
                                result_data["visual_feedback"] = {
                                    "format": "svg",
                                    "encoding": "text",
                                    "data": svg_content,
                                }
                        except Exception as e:
                            self.logger.warning(f"Failed to read SVG for visual feedback: {e}")
                            result_data["visual_feedback_error"] = str(e)

                    return result_data
                else:
                    return {
                        "success": False,
                        "error": f"Conversion to {output_format} failed",
                    }

            except Exception as e:
                return {"success": False, "error": f"Format conversion error: {str(e)}"}

        # For PDF format, add visual feedback if requested
        if visual_feedback and output_format == "pdf":
            try:
                # Convert first page of PDF to PNG for preview with lower resolution
                png_path = pdf_path.replace(".pdf", "_preview.png")
                self._run_subprocess_with_logging(
                    [
                        "pdftoppm",
                        "-png",
                        "-f",
                        FIRST_PAGE,
                        "-l",
                        LAST_PAGE,
                        "-r",
                        str(PREVIEW_DPI),
                        "-singlefile",
                        pdf_path,
                        png_path[:-4],
                    ],
                    check=True,
                )

                if os.path.exists(png_path):
                    feedback_result = self._process_image_for_feedback(png_path)
                    if "error" in feedback_result:
                        result["visual_feedback_error"] = feedback_result["error"]
                    else:
                        result["visual_feedback"] = feedback_result
            except Exception as e:
                self.logger.warning(f"Failed to generate visual feedback for PDF: {e}")
                result["visual_feedback_error"] = str(e)

        return result


def main():
    """Run the Content Creation MCP Server"""
    import argparse

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
