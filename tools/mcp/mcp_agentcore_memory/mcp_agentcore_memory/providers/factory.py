"""
Provider Factory

Creates memory providers based on configuration.
Supports AWS AgentCore and ChromaDB backends.
"""

import logging
import os
from typing import Optional

from .interface import MemoryProvider, ProviderType

logger = logging.getLogger(__name__)

# Singleton provider instance
_provider_instance: Optional[MemoryProvider] = None


def create_provider(provider_type: Optional[str] = None) -> MemoryProvider:
    """
    Factory to create memory provider based on configuration.

    Environment variables:
    - MEMORY_PROVIDER: agentcore or chromadb (default: chromadb)

    For agentcore:
    - AGENTCORE_MEMORY_ID: Memory instance ID (required)
    - AWS_REGION: AWS region (default: us-east-1)
    - AGENTCORE_DATA_PLANE_ENDPOINT: Optional VPC PrivateLink endpoint

    For chromadb:
    - CHROMADB_HOST: ChromaDB host (default: localhost)
    - CHROMADB_PORT: ChromaDB port (default: 8000)
    - CHROMADB_COLLECTION: Collection prefix (default: agent_memory)

    Args:
        provider_type: Override provider type (agentcore or chromadb)

    Returns:
        Configured MemoryProvider instance

    Raises:
        ValueError: If unknown provider type or missing required config
    """
    provider_str = provider_type if provider_type else os.environ.get("MEMORY_PROVIDER", "chromadb")
    provider = provider_str.lower().strip()

    logger.info("Creating memory provider: %s", provider)

    if provider == "agentcore":
        return _create_agentcore_provider()
    if provider == "chromadb":
        return _create_chromadb_provider()
    raise ValueError(f"Unknown provider: {provider}. Valid options: agentcore, chromadb")


def _create_agentcore_provider() -> MemoryProvider:
    """Create AWS AgentCore provider from environment."""
    from .agentcore import AgentCoreConfig, AgentCoreProvider

    memory_id = os.environ.get("AGENTCORE_MEMORY_ID")
    if not memory_id:
        raise ValueError("AGENTCORE_MEMORY_ID environment variable is required for agentcore provider")

    config = AgentCoreConfig(
        memory_id=memory_id,
        region=os.environ.get("AWS_REGION", "us-east-1"),
        data_plane_endpoint=os.environ.get("AGENTCORE_DATA_PLANE_ENDPOINT") or None,
    )

    logger.info(
        "Configured AgentCore provider: memory_id=%s, region=%s",
        config.memory_id,
        config.region,
    )

    return AgentCoreProvider(config)


def _create_chromadb_provider() -> MemoryProvider:
    """Create ChromaDB provider from environment."""
    from .chromadb_provider import ChromaDBConfig, ChromaDBProvider

    config = ChromaDBConfig(
        host=os.environ.get("CHROMADB_HOST", "localhost"),
        port=int(os.environ.get("CHROMADB_PORT", "8000")),
        collection_prefix=os.environ.get("CHROMADB_COLLECTION", "agent_memory"),
    )

    logger.info(
        "Configured ChromaDB provider: host=%s, port=%d, prefix=%s",
        config.host,
        config.port,
        config.collection_prefix,
    )

    return ChromaDBProvider(config)


def get_provider() -> MemoryProvider:
    """
    Get or create the singleton provider instance.

    Returns:
        The configured MemoryProvider
    """
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = create_provider()
    return _provider_instance


def reset_provider() -> None:
    """
    Reset the singleton provider (useful for testing).
    """
    global _provider_instance
    _provider_instance = None


def get_provider_type() -> ProviderType:
    """
    Get the configured provider type without creating the provider.

    Returns:
        ProviderType enum value
    """
    provider = os.environ.get("MEMORY_PROVIDER", "chromadb").lower().strip()
    if provider == "agentcore":
        return ProviderType.AGENTCORE
    if provider == "chromadb":
        return ProviderType.CHROMADB
    raise ValueError(f"Unknown provider: {provider}")
