"""Shared dependencies and state management for dashboard."""

from typing import Any, Dict, Optional

from economic_agents.monitoring import AlignmentMonitor, MetricsCollector, ResourceTracker


class DashboardState:
    """Manages dashboard state and provides access to monitoring components."""

    def __init__(self) -> None:
        """Initialize dashboard state."""
        self.resource_tracker: ResourceTracker | None = None
        self.metrics_collector: MetricsCollector | None = None
        self.alignment_monitor: AlignmentMonitor | None = None
        self.agent_state: Dict[str, Any] = {}
        self.company_registry: Dict[str, Any] = {}

    def set_resource_tracker(self, tracker: ResourceTracker):
        """Set the resource tracker instance."""
        self.resource_tracker = tracker

    def set_metrics_collector(self, collector: MetricsCollector):
        """Set the metrics collector instance."""
        self.metrics_collector = collector

    def set_alignment_monitor(self, monitor: AlignmentMonitor):
        """Set the alignment monitor instance."""
        self.alignment_monitor = monitor

    def update_agent_state(self, state: Dict[str, Any]):
        """Update agent state information."""
        self.agent_state = state

    def update_company_registry(self, registry: Dict[str, Any]):
        """Update company registry information."""
        self.company_registry = registry

    def get_agent_state(self) -> Dict[str, Any]:
        """Get current agent state."""
        return self.agent_state

    def get_company_registry(self) -> Dict[str, Any]:
        """Get company registry."""
        return self.company_registry

    def reset(self) -> None:
        """Reset all state to initial values.

        Useful for testing to ensure clean state between tests.
        """
        self.resource_tracker = None
        self.metrics_collector = None
        self.alignment_monitor = None
        self.agent_state = {}
        self.company_registry = {}


class DashboardStateContainer:
    """Container for managing the DashboardState singleton with override support.

    This container provides dependency injection support by allowing the
    default state to be overridden for testing or different application contexts.
    """

    def __init__(self) -> None:
        """Initialize the container with a default DashboardState instance."""
        self._default_state = DashboardState()
        self._override_state: Optional[DashboardState] = None

    def get_state(self) -> DashboardState:
        """Get the current DashboardState instance.

        Returns the override state if set, otherwise returns the default state.
        """
        return self._override_state if self._override_state is not None else self._default_state

    def override(self, state: DashboardState) -> None:
        """Override the default state with a custom instance.

        Args:
            state: The DashboardState instance to use instead of the default.
        """
        self._override_state = state

    def reset_override(self) -> None:
        """Remove the override and revert to the default state."""
        self._override_state = None

    def reset(self) -> None:
        """Reset both the override and the default state.

        Useful for testing to ensure completely clean state.
        """
        self._override_state = None
        self._default_state.reset()


# Container for managing DashboardState with DI support
_state_container = DashboardStateContainer()


def get_dashboard_state() -> DashboardState:
    """FastAPI dependency function to get dashboard state.

    This function is designed to be used with FastAPI's Depends() system.
    For non-FastAPI contexts (like run_demo.py), create a new DashboardState
    instance directly or use get_state_container() for advanced control.
    """
    return _state_container.get_state()


def get_state_container() -> DashboardStateContainer:
    """Get the DashboardStateContainer for advanced control.

    This allows tests to override the state instance or reset state between tests.
    Production code should use get_dashboard_state() or create instances directly.
    """
    return _state_container


def create_dashboard_state() -> DashboardState:
    """Factory function to create a new DashboardState instance.

    Use this for creating isolated instances (e.g., in tests or for
    non-web application contexts like run_demo.py).
    """
    return DashboardState()


# Backwards compatibility: provide a module-level reference to the default state.
# DEPRECATED: New code should use get_dashboard_state() or create_dashboard_state().
# This is kept for backwards compatibility with existing imports but will
# return the container's current state, allowing tests to override it.
def _get_dashboard_state_compat() -> DashboardState:
    """Get dashboard state (for backwards compatibility)."""
    return _state_container.get_state()


# Create a lazy property-like access for backwards compatibility
class _DashboardStateProxy:
    """Proxy object that delegates to the container's current state.

    This allows existing code that imports 'dashboard_state' to continue
    working while enabling tests to override the underlying state.
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(_state_container.get_state(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(_state_container.get_state(), name, value)


# DEPRECATED: Use get_dashboard_state() or create_dashboard_state() instead.
# Kept for backwards compatibility with existing code that imports dashboard_state.
dashboard_state = _DashboardStateProxy()
