"""
Reaction Search MCP Server

Provides semantic search for anime reaction images via MCP tools.

Usage:
    # STDIO mode (for Claude Code)
    python -m mcp_reaction_search.server --mode stdio

    # HTTP mode (for remote access)
    python -m mcp_reaction_search.server --mode http --port 8024
"""

import argparse
from dataclasses import asdict
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Add parent paths for imports when running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp_core"))

from mcp_core import BaseMCPServer

from .config_loader import ConfigLoader
from .search_engine import ReactionSearchEngine

logger = logging.getLogger(__name__)


class ReactionSearchServer(BaseMCPServer):
    """
    MCP Server for semantic reaction image search.

    Provides tools to search for contextually appropriate reaction images
    using natural language queries. Uses sentence-transformers for
    embedding-based similarity search.

    Tools:
    - search_reactions: Semantic search for reactions
    - get_reaction: Get a specific reaction by ID
    - list_reaction_tags: Browse available tags
    - refresh_reactions: Refresh the reaction cache
    - reaction_search_status: Get server status
    """

    def __init__(self, port: int = 8024):
        """
        Initialize the reaction search server.

        Args:
            port: HTTP port (default: 8024)
        """
        super().__init__(
            name="reaction-search",
            version="1.0.0",
            port=port,
        )
        self._config_loader: Optional[ConfigLoader] = None
        self._search_engine: Optional[ReactionSearchEngine] = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """
        Ensure the search engine is initialized (lazy loading).

        Loads config and computes embeddings on first call.
        """
        if self._initialized:
            return

        logger.info("Initializing reaction search engine...")

        # Get model from environment or use default
        model_name = os.getenv("REACTION_SEARCH_MODEL", "sentence-transformers/all-MiniLM-L12-v2")

        # Initialize components
        self._config_loader = ConfigLoader()
        self._search_engine = ReactionSearchEngine(model_name=model_name)

        # Load reactions and initialize engine
        reactions = self._config_loader.get_reactions()
        self._search_engine.initialize(reactions)

        self._initialized = True
        logger.info("Reaction search engine initialized with %d reactions", self._search_engine.reaction_count)

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available MCP tools."""
        return {
            "search_reactions": {
                "description": """Search for reaction images using natural language.

Returns contextually appropriate anime reaction images based on semantic similarity.
Useful for finding reactions that match an emotional state or situation.

Examples:
- "celebrating after fixing a bug" -> felix, aqua_happy
- "confused about the error message" -> confused, miku_confused
- "annoyed at the failing tests" -> kagami_annoyed, nao_annoyed
- "deep in thought while debugging" -> thinking_foxgirl, hifumi_studious""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query describing the desired reaction",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 5, max: 20)",
                            "default": 5,
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tag filter - reactions must have at least one of these tags",
                        },
                        "min_similarity": {
                            "type": "number",
                            "description": "Minimum similarity threshold 0-1 (default: 0.0)",
                            "default": 0.0,
                        },
                    },
                    "required": ["query"],
                },
            },
            "get_reaction": {
                "description": """Get a specific reaction image by ID.

Returns the full details for a reaction including URL and markdown for embedding.""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reaction_id": {
                            "type": "string",
                            "description": "Reaction identifier (e.g., 'felix', 'miku_typing')",
                        },
                    },
                    "required": ["reaction_id"],
                },
            },
            "list_reaction_tags": {
                "description": """List all available reaction tags with counts.

Useful for browsing available categories and filtering searches.""",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "refresh_reactions": {
                "description": """Refresh the reaction cache from GitHub.

Forces a fetch of the latest config, bypassing the 1-week cache TTL.""",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "reaction_search_status": {
                "description": """Get reaction search server status.

Returns information about initialization state, cache status, and model.""",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }

    async def search_reactions(
        self,
        query: str,
        limit: int = 5,
        tags: Optional[List[str]] = None,
        min_similarity: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Search for reactions matching a natural language query.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            tags: Optional tag filter
            min_similarity: Minimum similarity threshold

        Returns:
            Dict with search results
        """
        self._ensure_initialized()
        assert self._search_engine is not None  # Guaranteed by _ensure_initialized

        # Clamp limit
        limit = min(max(1, limit), 20)

        try:
            results = self._search_engine.search(
                query=query,
                limit=limit,
                tags=tags,
                min_similarity=min_similarity,
            )

            return {
                "success": True,
                "query": query,
                "count": len(results),
                "results": [asdict(r) for r in results],
            }
        except Exception as e:
            logger.error("Search failed: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    async def get_reaction(self, reaction_id: str) -> Dict[str, Any]:
        """
        Get a specific reaction by ID.

        Args:
            reaction_id: Reaction identifier

        Returns:
            Dict with reaction details or error
        """
        self._ensure_initialized()
        assert self._search_engine is not None  # Guaranteed by _ensure_initialized

        try:
            result = self._search_engine.get_by_id(reaction_id)
            if result is None:
                return {
                    "success": False,
                    "error": f"Reaction not found: {reaction_id}",
                }

            return {
                "success": True,
                "reaction": asdict(result),
            }
        except Exception as e:
            logger.error("Get reaction failed: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    async def list_reaction_tags(self) -> Dict[str, Any]:
        """
        List all available tags with counts.

        Returns:
            Dict with tag information
        """
        self._ensure_initialized()
        assert self._search_engine is not None  # Guaranteed by _ensure_initialized

        try:
            tags = self._search_engine.list_tags()

            # Group tags by category (heuristic)
            emotions = [
                "happy",
                "sad",
                "angry",
                "confused",
                "excited",
                "annoyed",
                "smug",
                "shocked",
                "nervous",
                "bored",
                "content",
            ]
            actions = [
                "typing",
                "thinking",
                "working",
                "gaming",
                "drinking",
                "waving",
                "cheering",
                "crying",
                "laughing",
                "studying",
            ]

            categorized = {
                "emotions": {t: c for t, c in tags.items() if t in emotions},
                "actions": {t: c for t, c in tags.items() if t in actions},
                "other": {t: c for t, c in tags.items() if t not in emotions and t not in actions},
            }

            return {
                "success": True,
                "total_tags": len(tags),
                "tags": tags,
                "categorized": categorized,
            }
        except Exception as e:
            logger.error("List tags failed: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    async def refresh_reactions(self) -> Dict[str, Any]:
        """
        Refresh the reaction cache from GitHub.

        Returns:
            Dict with refresh status
        """
        try:
            # Clear cache and reload
            if self._config_loader:
                self._config_loader.clear_cache()

            # Re-initialize
            self._initialized = False
            self._ensure_initialized()

            assert self._search_engine is not None  # Guaranteed by _ensure_initialized
            return {
                "success": True,
                "message": "Reactions refreshed from GitHub",
                "reaction_count": self._search_engine.reaction_count,
            }
        except Exception as e:
            logger.error("Refresh failed: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    async def reaction_search_status(self) -> Dict[str, Any]:
        """
        Get server status information.

        Returns:
            Dict with status information
        """
        status = {
            "server": "reaction-search",
            "version": "1.0.0",
            "initialized": self._initialized,
        }

        if self._initialized and self._search_engine is not None and self._config_loader is not None:
            status["engine"] = self._search_engine.get_status()
            status["cache"] = self._config_loader.get_cache_info()
        else:
            status["note"] = "Engine will initialize on first search"

        return status


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Reaction Search MCP Server")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Server mode (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8024,
        help="HTTP port (default: 8024)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and run server
    server = ReactionSearchServer(port=args.port)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
