"""Shared dependencies and state management for dashboard."""

from typing import Any, Dict

from economic_agents.monitoring import AlignmentMonitor, MetricsCollector, ResourceTracker


class DashboardState:
    """Manages dashboard state and provides access to monitoring components."""

    def __init__(self):
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


# Global dashboard state instance
dashboard_state = DashboardState()


def get_dashboard_state() -> DashboardState:
    """Dependency function to get dashboard state."""
    return dashboard_state
