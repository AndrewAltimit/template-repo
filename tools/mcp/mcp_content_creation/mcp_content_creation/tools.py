"""Content creation tools for MCP.

This module provides standalone functions that delegate to ContentCreationMCPServer.
All core logic is implemented in server.py to avoid code duplication.
"""

import asyncio
from typing import Any, Dict, Optional, cast

from .server import ContentCreationMCPServer


class _ServerHolder:
    """Holder class for singleton server instance to avoid global statement."""

    instance: Optional[ContentCreationMCPServer] = None


def _get_server() -> ContentCreationMCPServer:
    """Get or create the singleton server instance."""
    if _ServerHolder.instance is None:
        _ServerHolder.instance = ContentCreationMCPServer()
    return _ServerHolder.instance


# Tool registry for backwards compatibility
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
) -> Dict[str, Any]:
    """Create animation using Manim.

    Args:
        script: Python script for Manim animation
        output_format: Output format (mp4, gif, png, webm)

    Returns:
        Dictionary with success status and output path
    """
    server = _get_server()
    result = await server.create_manim_animation(script=script, output_format=output_format)
    return cast(Dict[str, Any], result)


@register_tool("compile_latex")
async def compile_latex(
    content: Optional[str] = None,
    input_path: Optional[str] = None,
    output_format: str = "pdf",
    template: str = "custom",
    response_mode: str = "minimal",
    preview_pages: str = "none",
    preview_dpi: int = 150,
) -> Dict[str, Any]:
    """Compile LaTeX document.

    Args:
        content: LaTeX document content (alternative to input_path)
        input_path: Path to .tex file to compile (alternative to content)
        output_format: Output format (pdf, dvi, ps)
        template: Document template (article, report, book, beamer, custom)
        response_mode: Level of response detail (minimal/standard/verbose)
        preview_pages: Pages to preview ('none', '1', '1,3,5', 'all')
        preview_dpi: DPI for preview images

    Returns:
        Dictionary with success status, output path, and optional metadata
    """
    server = _get_server()
    result = await server.compile_latex(
        content=content,
        input_path=input_path,
        output_format=output_format,
        template=template,
        response_mode=response_mode,
        preview_pages=preview_pages,
        preview_dpi=preview_dpi,
    )
    return cast(Dict[str, Any], result)


@register_tool("render_tikz")
async def render_tikz(
    tikz_code: str,
    output_format: str = "pdf",
    response_mode: str = "minimal",
) -> Dict[str, Any]:
    """Render TikZ diagrams as standalone images.

    Args:
        tikz_code: TikZ code for the diagram
        output_format: Output format (pdf, png, svg)
        response_mode: Response detail level (minimal/standard/verbose)

    Returns:
        Dictionary with output path
    """
    server = _get_server()
    result = await server.render_tikz(
        tikz_code=tikz_code,
        output_format=output_format,
        response_mode=response_mode,
    )
    return cast(Dict[str, Any], result)


@register_tool("preview_pdf")
async def preview_pdf(
    pdf_path: str,
    pages: str = "1",
    dpi: int = 150,
    response_mode: str = "minimal",
) -> Dict[str, Any]:
    """Generate PNG previews from an existing PDF file.

    Args:
        pdf_path: Path to PDF file to preview
        pages: Pages to preview ('1', '1,3,5', '1-5', 'all')
        dpi: Resolution for preview images
        response_mode: Response detail level (minimal/verbose)

    Returns:
        Dictionary with preview paths
    """
    server = _get_server()
    result = await server.preview_pdf(
        pdf_path=pdf_path,
        pages=pages,
        dpi=dpi,
        response_mode=response_mode,
    )
    return cast(Dict[str, Any], result)


# Convenience function for synchronous usage
def run_tool(name: str, **kwargs) -> Dict[str, Any]:
    """Run a tool synchronously.

    Args:
        name: Tool name
        **kwargs: Tool arguments

    Returns:
        Tool result dictionary
    """
    if name not in TOOLS:
        return {"success": False, "error": f"Unknown tool: {name}"}

    tool_func = TOOLS[name]
    return asyncio.run(tool_func(**kwargs))
