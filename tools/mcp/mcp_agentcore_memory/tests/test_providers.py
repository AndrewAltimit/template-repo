"""
Tests for memory providers.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_agentcore_memory.providers.interface import (
    BatchResult,
    MemoryEvent,
    MemoryRecord,
    ProviderType,
)
import pytest

# Check if botocore is available for AgentCore tests
try:
    import botocore  # noqa: F401

    HAS_BOTOCORE = True
except ImportError:
    HAS_BOTOCORE = False


class TestProviderInterface:
    """Tests for the abstract provider interface."""

    def test_provider_type_enum(self):
        """ProviderType enum should have expected values."""
        assert ProviderType.AGENTCORE.value == "agentcore"
        assert ProviderType.CHROMADB.value == "chromadb"

    def test_memory_event_creation(self):
        """MemoryEvent dataclass creation."""
        event = MemoryEvent(
            id="evt-123",
            actor_id="actor1",
            session_id="session1",
            content="Test content",
            timestamp=datetime.now(timezone.utc),
            metadata={"key": "value"},
        )

        assert event.id == "evt-123"
        assert event.actor_id == "actor1"
        assert event.metadata["key"] == "value"

    def test_memory_record_creation(self):
        """MemoryRecord dataclass creation."""
        record = MemoryRecord(
            id="rec-123",
            content="Test content",
            namespace="codebase/patterns",
            relevance=0.95,
        )

        assert record.id == "rec-123"
        assert record.namespace == "codebase/patterns"
        assert record.relevance == 0.95

    def test_batch_result_creation(self):
        """BatchResult dataclass creation."""
        result = BatchResult(created=5, failed=1, errors=["error1"])

        assert result.created == 5
        assert result.failed == 1
        assert len(result.errors) == 1


@pytest.mark.skipif(not HAS_BOTOCORE, reason="botocore not installed")
class TestAgentCoreProvider:
    """Tests for AWS AgentCore provider with mocked aiobotocore."""

    @pytest.fixture
    def mock_config(self):
        """Mock AgentCore config."""
        from mcp_agentcore_memory.providers.agentcore import AgentCoreConfig

        return AgentCoreConfig(
            memory_id="mem-test-12345",
            region="us-east-1",
        )

    @pytest.fixture
    def mock_aiobotocore_client(self):
        """Create a mock aiobotocore client with async context manager."""
        mock_client = AsyncMock()

        @asynccontextmanager
        async def mock_context():
            yield mock_client

        return mock_client, mock_context

    @pytest.mark.asyncio
    async def test_store_event(self, mock_config, mock_aiobotocore_client):
        """Test store_event with mocked aiobotocore."""
        from mcp_agentcore_memory.providers.agentcore import AgentCoreProvider

        mock_client, mock_context = mock_aiobotocore_client

        # Setup mock response
        mock_client.create_event.return_value = {"event": {"eventId": "evt-123", "sessionId": "test-session"}}

        provider = AgentCoreProvider(mock_config)

        # Patch the internal context manager and rate limiter
        with patch.object(provider, "_get_data_plane_client", mock_context):
            with patch("mcp_agentcore_memory.providers.agentcore.get_event_rate_limiter") as mock_limiter:
                mock_limiter.return_value.acquire = AsyncMock()

                event = await provider.store_event(
                    actor_id="test-actor",
                    session_id="test-session",
                    content="Test memory content",
                )

        assert event.id == "evt-123"
        assert event.actor_id == "test-actor"
        mock_client.create_event.assert_called_once()

        # Verify correct API shape was used
        call_kwargs = mock_client.create_event.call_args.kwargs
        assert "branch" in call_kwargs  # Should be struct
        assert "payload" in call_kwargs
        assert isinstance(call_kwargs["payload"], list)

    @pytest.mark.asyncio
    async def test_search_records_requires_query(self, mock_config, mock_aiobotocore_client):
        """Test that search_records requires a non-empty query."""
        from mcp_agentcore_memory.providers.agentcore import AgentCoreProvider

        mock_client, mock_context = mock_aiobotocore_client
        provider = AgentCoreProvider(mock_config)

        with pytest.raises(ValueError, match="query is required"):
            with patch.object(provider, "_get_data_plane_client", mock_context):
                await provider.search_records(
                    query="",  # Empty query should fail
                    namespace="test/namespace",
                )

    @pytest.mark.asyncio
    async def test_store_records(self, mock_config, mock_aiobotocore_client):
        """Test batch store records."""
        from mcp_agentcore_memory.providers.agentcore import AgentCoreProvider

        mock_client, mock_context = mock_aiobotocore_client

        # API uses successfulRecords/failedRecords not memoryRecords/errors
        mock_client.batch_create_memory_records.return_value = {
            "successfulRecords": [{"memoryRecordId": "rec-1"}, {"memoryRecordId": "rec-2"}],
            "failedRecords": [],
        }

        provider = AgentCoreProvider(mock_config)

        with patch.object(provider, "_get_data_plane_client", mock_context):
            result = await provider.store_records(
                records=[
                    {"content": "Fact 1", "metadata": {}},
                    {"content": "Fact 2", "metadata": {}},
                ],
                namespace="codebase/patterns",
            )

        assert result.created == 2
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_health_check(self, mock_config, mock_aiobotocore_client):
        """Test health check."""
        from mcp_agentcore_memory.providers.agentcore import AgentCoreProvider

        mock_client, mock_context = mock_aiobotocore_client
        mock_client.list_events.return_value = {"events": []}

        provider = AgentCoreProvider(mock_config)

        with patch.object(provider, "_get_data_plane_client", mock_context):
            healthy = await provider.health_check()

        assert healthy is True

    @pytest.mark.asyncio
    async def test_get_info(self, mock_config):
        """Test get_info returns correct provider info."""
        from mcp_agentcore_memory.providers.agentcore import AgentCoreProvider

        provider = AgentCoreProvider(mock_config)
        info = await provider.get_info()

        assert info["provider"] == "agentcore"
        assert info["memory_id"] == "mem-test-12345"
        assert info["region"] == "us-east-1"
        assert "rate_limit" in info

    @pytest.mark.asyncio
    async def test_session_id_length_validation(self, mock_config, mock_aiobotocore_client):
        """Test that session_id > 100 chars is rejected."""
        from mcp_agentcore_memory.providers.agentcore import AgentCoreProvider

        mock_client, mock_context = mock_aiobotocore_client
        provider = AgentCoreProvider(mock_config)

        long_session_id = "x" * 101  # Exceeds 100 char limit

        with pytest.raises(ValueError, match="session_id must be <= 100"):
            with patch.object(provider, "_get_data_plane_client", mock_context):
                with patch("mcp_agentcore_memory.providers.agentcore.get_event_rate_limiter") as mock_limiter:
                    mock_limiter.return_value.acquire = AsyncMock()
                    await provider.store_event(
                        actor_id="test-actor",
                        session_id=long_session_id,
                        content="Test content",
                    )

    @pytest.mark.asyncio
    async def test_aws_throttling_exception_handling(self, mock_config, mock_aiobotocore_client):
        """Test behavior when AWS returns ThrottlingException."""
        from botocore.exceptions import ClientError
        from mcp_agentcore_memory.providers.agentcore import AgentCoreProvider

        mock_client, mock_context = mock_aiobotocore_client

        # Simulate AWS ThrottlingException
        mock_client.create_event.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "CreateEvent",
        )

        provider = AgentCoreProvider(mock_config)

        with pytest.raises(ClientError) as exc_info:
            with patch.object(provider, "_get_data_plane_client", mock_context):
                with patch("mcp_agentcore_memory.providers.agentcore.get_event_rate_limiter") as mock_limiter:
                    mock_limiter.return_value.acquire = AsyncMock()
                    await provider.store_event(
                        actor_id="test-actor",
                        session_id="test-session",
                        content="Test content",
                    )

        assert exc_info.value.response["Error"]["Code"] == "ThrottlingException"

    @pytest.mark.asyncio
    async def test_partial_batch_failure(self, mock_config, mock_aiobotocore_client):
        """Test BatchCreateMemoryRecords with partial failures."""
        from mcp_agentcore_memory.providers.agentcore import AgentCoreProvider

        mock_client, mock_context = mock_aiobotocore_client

        # Simulate partial failure - 2 succeed, 1 fails
        # API uses successfulRecords/failedRecords not memoryRecords/errors
        mock_client.batch_create_memory_records.return_value = {
            "successfulRecords": [{"memoryRecordId": "rec-1"}, {"memoryRecordId": "rec-2"}],
            "failedRecords": [{"message": "Invalid record format"}],
        }

        provider = AgentCoreProvider(mock_config)

        with patch.object(provider, "_get_data_plane_client", mock_context):
            result = await provider.store_records(
                records=[
                    {"content": "Fact 1", "metadata": {}},
                    {"content": "Fact 2", "metadata": {}},
                    {"content": "Invalid", "metadata": {}},
                ],
                namespace="test/namespace",
            )

        assert result.created == 2
        assert result.failed == 1
        assert len(result.errors) == 1


class TestChromaDBProvider:
    """Tests for ChromaDB provider with mocked client."""

    @pytest.fixture
    def mock_chromadb(self):
        """Mock ChromaDB client and collection."""
        mock_collection = MagicMock()
        mock_collection.add = MagicMock()
        mock_collection.get = MagicMock(
            return_value={
                "ids": ["id-1"],
                "documents": ["content 1"],
                "metadatas": [{"actor_id": "actor1", "session_id": "session1", "timestamp": "2024-01-01T00:00:00+00:00"}],
            }
        )
        mock_collection.query = MagicMock(
            return_value={
                "ids": [["id-1"]],
                "documents": [["content 1"]],
                "metadatas": [[{"created_at": "2024-01-01T00:00:00+00:00"}]],
                "distances": [[0.1]],
            }
        )

        mock_client = MagicMock()
        mock_client.get_or_create_collection = MagicMock(return_value=mock_collection)
        mock_client.heartbeat = MagicMock()

        return mock_client, mock_collection

    @pytest.mark.asyncio
    async def test_store_event(self, mock_chromadb):
        """Test store_event with mocked ChromaDB."""
        from mcp_agentcore_memory.providers.chromadb_provider import ChromaDBConfig, ChromaDBProvider

        mock_client, mock_collection = mock_chromadb

        config = ChromaDBConfig(host="localhost", port=8000)
        provider = ChromaDBProvider(config)
        provider._client = mock_client
        provider._events_collection = mock_collection

        event = await provider.store_event(
            actor_id="actor1",
            session_id="session1",
            content="Test content",
        )

        assert event.actor_id == "actor1"
        assert event.session_id == "session1"
        mock_collection.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_records(self, mock_chromadb):
        """Test search_records with mocked ChromaDB."""
        from mcp_agentcore_memory.providers.chromadb_provider import ChromaDBConfig, ChromaDBProvider

        mock_client, mock_collection = mock_chromadb

        config = ChromaDBConfig(host="localhost", port=8000)
        provider = ChromaDBProvider(config)
        provider._client = mock_client
        provider._records_collections["test/namespace"] = mock_collection

        records = await provider.search_records(
            query="test query",
            namespace="test/namespace",
            top_k=5,
        )

        assert len(records) == 1
        assert records[0].relevance == 0.9  # 1 - 0.1 distance
        mock_collection.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check(self, mock_chromadb):
        """Test health check."""
        from mcp_agentcore_memory.providers.chromadb_provider import ChromaDBConfig, ChromaDBProvider

        mock_client, _ = mock_chromadb

        config = ChromaDBConfig(host="localhost", port=8000)
        provider = ChromaDBProvider(config)
        provider._client = mock_client

        healthy = await provider.health_check()
        assert healthy is True
        mock_client.heartbeat.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_info(self):
        """Test get_info returns correct provider info."""
        from mcp_agentcore_memory.providers.chromadb_provider import ChromaDBConfig, ChromaDBProvider

        config = ChromaDBConfig(host="localhost", port=8000)
        provider = ChromaDBProvider(config)

        info = await provider.get_info()

        assert info["provider"] == "chromadb"
        assert info["host"] == "localhost"
        assert info["port"] == 8000
        assert info["rate_limit"] is None  # No rate limits!
