#!/usr/bin/env python3
"""Basic tests that can run without full server initialization"""

import asyncio

import pytest


def test_imports():
    """Test that basic imports work"""
    # Test core imports
    # Note: All MCP servers have been migrated to Rust. No Python MCP modules to test.
    # Testing sleeper_agents as a representative Python package
    from sleeper_agents import DetectionConfig  # noqa: E402

    assert DetectionConfig is not None


def test_basic_functionality():
    """Test basic functionality without server initialization"""
    assert 1 + 1 == 2
    assert isinstance(42, int)


@pytest.mark.asyncio
async def test_async_basic():
    """Test basic async functionality"""

    async def get_value():
        await asyncio.sleep(0.01)
        return 42

    result = await get_value()
    assert result == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
