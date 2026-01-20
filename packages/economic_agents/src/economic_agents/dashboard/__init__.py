"""Dashboard backend for economic agents monitoring."""

from economic_agents.dashboard.app import app
from economic_agents.dashboard.dependencies import (
    DashboardState,
    create_dashboard_state,
    dashboard_state,
    dashboard_state_override,
    get_dashboard_state,
    get_state_container,
)
from economic_agents.dashboard.routers.websocket import broadcast_update, get_connection_manager

__all__ = [
    "app",
    "DashboardState",
    "create_dashboard_state",
    "dashboard_state",  # Deprecated: use get_dashboard_state() or dashboard_state_override()
    "dashboard_state_override",  # Recommended for tests: context manager for state isolation
    "get_dashboard_state",
    "get_state_container",
    "broadcast_update",
    "get_connection_manager",
]
