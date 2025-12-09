"""
Pytest configuration for test suite
"""

from pathlib import Path
import sys

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
