"""Dependency injection for FastAPI routes.

This module breaks the cyclic import between api/main.py and api/routes/*.py
by providing accessor functions for shared state instead of importing main directly.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.container_manager import ContainerManager
    from core.database import Database


def get_db() -> "Database":
    """Get the database instance.

    Returns:
        Database instance initialized in main.py
    """
    from api import main as app_main

    return app_main.db


def get_container_manager() -> "ContainerManager":
    """Get the container manager instance.

    Returns:
        ContainerManager instance initialized in main.py
    """
    from api import main as app_main

    return app_main.container_manager
