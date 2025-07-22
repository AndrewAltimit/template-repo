"""Content creation tools for MCP"""

import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

# Tool registry
TOOLS = {}


def register_tool(name: str):
    """Decorator to register a tool"""

    def decorator(func):
        TOOLS[name] = func
        return func

    return decorator


@register_tool("create_manim_animation")
async def create_manim_animation(
    script: str,
    output_format: str = "mp4",
    quality: str = "medium",
    preview: bool = False,
) -> Dict[str, Any]:
    """Create animation using Manim"""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            script_path = f.name

        # Build Manim command
        command = ["manim", "-pql", script_path]

        # Parse class name from script
        import re

        class_match = re.search(r"class\s+(\w+)\s*\(", script)
        if class_match:
            class_name = class_match.group(1)
            command.append(class_name)

        result = subprocess.run(command, capture_output=True, text=True)

        # Clean up
        os.unlink(script_path)

        if result.returncode == 0:
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
                "output": result.stdout,
            }
        else:
            return {
                "success": False,
                "error": result.stderr,
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_tool("compile_latex")
async def compile_latex(
    content: str,
    format: str = "pdf",
    template: str = "article",
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Compile LaTeX document"""
    if output_dir is None:
        output_dir = os.path.expanduser("~/output/latex")

    os.makedirs(output_dir, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write LaTeX file
            tex_file = os.path.join(tmpdir, "document.tex")
            with open(tex_file, "w") as f:
                f.write(content)

            # Compile based on format
            if format == "pdf":
                command = ["pdflatex", "-interaction=nonstopmode", tex_file]
            elif format == "dvi":
                command = ["latex", "-interaction=nonstopmode", tex_file]
            else:
                return {"success": False, "error": f"Unsupported format: {format}"}

            # Run compilation
            result = subprocess.run(command, cwd=tmpdir, capture_output=True, text=True)

            if result.returncode == 0:
                # Copy output file
                output_file = os.path.join(tmpdir, f"document.{format}")
                if os.path.exists(output_file):
                    dest_file = os.path.join(output_dir, f"document.{format}")
                    shutil.copy(output_file, dest_file)

                    return {
                        "success": True,
                        "format": format,
                        "output_path": dest_file,
                        "output": result.stdout,
                    }

            return {
                "success": False,
                "error": result.stderr,
            }
    except Exception as e:
        return {"success": False, "error": str(e)}
