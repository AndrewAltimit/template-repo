"""MCP Server Module - Modular Architecture

This package contains specialized MCP servers:
- code_quality: Code formatting and linting tools
- content_creation: Manim animations and LaTeX compilation
- gemini: AI integration (must run on host)
- gaea2: Terrain generation tools
"""

# Import the individual servers for convenience
from .code_quality import CodeQualityMCPServer
from .content_creation import ContentCreationMCPServer
from .gaea2 import Gaea2MCPServer
from .gemini import GeminiMCPServer

__all__ = [
    "CodeQualityMCPServer",
    "ContentCreationMCPServer",
    "GeminiMCPServer",
    "Gaea2MCPServer",
]
