"""
Memory Providers

Swappable backends for the memory system:
- AgentCoreProvider: AWS Bedrock AgentCore (managed)
- ChromaDBProvider: Self-hosted ChromaDB
- PostgresProvider: Self-hosted PostgreSQL + pgvector
"""

from .interface import (
    BatchResult,
    MemoryEvent,
    MemoryProvider,
    MemoryRecord,
    ProviderType,
)

__all__ = [
    "MemoryProvider",
    "ProviderType",
    "MemoryEvent",
    "MemoryRecord",
    "BatchResult",
]
