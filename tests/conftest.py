"""
Pytest configuration for test suite
"""

from pathlib import Path
import sys

import pytest

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Enable pytest-asyncio for all async tests
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()
