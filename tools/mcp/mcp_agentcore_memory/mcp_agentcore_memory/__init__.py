"""
MCP AgentCore Memory Server

Multi-provider memory system for AI agents supporting:
- AWS Bedrock AgentCore (managed, rate-limited)
- ChromaDB (self-hosted, no limits)
- PostgreSQL + pgvector (self-hosted, SQL-powered)
"""

__version__ = "0.1.0"

from .namespaces import MemoryNamespace

__all__ = [
    "__version__",
    "MemoryNamespace",
]
