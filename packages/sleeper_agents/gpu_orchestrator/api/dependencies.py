# pylint: disable=cyclic-import
# Rationale: This module intentionally uses deferred imports to break the cyclic
# dependency between api/main.py and api/routes/*.py. Pylint detects this as a
# cycle during static analysis, but at runtime the imports are resolved correctly.
"""Dependency injection for FastAPI routes.

This module breaks the cyclic import between api/main.py and api/routes/*.py
by providing accessor functions for shared state instead of importing main directly.

Note: These getters are only safe to call after the FastAPI lifespan startup
has completed. In the normal request lifecycle, this is guaranteed. If called
prematurely, a RuntimeError will be raised with a clear message.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.container_manager import ContainerManager
    from core.database import Database


def get_db() -> "Database":
    """Get the database instance.

    Returns:
        Database instance initialized in main.py

    Raises:
        RuntimeError: If called before application startup completes
    """
    from api import main as app_main

    if app_main.db is None:
        raise RuntimeError(
            "Database not initialized. This function should only be called "
            "after the FastAPI application lifespan startup has completed."
        )
    return app_main.db


def get_container_manager() -> "ContainerManager":
    """Get the container manager instance.

    Returns:
        ContainerManager instance initialized in main.py

    Raises:
        RuntimeError: If called before application startup completes
    """
    from api import main as app_main

    if app_main.container_manager is None:
        raise RuntimeError(
            "ContainerManager not initialized. This function should only be called "
            "after the FastAPI application lifespan startup has completed."
        )
    return app_main.container_manager
