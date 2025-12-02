"""Content creation tools for MCP - Legacy compatibility module.

This module provides standalone functions for content creation tools.
For full functionality, use the ContentCreationMCPServer class from server.py.

The server.py implementation includes:
- input_path support for compiling from files
- response_mode for controlling response verbosity
- preview_pages for multi-page PNG export
- preview_pdf tool for previewing existing PDFs
"""

import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional, Set

# Tool registry for backwards compatibility
TOOLS = {}


def register_tool(name: str):
    """Decorator to register a tool"""

    def decorator(func):
        TOOLS[name] = func
        return func

    return decorator


def _get_pdf_page_count(pdf_path: str) -> int:
    """Extract page count from PDF using pdfinfo."""
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
    except Exception:
        pass
    return 0


def _parse_page_spec(spec: str, total_pages: int) -> List[int]:
    """Parse page specification string into list of page numbers."""
    if not spec or spec.lower() == "none":
        return []

    if spec.lower() == "all":
        return list(range(1, total_pages + 1))

    pages: Set[int] = set()

    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-")
                start_page = max(1, int(start.strip()))
                end_page = min(total_pages, int(end.strip()))
                pages.update(range(start_page, end_page + 1))
            except ValueError:
                pass
        else:
            try:
                page = int(part)
                if 1 <= page <= total_pages:
                    pages.add(page)
            except ValueError:
                pass

    return sorted(pages)


def _export_pages_to_png(
    pdf_path: str,
    pages: List[int],
    dpi: int = 150,
    output_dir: Optional[str] = None,
) -> List[str]:
    """Export specific pages from PDF to PNG files."""
    if output_dir is None:
        output_dir = os.path.dirname(pdf_path)

    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    png_paths: List[str] = []

    for page in pages:
        output_base = os.path.join(output_dir, f"{base_name}_page{page}")
        try:
            subprocess.run(
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
                capture_output=True,
                check=True,
            )
            png_path = f"{output_base}.png"
            if os.path.exists(png_path):
                png_paths.append(png_path)
        except Exception:
            pass

    return png_paths


@register_tool("create_manim_animation")
async def create_manim_animation(
    script: str,
    output_format: str = "mp4",
) -> Dict[str, Any]:
    """Create animation using Manim.

    Args:
        script: Python script for Manim animation
        output_format: Output format (mp4, gif, png, webm)

    Returns:
        Dictionary with success status and output path
    """
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            script_path = f.name

        # Build Manim command
        command = ["manim", "-pql", script_path]

        # Parse class name from script
        class_match = re.search(r"class\s+(\w+)\s*\(", script)
        if class_match:
            class_name = class_match.group(1)
            command.append(class_name)

        result = subprocess.run(command, capture_output=True, text=True, check=False)

        # Clean up
        os.unlink(script_path)

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Manim execution failed with exit code {result.returncode}: {result.stderr}",
            }

        # Find output file
        output_dir = os.path.expanduser("~/media/videos")
        output_files: List[str] = []
        if os.path.exists(output_dir):
            for root, _, files in os.walk(output_dir):
                output_files.extend(os.path.join(root, f) for f in files if f.endswith(f".{output_format}"))

        return {
            "success": True,
            "format": output_format,
            "output_path": output_files[0] if output_files else None,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool("compile_latex")
async def compile_latex(
    content: Optional[str] = None,
    input_path: Optional[str] = None,
    output_format: str = "pdf",
    output_dir: Optional[str] = None,
    response_mode: str = "minimal",
    preview_pages: str = "none",
    preview_dpi: int = 150,
) -> Dict[str, Any]:
    """Compile LaTeX document.

    Args:
        content: LaTeX document content (alternative to input_path)
        input_path: Path to .tex file to compile (alternative to content)
        output_format: Output format (pdf, dvi)
        output_dir: Directory for output files
        response_mode: Level of response detail (minimal/standard/verbose)
        preview_pages: Pages to preview ('none', '1', '1,3,5', 'all')
        preview_dpi: DPI for preview images

    Returns:
        Dictionary with success status, output path, and optional metadata
    """
    if output_dir is None:
        output_dir = os.path.expanduser("~/output/latex")

    os.makedirs(output_dir, exist_ok=True)

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
            working_dir = os.path.dirname(os.path.abspath(input_path))
        except Exception as e:
            return {"success": False, "error": f"Failed to read input file: {e}"}

    start_time = time.time()

    # At this point content is guaranteed to be str (validated above)
    assert content is not None

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            compile_dir = working_dir if working_dir else tmpdir

            # Write LaTeX file
            tex_file = os.path.join(compile_dir, "document.tex")
            with open(tex_file, "w", encoding="utf-8") as f:
                f.write(content)

            # Compile based on format
            if output_format == "pdf":
                command = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_file]
            elif output_format == "dvi":
                command = ["latex", "-interaction=nonstopmode", "-halt-on-error", tex_file]
            else:
                return {"success": False, "error": f"Unsupported format: {output_format}"}

            # Run compilation twice for references
            for _ in range(2):
                result = subprocess.run(command, cwd=compile_dir, capture_output=True, text=True, check=False)

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Compilation failed with exit code {result.returncode}",
                }

            # Check for output file
            output_file = tex_file.replace(".tex", f".{output_format}")
            if not os.path.exists(output_file):
                return {
                    "success": False,
                    "error": "Compilation succeeded but output file not found",
                }

            # Copy output file
            timestamp = int(time.time())
            dest_file = os.path.join(output_dir, f"document_{timestamp}.{output_format}")
            shutil.copy(output_file, dest_file)

            # Build response
            page_count = _get_pdf_page_count(dest_file) if output_format == "pdf" else 0
            file_size_kb = os.path.getsize(dest_file) / 1024

            result_data: Dict[str, Any] = {
                "success": True,
                "output_path": dest_file,
                "page_count": page_count,
                "file_size_kb": round(file_size_kb, 2),
            }

            # Generate previews if requested
            if output_format == "pdf" and preview_pages != "none" and page_count > 0:
                pages_to_export = _parse_page_spec(preview_pages, page_count)
                if pages_to_export:
                    preview_paths = _export_pages_to_png(dest_file, pages_to_export, dpi=preview_dpi, output_dir=output_dir)
                    if response_mode in ("standard", "verbose"):
                        result_data["preview_paths"] = preview_paths

            # Add extra metadata for standard/verbose modes
            if response_mode in ("standard", "verbose"):
                result_data["format"] = output_format
                result_data["compile_time_seconds"] = round(time.time() - start_time, 2)

            return result_data

    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool("preview_pdf")
async def preview_pdf(
    pdf_path: str,
    pages: str = "1",
    dpi: int = 150,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate PNG previews from an existing PDF file.

    Args:
        pdf_path: Path to PDF file to preview
        pages: Pages to preview ('1', '1,3,5', '1-5', 'all')
        dpi: Resolution for preview images
        output_dir: Directory for output files

    Returns:
        Dictionary with preview paths
    """
    if not os.path.exists(pdf_path):
        return {"success": False, "error": f"PDF file not found: {pdf_path}"}

    if output_dir is None:
        output_dir = os.path.dirname(pdf_path)

    try:
        page_count = _get_pdf_page_count(pdf_path)
        if page_count == 0:
            return {"success": False, "error": "Could not determine PDF page count"}

        pages_to_export = _parse_page_spec(pages, page_count)
        if not pages_to_export:
            return {"success": False, "error": f"No valid pages in specification: {pages}"}

        preview_paths = _export_pages_to_png(pdf_path, pages_to_export, dpi=dpi, output_dir=output_dir)

        if not preview_paths:
            return {"success": False, "error": "Failed to generate previews"}

        return {
            "success": True,
            "pdf_path": pdf_path,
            "page_count": page_count,
            "preview_paths": preview_paths,
            "pages_exported": pages_to_export,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
