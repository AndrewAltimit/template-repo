"""Event-driven monitoring system for economic agents.

Provides loose coupling between agent operations and monitoring components
through an event bus pattern.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events that can be published."""

    # Agent lifecycle events
    AGENT_INITIALIZED = "agent.initialized"
    AGENT_CYCLE_STARTED = "agent.cycle.started"
    AGENT_CYCLE_COMPLETED = "agent.cycle.completed"
    AGENT_STOPPED = "agent.stopped"

    # Financial events
    TRANSACTION_COMPLETED = "transaction.completed"
    BALANCE_CHANGED = "balance.changed"

    # Task events
    TASK_CLAIMED = "task.claimed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # Company events
    COMPANY_FORMED = "company.formed"
    COMPANY_STAGE_CHANGED = "company.stage.changed"
    INVESTMENT_SOUGHT = "investment.sought"
    INVESTMENT_RECEIVED = "investment.received"

    # Resource events
    COMPUTE_CONSUMED = "compute.consumed"
    COMPUTE_LOW = "compute.low"

    # Decision events
    DECISION_MADE = "decision.made"
    ALLOCATION_DECIDED = "allocation.decided"


@dataclass
class AgentEvent:
    """Base event structure for agent monitoring.

    All events carry a type, timestamp, and optional data payload.
    """

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    agent_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "data": self.data,
        }


# Type alias for event handlers
EventHandler = Callable[[AgentEvent], None]


class EventBus:
    """Central event bus for agent monitoring.

    Allows components to publish events and subscribe to specific event types.
    Supports synchronous event handling for simplicity.

    Example:
        bus = EventBus()

        # Subscribe to events
        def on_task_completed(event: AgentEvent):
            print(f"Task completed: {event.data}")

        bus.subscribe(EventType.TASK_COMPLETED, on_task_completed)

        # Publish events
        bus.publish(AgentEvent(
            event_type=EventType.TASK_COMPLETED,
            agent_id="agent-123",
            data={"task_id": "task-1", "reward": 50.0}
        ))
    """

    def __init__(self):
        """Initialize event bus."""
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: Type of events to receive
            handler: Callback function to invoke
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all events.

        Args:
            handler: Callback function to invoke for all events
        """
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from a specific event type.

        Args:
            event_type: Type of events
            handler: Handler to remove
        """
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

    def unsubscribe_all(self, handler: EventHandler) -> None:
        """Unsubscribe from all events.

        Args:
            handler: Handler to remove
        """
        self._global_handlers = [h for h in self._global_handlers if h != handler]

    def publish(self, event: AgentEvent) -> None:
        """Publish an event to all subscribed handlers.

        Args:
            event: Event to publish
        """
        # Notify specific handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # Log but don't fail on handler errors
                logger.exception(
                    "Handler %s failed for event %s",
                    getattr(handler, "__name__", handler),
                    event.event_type.value,
                )

        # Notify global handlers
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Global handler %s failed for event %s",
                    getattr(handler, "__name__", handler),
                    event.event_type.value,
                )

    def clear(self) -> None:
        """Clear all subscriptions."""
        self._handlers.clear()
        self._global_handlers.clear()


class EventPublisher:
    """Mixin for classes that publish events.

    Provides convenient methods for publishing common event types.
    """

    def __init__(self, event_bus: EventBus | None = None, agent_id: str = ""):
        """Initialize publisher.

        Args:
            event_bus: Event bus to publish to (optional)
            agent_id: Agent ID for event context
        """
        self._event_bus = event_bus
        self._publisher_agent_id = agent_id

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus for publishing."""
        self._event_bus = event_bus

    def _publish(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        """Publish an event if event bus is configured."""
        if self._event_bus is None:
            return

        event = AgentEvent(
            event_type=event_type,
            agent_id=self._publisher_agent_id,
            data=data or {},
        )
        self._event_bus.publish(event)

    def publish_transaction(
        self,
        transaction_type: str,
        amount: float,
        balance_after: float,
        purpose: str = "",
    ) -> None:
        """Publish a transaction event."""
        self._publish(
            EventType.TRANSACTION_COMPLETED,
            {
                "transaction_type": transaction_type,
                "amount": amount,
                "balance_after": balance_after,
                "purpose": purpose,
            },
        )

    def publish_task_completed(
        self,
        task_id: str,
        task_title: str,
        reward: float,
    ) -> None:
        """Publish task completion event."""
        self._publish(
            EventType.TASK_COMPLETED,
            {
                "task_id": task_id,
                "task_title": task_title,
                "reward": reward,
            },
        )

    def publish_task_failed(
        self,
        task_id: str,
        task_title: str,
        reason: str,
    ) -> None:
        """Publish task failure event."""
        self._publish(
            EventType.TASK_FAILED,
            {
                "task_id": task_id,
                "task_title": task_title,
                "reason": reason,
            },
        )

    def publish_decision(
        self,
        decision_type: str,
        decision: str,
        reasoning: str,
        confidence: float,
    ) -> None:
        """Publish decision event."""
        self._publish(
            EventType.DECISION_MADE,
            {
                "decision_type": decision_type,
                "decision": decision,
                "reasoning": reasoning,
                "confidence": confidence,
            },
        )

    def publish_cycle_completed(
        self,
        cycle_number: int,
        balance: float,
        compute_hours: float,
        tasks_completed: int,
    ) -> None:
        """Publish cycle completion event."""
        self._publish(
            EventType.AGENT_CYCLE_COMPLETED,
            {
                "cycle": cycle_number,
                "balance": balance,
                "compute_hours": compute_hours,
                "tasks_completed": tasks_completed,
            },
        )

    def publish_company_formed(
        self,
        company_id: str,
        company_name: str,
        capital: float,
    ) -> None:
        """Publish company formation event."""
        self._publish(
            EventType.COMPANY_FORMED,
            {
                "company_id": company_id,
                "company_name": company_name,
                "capital": capital,
            },
        )


# Global event bus instance (singleton pattern)
_global_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance.

    Returns:
        Global EventBus instance
    """
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (mainly for testing)."""
    global _global_event_bus
    if _global_event_bus is not None:
        _global_event_bus.clear()
    _global_event_bus = None
