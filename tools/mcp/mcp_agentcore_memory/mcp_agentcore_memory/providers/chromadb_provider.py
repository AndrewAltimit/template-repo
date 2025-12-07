"""
ChromaDB Provider for Self-Hosted Vector Memory

Benefits over AWS AgentCore:
- No rate limits
- No AWS dependency
- Full control over data
- Free (self-hosted)

Requirements:
- ChromaDB server running (docker or local)
- Uses sentence-transformers for embeddings by default
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ..sanitize import sanitize_content
from .interface import BatchResult, MemoryEvent, MemoryProvider, MemoryRecord, ProviderType

logger = logging.getLogger(__name__)


@dataclass
class ChromaDBConfig:
    """Configuration for ChromaDB provider."""

    host: str = "localhost"
    port: int = 8000
    collection_prefix: str = "agent_memory"
    # Set to False if telemetry is a concern
    anonymized_telemetry: bool = False


class ChromaDBProvider(MemoryProvider):
    """
    Self-hosted ChromaDB provider with vector search.

    Features:
    - No rate limits (unlike AWS AgentCore)
    - Native embedding support via sentence-transformers
    - Simple setup with docker-compose
    - Zero AWS cost

    Attributes:
        config: ChromaDB configuration
        client: ChromaDB HTTP client
    """

    def __init__(self, config: ChromaDBConfig):
        """
        Initialize ChromaDB provider.

        Args:
            config: ChromaDB configuration
        """
        self.config = config
        self._client = None
        self._events_collection = None
        self._records_collections: Dict[str, Any] = {}

    def _get_client(self):
        """Get or create ChromaDB client."""
        if self._client is None:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.HttpClient(
                host=self.config.host,
                port=self.config.port,
                settings=Settings(
                    anonymized_telemetry=self.config.anonymized_telemetry,
                ),
            )
        return self._client

    def _get_events_collection(self):
        """Get or create events collection."""
        if self._events_collection is None:
            client = self._get_client()
            self._events_collection = client.get_or_create_collection(
                name=f"{self.config.collection_prefix}_events",
                metadata={"hnsw:space": "cosine"},
            )
        return self._events_collection

    def _get_records_collection(self, namespace: str):
        """Get or create records collection for a namespace."""
        if namespace not in self._records_collections:
            client = self._get_client()
            # Replace / with _ for valid collection name
            safe_name = namespace.replace("/", "_").replace("-", "_")
            self._records_collections[namespace] = client.get_or_create_collection(
                name=f"{self.config.collection_prefix}_records_{safe_name}",
                metadata={"hnsw:space": "cosine"},
            )
        return self._records_collections[namespace]

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.CHROMADB

    @property
    def supports_semantic_search(self) -> bool:
        """ChromaDB has native embedding support."""
        return True

    async def store_event(
        self,
        actor_id: str,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEvent:
        """
        Store a short-term memory event.

        No rate limits in ChromaDB!

        Args:
            actor_id: Actor identifier
            session_id: Session identifier
            content: Content to store
            metadata: Optional metadata

        Returns:
            Created MemoryEvent
        """
        # Sanitize content to prevent secret storage
        sanitized_content = sanitize_content(content)

        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        collection = self._get_events_collection()
        collection.add(
            ids=[event_id],
            documents=[sanitized_content],
            metadatas=[
                {
                    "actor_id": actor_id,
                    "session_id": session_id,
                    "timestamp": timestamp.isoformat(),
                    **(metadata or {}),
                }
            ],
        )

        logger.debug(
            "Created event %s for actor=%s session=%s",
            event_id,
            actor_id,
            session_id,
        )

        return MemoryEvent(
            id=event_id,
            actor_id=actor_id,
            session_id=session_id,
            content=sanitized_content,
            timestamp=timestamp,
            metadata=metadata or {},
        )

    async def list_events(
        self,
        actor_id: str,
        session_id: str,
        limit: int = 100,
    ) -> List[MemoryEvent]:
        """
        List events from a session.

        Args:
            actor_id: Actor identifier
            session_id: Session identifier
            limit: Maximum events to return

        Returns:
            List of MemoryEvents, most recent first
        """
        collection = self._get_events_collection()

        # ChromaDB where filter with AND
        results = collection.get(
            where={
                "$and": [
                    {"actor_id": {"$eq": actor_id}},
                    {"session_id": {"$eq": session_id}},
                ]
            },
            limit=limit,
            include=["documents", "metadatas"],
        )

        events = []
        for i, doc_id in enumerate(results.get("ids", [])):
            meta = results.get("metadatas", [])[i] if results.get("metadatas") else {}
            doc = results.get("documents", [])[i] if results.get("documents") else ""

            events.append(
                MemoryEvent(
                    id=doc_id,
                    actor_id=meta.get("actor_id", actor_id),
                    session_id=meta.get("session_id", session_id),
                    content=doc,
                    timestamp=(
                        datetime.fromisoformat(meta["timestamp"]) if "timestamp" in meta else datetime.now(timezone.utc)
                    ),
                    metadata={k: v for k, v in meta.items() if k not in ("actor_id", "session_id", "timestamp")},
                )
            )

        # Sort by timestamp descending
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events

    async def store_records(
        self,
        records: List[Dict[str, Any]],
        namespace: str,
    ) -> BatchResult:
        """
        Store long-term memory records.

        Args:
            records: List of {"content": str, "metadata": dict}
            namespace: Target namespace

        Returns:
            BatchResult with created/failed counts
        """
        if not records:
            return BatchResult(created=0, failed=0)

        collection = self._get_records_collection(namespace)

        ids = []
        documents = []
        metadatas = []

        for record in records:
            record_id = str(uuid.uuid4())
            sanitized = sanitize_content(record.get("content", ""))

            ids.append(record_id)
            documents.append(sanitized)
            metadatas.append(
                {
                    "namespace": namespace,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    **(record.get("metadata", {})),
                }
            )

        try:
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
            logger.debug("Stored %d records in namespace %s", len(records), namespace)
            return BatchResult(created=len(records), failed=0)
        except Exception as e:
            logger.error("Failed to store records: %s", e)
            return BatchResult(created=0, failed=len(records), errors=[str(e)])

    async def search_records(
        self,
        query: str,
        namespace: str,
        top_k: int = 10,
    ) -> List[MemoryRecord]:
        """
        Search long-term records with semantic similarity.

        Args:
            query: Search query
            namespace: Namespace to search in
            top_k: Maximum results to return

        Returns:
            List of MemoryRecords sorted by relevance
        """
        collection = self._get_records_collection(namespace)

        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        records = []
        if results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
                doc = results.get("documents", [[]])[0][i] if results.get("documents") else ""
                # Convert distance to similarity (cosine: 1 - distance)
                distance = results.get("distances", [[]])[0][i] if results.get("distances") else 0
                relevance = 1.0 - distance

                records.append(
                    MemoryRecord(
                        id=doc_id,
                        content=doc,
                        namespace=namespace,
                        relevance=relevance,
                        created_at=datetime.fromisoformat(meta["created_at"]) if "created_at" in meta else None,
                        metadata={k: v for k, v in meta.items() if k not in ("namespace", "created_at")},
                    )
                )

        return records

    async def list_records(
        self,
        namespace: str,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        """
        List memory records in a namespace (no semantic search).

        Args:
            namespace: Namespace to list
            limit: Maximum records to return

        Returns:
            List of MemoryRecords
        """
        collection = self._get_records_collection(namespace)
        results = collection.get(limit=limit, include=["documents", "metadatas"])

        records = []
        for i, doc_id in enumerate(results.get("ids", [])):
            meta = results.get("metadatas", [])[i] if results.get("metadatas") else {}
            doc = results.get("documents", [])[i] if results.get("documents") else ""

            records.append(
                MemoryRecord(
                    id=doc_id,
                    content=doc,
                    namespace=namespace,
                    created_at=datetime.fromisoformat(meta["created_at"]) if "created_at" in meta else None,
                    metadata=meta,
                )
            )

        return records

    async def health_check(self) -> bool:
        """
        Check ChromaDB connectivity.

        Returns:
            True if healthy, False otherwise
        """
        try:
            client = self._get_client()
            client.heartbeat()
            return True
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            return False

    async def get_info(self) -> Dict[str, Any]:
        """
        Get provider info and capabilities.

        Returns:
            Dict with provider details
        """
        return {
            "provider": "chromadb",
            "host": self.config.host,
            "port": self.config.port,
            "collection_prefix": self.config.collection_prefix,
            "rate_limit": None,  # No rate limits!
            "semantic_search": True,
            "managed_service": False,
        }
