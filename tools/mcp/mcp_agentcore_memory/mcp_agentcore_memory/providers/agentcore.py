"""
AWS Bedrock AgentCore Memory Provider

Uses aiobotocore for truly async operations (NOT boto3 which is synchronous).

CRITICAL CONSTRAINTS:
- Rate limited: 0.25 req/sec per actor+session for CreateEvent
- Control plane (CreateMemory) uses different endpoint than data plane
- Payload shapes must match exactly per API docs

References:
- CreateEvent API: AWS Bedrock AgentCore APIReference
- RetrieveMemoryRecords: AWS Bedrock AgentCore APIReference
- BatchCreateMemoryRecords: AWS Bedrock AgentCore APIReference
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ..rate_limiter import get_event_rate_limiter
from ..sanitize import sanitize_content
from .interface import BatchResult, MemoryEvent, MemoryProvider, MemoryRecord, ProviderType

logger = logging.getLogger(__name__)


@dataclass
class AgentCoreConfig:
    """Configuration for AgentCore Memory client."""

    memory_id: str
    region: str = "us-east-1"
    data_plane_endpoint: Optional[str] = None  # For VPC PrivateLink (data plane only)
    max_retries: int = 3
    timeout: int = 30


class AgentCoreProvider(MemoryProvider):
    """
    AWS Bedrock AgentCore Memory provider.

    Uses aiobotocore for truly async operations.

    CRITICAL CONSTRAINTS:
    - Rate limited: 0.25 req/sec per actor+session for CreateEvent
    - Use store_records() for facts (no rate limit via BatchCreateMemoryRecords)
    - Control plane (setup) uses different endpoint

    Attributes:
        config: AgentCore configuration
        _session: aiobotocore session for async client creation
    """

    def __init__(self, config: AgentCoreConfig):
        """
        Initialize the AgentCore provider.

        Args:
            config: AgentCore configuration with memory_id and region
        """
        self.config = config
        self._session = None  # Lazy initialization
        self._boto_config = None  # Lazy initialization

    def _get_boto_config(self):
        """Get or create botocore Config (lazy import)."""
        if self._boto_config is None:
            from botocore.config import Config

            self._boto_config = Config(
                retries={"max_attempts": self.config.max_retries},
                connect_timeout=self.config.timeout,
                read_timeout=self.config.timeout,
            )
        return self._boto_config

    def _get_session(self):
        """Get or create aiobotocore session."""
        if self._session is None:
            from aiobotocore.session import get_session

            self._session = get_session()
        return self._session

    @asynccontextmanager
    async def _get_data_plane_client(self):
        """
        Get async data plane client (bedrock-agentcore).

        Uses context manager for proper resource cleanup.
        """
        session = self._get_session()
        async with session.create_client(
            "bedrock-agentcore",
            region_name=self.config.region,
            endpoint_url=self.config.data_plane_endpoint,
            config=self._get_boto_config(),
        ) as client:
            yield client

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.AGENTCORE

    @property
    def supports_semantic_search(self) -> bool:
        """AgentCore has native semantic search."""
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

        IMPORTANT: Rate limited to 0.25 req/sec per actor+session!
        Only use for sparse, high-value events:
        - Session start goals
        - Key decisions made
        - Periodic summaries
        - Final outcomes

        Args:
            actor_id: Actor identifier (e.g., 'repo:myrepo:agent:claude')
            session_id: Session identifier (max 100 chars)
            content: Content to store
            metadata: Optional metadata

        Returns:
            Created MemoryEvent
        """
        # Validate session_id length per API requirements
        if len(session_id) > 100:
            raise ValueError("session_id must be <= 100 characters")

        # Sanitize content to prevent secret storage
        sanitized_content = sanitize_content(content)

        # Apply rate limiting (blocks up to 4 seconds if needed)
        rate_limiter = get_event_rate_limiter()
        await rate_limiter.acquire(actor_id, session_id)

        # Generate idempotency token for safe retries
        client_token = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        async with self._get_data_plane_client() as client:
            response = await client.create_event(
                memoryId=self.config.memory_id,
                actorId=actor_id,
                sessionId=session_id,
                branch={"name": "main"},
                eventTimestamp=timestamp,
                payload=[
                    {
                        "conversational": {
                            "content": {"text": sanitized_content},
                            "role": "USER",  # or "ASSISTANT"
                        }
                    }
                ],
                clientToken=client_token,
            )

            # Response shape: {"event": {"eventId": "...", ...}}
            event_id = response.get("event", {}).get("eventId", client_token)

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
        List events from a session with pagination.

        Args:
            actor_id: Actor identifier
            session_id: Session identifier
            limit: Maximum events to return

        Returns:
            List of MemoryEvents, most recent first
        """
        events: List[MemoryEvent] = []
        next_token = None

        async with self._get_data_plane_client() as client:
            while len(events) < limit:
                params = {
                    "memoryId": self.config.memory_id,
                    "actorId": actor_id,
                    "sessionId": session_id,
                    "maxResults": min(limit - len(events), 100),
                }
                if next_token:
                    params["nextToken"] = next_token

                response = await client.list_events(**params)

                for event in response.get("events", []):
                    # Extract content from payload structure
                    payload = event.get("payload", [])
                    content = ""
                    if payload and isinstance(payload, list):
                        conv = payload[0].get("conversational", {})
                        content = conv.get("content", {}).get("text", "")

                    events.append(
                        MemoryEvent(
                            id=event.get("eventId", ""),
                            actor_id=actor_id,
                            session_id=session_id,
                            content=content,
                            timestamp=event.get("eventTimestamp", datetime.now(timezone.utc)),
                            metadata=event.get("metadata", {}),
                        )
                    )

                next_token = response.get("nextToken")
                if not next_token:
                    break

        return events[:limit]

    async def store_records(
        self,
        records: List[Dict[str, Any]],
        namespace: str,
    ) -> BatchResult:
        """
        Store long-term memory records directly (bypasses short-term extraction).

        This is the PREFERRED method for explicit fact storage.
        Uses BatchCreateMemoryRecords - no rate limit concerns!

        Args:
            records: List of {"content": str, "metadata": dict}
            namespace: Target namespace (e.g., "codebase/patterns")

        Returns:
            BatchResult with created/failed counts
        """
        if not records:
            return BatchResult(created=0, failed=0)

        # Build memory records with sanitized content
        # API requires: requestIdentifier, namespaces (list), content, timestamp
        memory_records = []
        timestamp = datetime.now(timezone.utc)
        for r in records:
            sanitized = sanitize_content(r.get("content", ""))
            memory_records.append(
                {
                    "requestIdentifier": str(uuid.uuid4()),  # Unique per record
                    "namespaces": [namespace],  # List of namespaces
                    "content": {"text": sanitized},
                    "timestamp": timestamp,
                    # Note: metadata not supported in this API
                }
            )

        async with self._get_data_plane_client() as client:
            response = await client.batch_create_memory_records(
                memoryId=self.config.memory_id,
                records=memory_records,  # API uses 'records' not 'memoryRecords'
            )

            # Response uses successfulRecords/failedRecords not memoryRecords/errors
            created = len(response.get("successfulRecords", []))
            errors = response.get("failedRecords", [])

            logger.debug(
                "BatchCreateMemoryRecords: %d created, %d failed in namespace %s",
                created,
                len(errors),
                namespace,
            )

            return BatchResult(
                created=created,
                failed=len(errors),
                errors=[str(e) for e in errors],
            )

    async def search_records(
        self,
        query: str,
        namespace: str,
        top_k: int = 10,
    ) -> List[MemoryRecord]:
        """
        Search long-term records with semantic similarity.

        IMPORTANT: query is REQUIRED by the AWS API.

        Args:
            query: Search query (required, non-empty)
            namespace: Namespace to search in
            top_k: Maximum results to return

        Returns:
            List of MemoryRecords sorted by relevance
        """
        if not query or not query.strip():
            raise ValueError("query is required for search_records. Use list_records() to list without searching.")

        async with self._get_data_plane_client() as client:
            response = await client.retrieve_memory_records(
                memoryId=self.config.memory_id,
                namespace=namespace,
                maxResults=top_k,
                # API uses searchQuery (string), not semanticQuery
                searchCriteria={
                    "searchQuery": query,
                    "topK": top_k,
                },
            )

            # Response may use memoryRecordSummaries, not memoryRecords
            records = response.get("memoryRecordSummaries", [])

            return [
                MemoryRecord(
                    id=r.get("memoryRecordId", ""),
                    content=(
                        r.get("content", {}).get("text", "")
                        if isinstance(r.get("content"), dict)
                        else str(r.get("content", ""))
                    ),
                    namespace=r.get("namespace", namespace),
                    relevance=r.get("relevanceScore"),
                    created_at=r.get("createdAt"),
                    metadata=r.get("metadata", {}),
                )
                for r in records
            ]

    async def list_records(
        self,
        namespace: str,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        """
        List memory records in a namespace WITHOUT semantic search.

        Use this for enumeration/backup. For search, use search_records().

        Args:
            namespace: Namespace to list
            limit: Maximum records to return

        Returns:
            List of MemoryRecords
        """
        records: List[MemoryRecord] = []
        next_token = None

        async with self._get_data_plane_client() as client:
            while len(records) < limit:
                params = {
                    "memoryId": self.config.memory_id,
                    "namespace": namespace,
                    "maxResults": min(limit - len(records), 100),
                }
                if next_token:
                    params["nextToken"] = next_token

                response = await client.list_memory_records(**params)

                for r in response.get("memoryRecords", []):
                    content = r.get("content", {})
                    if isinstance(content, dict):
                        content_text = content.get("text", "")
                    else:
                        content_text = str(content)

                    records.append(
                        MemoryRecord(
                            id=r.get("memoryRecordId", ""),
                            content=content_text,
                            namespace=r.get("namespace", namespace),
                            created_at=r.get("createdAt"),
                            metadata=r.get("metadata", {}),
                        )
                    )

                next_token = response.get("nextToken")
                if not next_token:
                    break

        return records[:limit]

    async def health_check(self) -> bool:
        """
        Check connectivity to AgentCore.

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with self._get_data_plane_client() as client:
                # Simple list with minimal results to verify connectivity
                await client.list_events(
                    memoryId=self.config.memory_id,
                    actorId="health-check",
                    sessionId="ping",
                    maxResults=1,
                )
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
            "provider": "agentcore",
            "memory_id": self.config.memory_id,
            "region": self.config.region,
            "endpoint": self.config.data_plane_endpoint or "public",
            "rate_limit": "0.25 req/sec per actor+session (CreateEvent only)",
            "semantic_search": True,
            "managed_service": True,
        }
