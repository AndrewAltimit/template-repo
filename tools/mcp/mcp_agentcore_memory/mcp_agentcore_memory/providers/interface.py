"""
Abstract Memory Provider Interface

All memory providers must implement this interface to be swappable.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderType(Enum):
    """Supported memory provider types."""

    AGENTCORE = "agentcore"
    CHROMADB = "chromadb"


@dataclass
class MemoryEvent:
    """Short-term memory event."""

    id: str
    actor_id: str
    session_id: str
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryRecord:
    """Long-term memory record."""

    id: str
    content: str
    namespace: str
    relevance: Optional[float] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    """Result of batch operations."""

    created: int
    failed: int
    errors: List[str] = field(default_factory=list)


class MemoryProvider(ABC):
    """
    Abstract interface for memory providers.

    All providers must implement this interface to be swappable.
    The MCP server is provider-agnostic and uses this interface.
    """

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type."""

    @property
    @abstractmethod
    def supports_semantic_search(self) -> bool:
        """Whether this provider supports semantic/vector search."""

    # ─────────────────────────────────────────────────────────────
    # Short-term memory (events)
    # ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def store_event(
        self,
        actor_id: str,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEvent:
        """
        Store a short-term memory event.

        Note: AWS AgentCore has rate limits (0.25 req/sec per actor+session).
        Self-hosted providers typically don't have this limitation.

        Args:
            actor_id: Identifier for the actor (agent or user)
            session_id: Session identifier (max 100 chars for AgentCore)
            content: Content to store
            metadata: Optional metadata dict

        Returns:
            The created MemoryEvent
        """

    @abstractmethod
    async def list_events(
        self,
        actor_id: str,
        session_id: str,
        limit: int = 100,
    ) -> List[MemoryEvent]:
        """
        List events for a session.

        Args:
            actor_id: Actor identifier
            session_id: Session identifier
            limit: Maximum number of events to return

        Returns:
            List of MemoryEvents, most recent first
        """

    # ─────────────────────────────────────────────────────────────
    # Long-term memory (records/facts)
    # ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def store_records(
        self,
        records: List[Dict[str, Any]],
        namespace: str,
    ) -> BatchResult:
        """
        Store long-term memory records (facts, patterns).

        Args:
            records: List of {"content": str, "metadata": dict}
            namespace: Target namespace (e.g., "codebase/patterns")

        Returns:
            BatchResult with created/failed counts
        """

    @abstractmethod
    async def search_records(
        self,
        query: str,
        namespace: str,
        top_k: int = 10,
    ) -> List[MemoryRecord]:
        """
        Search long-term records with semantic similarity.

        Falls back to keyword search if semantic not supported.

        Args:
            query: Search query (required)
            namespace: Namespace to search in
            top_k: Maximum results to return

        Returns:
            List of MemoryRecords sorted by relevance
        """

    @abstractmethod
    async def list_records(
        self,
        namespace: str,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        """
        List all records in a namespace (no search).

        Args:
            namespace: Namespace to list
            limit: Maximum records to return

        Returns:
            List of MemoryRecords
        """

    # ─────────────────────────────────────────────────────────────
    # Health & Info
    # ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if provider is healthy and connected.

        Returns:
            True if healthy, False otherwise
        """

    @abstractmethod
    async def get_info(self) -> Dict[str, Any]:
        """
        Get provider info and capabilities.

        Returns:
            Dict with provider details (type, rate limits, features, etc.)
        """
