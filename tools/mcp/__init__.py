"""MCP Server Module - Modular Architecture

This package contains specialized MCP servers:
- code_quality: Code formatting and linting tools
- content_creation: Manim animations and LaTeX compilation
- gemini: AI integration (must run on host)
- gaea2: Terrain generation tools

Note: Each server should be imported directly from its module to avoid
cross-dependencies between servers with different requirements.
"""

# Do not import servers here to avoid cross-dependencies
# Each server has different dependencies that may not be available
# in all environments. Import directly from the specific module instead:
# from tools.mcp.code_quality import CodeQualityMCPServer
# from tools.mcp.content_creation import ContentCreationMCPServer
# etc.
