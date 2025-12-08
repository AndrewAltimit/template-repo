"""
Pytest configuration and fixtures for AgentCore Memory tests.
"""

import os
import sys

import pytest

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_env_chromadb(monkeypatch):
    """Set environment for ChromaDB provider."""
    monkeypatch.setenv("MEMORY_PROVIDER", "chromadb")
    monkeypatch.setenv("CHROMADB_HOST", "localhost")
    monkeypatch.setenv("CHROMADB_PORT", "8000")
    monkeypatch.setenv("CHROMADB_COLLECTION", "test_memory")


@pytest.fixture
def mock_env_agentcore(monkeypatch):
    """Set environment for AgentCore provider."""
    monkeypatch.setenv("MEMORY_PROVIDER", "agentcore")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AGENTCORE_MEMORY_ID", "mem-test-12345")
