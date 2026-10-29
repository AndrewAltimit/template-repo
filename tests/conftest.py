"""
Pytest configuration for test suite
"""

from pathlib import Path
import sys

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Enable pytest-asyncio for all async tests. The default event loop is used;
# overriding the `event_loop_policy` fixture is deprecated in pytest-asyncio 1.x
# (and asyncio event loop policies are deprecated from Python 3.14).
pytest_plugins = ["pytest_asyncio"]
