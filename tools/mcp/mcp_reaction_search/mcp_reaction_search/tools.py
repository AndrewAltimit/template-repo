"""
Tool Registry for Reaction Search MCP Server

Provides a consistent interface for CI/CD and tool discovery.
"""

from typing import Any, Dict, List

from .server import ReactionSearchServer

# Tool metadata for CI/CD integration
TOOL_METADATA = {
    "name": "mcp-reaction-search",
    "description": "Semantic search for anime reaction images",
    "version": "1.0.0",
    "port": 8024,
    "transport": ["stdio", "http"],
    "tools": [
        "search_reactions",
        "get_reaction",
        "list_reaction_tags",
        "refresh_reactions",
        "reaction_search_status",
    ],
}


def get_server() -> ReactionSearchServer:
    """Get a configured server instance."""
    return ReactionSearchServer()


def get_tools() -> Dict[str, Dict[str, Any]]:
    """Get all available tools with their schemas."""
    server = get_server()
    return server.get_tools()


def list_tool_names() -> List[str]:
    """Get list of available tool names."""
    tools = TOOL_METADATA.get("tools", [])
    if isinstance(tools, list):
        return [str(t) for t in tools]
    return []


def get_metadata() -> Dict[str, Any]:
    """Get server metadata."""
    return TOOL_METADATA
