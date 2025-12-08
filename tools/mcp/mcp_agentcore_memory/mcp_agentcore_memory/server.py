"""
AgentCore Memory MCP Server

Multi-provider memory system for AI agents.
Supports AWS AgentCore and ChromaDB backends.

Usage:
    # STDIO mode (for Claude Code)
    python -m mcp_agentcore_memory.server --mode stdio

    # HTTP mode (for remote access)
    python -m mcp_agentcore_memory.server --mode http --port 8023
"""

import argparse
from datetime import datetime, timezone
import logging
import os
import sys
from typing import Any, Dict, Optional

# Add parent paths for imports when running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "mcp_core"))

from mcp_core import BaseMCPServer

from .cache import get_cache
from .namespaces import MemoryNamespace
from .providers.factory import get_provider, get_provider_type
from .providers.interface import MemoryProvider

logger = logging.getLogger(__name__)


class AgentCoreMemoryServer(BaseMCPServer):
    """
    MCP Server for AI agent memory.

    Supports multiple backends via MEMORY_PROVIDER env var:
    - agentcore: AWS Bedrock AgentCore (rate limited, managed)
    - chromadb: Self-hosted ChromaDB (no limits, free)

    Tools:
    - store_event: Store short-term memory (rate-limited for AgentCore)
    - store_facts: Store long-term facts (no rate limit)
    - search_memories: Semantic search across memories
    - list_session_events: List events from a session
    - memory_status: Get provider status and info
    """

    def __init__(self, port: int = 8023):
        """
        Initialize the memory server.

        Args:
            port: HTTP port (default: 8023)
        """
        super().__init__(
            name="agentcore-memory",
            version="0.1.0",
            port=port,
        )
        self._provider: Optional[MemoryProvider] = None
        self._cache = get_cache()

    async def _get_provider(self) -> MemoryProvider:
        """Get or create the memory provider."""
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available MCP tools."""
        return {
            "store_event": {
                "description": """Store a short-term memory event.

IMPORTANT for AWS AgentCore: Rate limited to 0.25 req/sec per session!
Only use for sparse, high-value events:
- Session start goals
- Key decisions made
- Final outcomes

For ChromaDB: No rate limits.""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Content to remember",
                        },
                        "actor_id": {
                            "type": "string",
                            "description": "Actor identifier (e.g., 'claude-code', 'issue-monitor')",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session identifier (max 100 chars for AgentCore)",
                        },
                    },
                    "required": ["content", "actor_id", "session_id"],
                },
            },
            "store_facts": {
                "description": """Store facts/patterns for long-term retention.

This bypasses short-term event rate limits (uses BatchCreateMemoryRecords).
Use for:
- Discovered patterns
- Architectural decisions
- Learned conventions""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "facts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of facts to store",
                        },
                        "namespace": {
                            "type": "string",
                            "description": f"Namespace for organization (e.g., '{MemoryNamespace.PATTERNS}')",
                        },
                        "source": {
                            "type": "string",
                            "description": "Source attribution (e.g., 'PR #42', 'claude-code')",
                        },
                    },
                    "required": ["facts", "namespace"],
                },
            },
            "search_memories": {
                "description": """Search memories using semantic query.

Returns relevant memories ranked by similarity.""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "namespace": {
                            "type": "string",
                            "description": f"Namespace to search (e.g., '{MemoryNamespace.PATTERNS}')",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum results to return (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query", "namespace"],
                },
            },
            "list_session_events": {
                "description": "List events from a specific session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "actor_id": {
                            "type": "string",
                            "description": "Actor identifier",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session identifier",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum events to return (default: 50)",
                            "default": 50,
                        },
                    },
                    "required": ["actor_id", "session_id"],
                },
            },
            "list_namespaces": {
                "description": "List available predefined namespaces.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "memory_status": {
                "description": "Get memory provider status and info.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }

    async def store_event(
        self,
        content: str,
        actor_id: str,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Store a short-term memory event.

        Args:
            content: Content to remember
            actor_id: Actor identifier
            session_id: Session identifier

        Returns:
            Result with event_id and provider info
        """
        provider = await self._get_provider()

        try:
            event = await provider.store_event(
                actor_id=actor_id,
                session_id=session_id,
                content=content,
            )

            info = await provider.get_info()
            result = {
                "success": True,
                "event_id": event.id,
                "provider": info.get("provider"),
                "timestamp": event.timestamp.isoformat(),
            }

            # Add rate limit warning for AgentCore
            if info.get("rate_limit"):
                result["note"] = f"Rate limited: {info['rate_limit']}"

            return result

        except Exception as e:
            logger.error("Failed to store event: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    async def store_facts(
        self,
        facts: list,
        namespace: str,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Store facts for long-term retention.

        Args:
            facts: List of fact strings
            namespace: Target namespace
            source: Optional source attribution

        Returns:
            Result with created/failed counts
        """
        provider = await self._get_provider()

        # Build records with metadata
        records = [
            {
                "content": fact,
                "metadata": {
                    "source": source,
                    "stored_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            for fact in facts
        ]

        try:
            result = await provider.store_records(records, namespace)

            # Invalidate cache for this namespace
            self._cache.invalidate(namespace)

            return {
                "success": result.failed == 0,
                "created": result.created,
                "failed": result.failed,
                "namespace": namespace,
                "errors": result.errors if result.failed > 0 else None,
            }

        except Exception as e:
            logger.error("Failed to store facts: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    async def search_memories(
        self,
        query: str,
        namespace: str,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Search memories using semantic query.

        Args:
            query: Search query
            namespace: Namespace to search
            top_k: Maximum results

        Returns:
            Search results with memories
        """
        # Check cache first
        cached = self._cache.get(query, namespace)
        if cached is not None:
            return {
                "query": query,
                "namespace": namespace,
                "count": len(cached),
                "cached": True,
                "memories": cached,
            }

        provider = await self._get_provider()

        try:
            records = await provider.search_records(query, namespace, top_k)

            memories = [
                {
                    "content": r.content,
                    "relevance": r.relevance,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ]

            # Cache the results
            self._cache.set(query, namespace, memories)

            return {
                "query": query,
                "namespace": namespace,
                "count": len(memories),
                "cached": False,
                "memories": memories,
            }

        except Exception as e:
            logger.error("Failed to search memories: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    async def list_session_events(
        self,
        actor_id: str,
        session_id: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        List events from a session.

        Args:
            actor_id: Actor identifier
            session_id: Session identifier
            limit: Maximum events

        Returns:
            List of events
        """
        provider = await self._get_provider()

        try:
            events = await provider.list_events(actor_id, session_id, limit)

            return {
                "actor_id": actor_id,
                "session_id": session_id,
                "count": len(events),
                "events": [
                    {
                        "id": e.id,
                        "content": e.content,
                        "timestamp": e.timestamp.isoformat(),
                    }
                    for e in events
                ],
            }

        except Exception as e:
            logger.error("Failed to list events: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    async def list_namespaces(self) -> Dict[str, Any]:
        """
        List available predefined namespaces.

        Returns:
            Dict with namespace categories and values
        """
        return {
            "namespaces": {
                "codebase": {
                    "architecture": MemoryNamespace.ARCHITECTURE,
                    "patterns": MemoryNamespace.PATTERNS,
                    "conventions": MemoryNamespace.CONVENTIONS,
                    "dependencies": MemoryNamespace.DEPENDENCIES,
                },
                "reviews": {
                    "pr": MemoryNamespace.PR_REVIEWS,
                    "issues": MemoryNamespace.ISSUE_CONTEXT,
                },
                "preferences": {
                    "user": MemoryNamespace.USER_PREFS,
                    "project": MemoryNamespace.PROJECT_PREFS,
                },
                "agents": {
                    "claude": MemoryNamespace.CLAUDE_LEARNINGS,
                    "gemini": MemoryNamespace.GEMINI_LEARNINGS,
                    "opencode": MemoryNamespace.OPENCODE_LEARNINGS,
                    "crush": MemoryNamespace.CRUSH_LEARNINGS,
                    "codex": MemoryNamespace.CODEX_LEARNINGS,
                },
            },
            "note": "Use hierarchical namespaces with '/' separator for organization",
        }

    async def memory_status(self) -> Dict[str, Any]:
        """
        Get memory provider status and info.

        Returns:
            Provider status and capabilities
        """
        try:
            provider = await self._get_provider()
            healthy = await provider.health_check()
            info = await provider.get_info()
            cache_stats = self._cache.get_stats()

            return {
                "status": "connected" if healthy else "disconnected",
                "provider": info,
                "cache": cache_stats,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "configured_provider": get_provider_type().value,
            }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AgentCore Memory MCP Server")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Server mode (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8023,
        help="HTTP port (default: 8023)",
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
    server = AgentCoreMemoryServer(port=args.port)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
