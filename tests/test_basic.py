#!/usr/bin/env python3
"""Basic tests that can run without full server initialization"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import pytest  # noqa: E402


def test_imports():
    """Test that basic imports work"""
    # Test code quality imports
    from tools.mcp.code_quality.tools import TOOLS as CODE_TOOLS

    assert len(CODE_TOOLS) > 0

    # Test content creation imports
    from tools.mcp.content_creation.tools import TOOLS as CONTENT_TOOLS

    assert len(CONTENT_TOOLS) > 0

    # Test core imports
    from tools.mcp.core.base_server import BaseMCPServer

    assert BaseMCPServer is not None


def test_basic_functionality():
    """Test basic functionality without server initialization"""
    assert 1 + 1 == 2
    assert isinstance(42, int)


@pytest.mark.asyncio
async def test_async_basic():
    """Test basic async functionality"""
    import asyncio

    async def get_value():
        await asyncio.sleep(0.01)
        return 42

    result = await get_value()
    assert result == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
