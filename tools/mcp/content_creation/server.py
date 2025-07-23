"""Content Creation MCP Server - Manim animations and LaTeX compilation"""

import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional  # noqa: F401

from ..core.base_server import BaseMCPServer
from ..core.utils import ensure_directory, setup_logging


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

            self.logger.info(f"Running Manim: {' '.join(cmd)}")

            # Run Manim
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

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

    async def compile_latex(self, content: str, format: str = "pdf", template: str = "article") -> Dict[str, Any]:
        """Compile LaTeX document to various formats

        Args:
            content: LaTeX document content
            format: Output format (pdf, dvi, ps)
            template: Document template to use

        Returns:
            Dictionary with compiled document path and metadata
        """
        try:
            # Add template wrapper if not custom
            if template != "custom" and not content.startswith("\\documentclass"):
                templates = {
                    "article": "\\documentclass{article}\n\\begin{document}\n{content}\n\\end{document}",
                    "report": "\\documentclass{report}\n\\begin{document}\n{content}\n\\end{document}",
                    "book": "\\documentclass{book}\n\\begin{document}\n{content}\n\\end{document}",
                    "beamer": "\\documentclass{beamer}\n\\begin{document}\n{content}\n\\end{document}",
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

                self.logger.info(f"Compiling LaTeX with: {' '.join(cmd)}")

                # Run compilation (twice for references)
                for i in range(2):
                    result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True, check=False)
                    if result.returncode != 0 and i == 0:
                        # First compilation might fail due to references
                        self.logger.warning("First compilation pass had warnings")

                # Convert DVI to PS if needed
                if format == "ps" and result.returncode == 0:
                    dvi_file = os.path.join(tmpdir, "document.dvi")
                    ps_file = os.path.join(tmpdir, "document.ps")
                    subprocess.run(["dvips", dvi_file, "-o", ps_file], check=False)

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

                    return {
                        "success": True,
                        "output_path": output_path,
                        "format": format,
                        "template": template,
                        "log_path": log_path if os.path.exists(log_file) else None,
                    }

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

    async def render_tikz(self, tikz_code: str, output_format: str = "pdf") -> Dict[str, Any]:
        """Render TikZ diagram as standalone image

        Args:
            tikz_code: TikZ code for the diagram
            output_format: Output format (pdf, png, svg)

        Returns:
            Dictionary with rendered diagram path
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
                    subprocess.run(
                        ["pdftoppm", "-png", "-singlefile", pdf_path, output_path[:-4]],
                        check=True,
                    )
                elif output_format == "svg":
                    # Use pdf2svg for SVG conversion
                    subprocess.run(["pdf2svg", pdf_path, output_path], check=True)

                if os.path.exists(output_path):
                    return {
                        "success": True,
                        "output_path": output_path,
                        "format": output_format,
                        "source_pdf": pdf_path,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Conversion to {output_format} failed",
                    }

            except Exception as e:
                return {"success": False, "error": f"Format conversion error: {str(e)}"}

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
