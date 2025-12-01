#!/usr/bin/env python3
"""Basic tests that can run without full server initialization"""

import asyncio

import pytest


def test_imports():
    """Test that basic imports work"""
    # Test code quality imports
    from mcp_code_quality.tools import TOOLS as CODE_TOOLS  # noqa: E402

    assert len(CODE_TOOLS) > 0

    # Test content creation imports
    from mcp_content_creation.tools import TOOLS as CONTENT_TOOLS  # noqa: E402

    assert len(CONTENT_TOOLS) > 0

    # Test core imports
    from mcp_core.base_server import BaseMCPServer  # noqa: E402

    assert BaseMCPServer is not None


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
