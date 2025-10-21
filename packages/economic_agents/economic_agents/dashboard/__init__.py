"""Dashboard backend for economic agents monitoring."""

from economic_agents.dashboard.app import app
from economic_agents.dashboard.dependencies import dashboard_state, get_dashboard_state
from economic_agents.dashboard.routers.websocket import broadcast_update, get_connection_manager

__all__ = [
    "app",
    "dashboard_state",
    "get_dashboard_state",
    "broadcast_update",
    "get_connection_manager",
]
