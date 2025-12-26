"""
MCP Reaction Search Server

Semantic search for anime reaction images using sentence-transformers.
"""

from typing import TYPE_CHECKING

__version__ = "1.0.0"
__all__ = ["ReactionSearchServer"]

# Lazy import to avoid RuntimeWarning when running as module
# The warning occurs because __init__.py imports server.py, which is then
# executed as __main__ when using `python -m mcp_reaction_search.server`
if TYPE_CHECKING:
    from .server import ReactionSearchServer


def __getattr__(name: str):
    """Lazy import for runtime access."""
    if name == "ReactionSearchServer":
        from .server import ReactionSearchServer

        return ReactionSearchServer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
