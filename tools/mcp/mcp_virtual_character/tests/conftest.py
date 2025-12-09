"""
Pytest configuration for Virtual Character MCP tests.
"""

from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Enable pytest-asyncio for all async tests
pytest_plugins = ["pytest_asyncio"]
