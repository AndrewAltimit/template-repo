"""Tests for event-driven monitoring system."""

from datetime import datetime

import pytest

from economic_agents.monitoring.events import (
    AgentEvent,
    EventBus,
    EventPublisher,
    EventType,
    get_event_bus,
    reset_event_bus,
)


@pytest.fixture(autouse=True)
def reset_global_bus():
    """Reset global event bus after each test."""
    yield
    reset_event_bus()


class TestEventType:
    """Tests for EventType enum."""

    def test_event_type_values(self):
        """EventType has expected string values."""
        assert EventType.AGENT_INITIALIZED.value == "agent.initialized"
        assert EventType.TASK_COMPLETED.value == "task.completed"
        assert EventType.TRANSACTION_COMPLETED.value == "transaction.completed"
        assert EventType.COMPANY_FORMED.value == "company.formed"

    def test_event_type_is_string_enum(self):
        """EventType inherits from str for easy serialization."""
        assert isinstance(EventType.TASK_COMPLETED, str)
        assert EventType.TASK_COMPLETED == "task.completed"


class TestAgentEvent:
    """Tests for AgentEvent dataclass."""

    def test_event_creation_minimal(self):
        """AgentEvent can be created with just event_type."""
        event = AgentEvent(event_type=EventType.AGENT_INITIALIZED)
        assert event.event_type == EventType.AGENT_INITIALIZED
        assert event.agent_id == ""
        assert event.data == {}
        assert isinstance(event.timestamp, datetime)

    def test_event_creation_full(self):
        """AgentEvent can be created with all fields."""
        timestamp = datetime.now()
        event = AgentEvent(
            event_type=EventType.TASK_COMPLETED,
            timestamp=timestamp,
            agent_id="agent-123",
            data={"task_id": "task-1", "reward": 50.0},
        )
        assert event.event_type == EventType.TASK_COMPLETED
        assert event.timestamp == timestamp
        assert event.agent_id == "agent-123"
        assert event.data["task_id"] == "task-1"
        assert event.data["reward"] == 50.0

    def test_event_to_dict(self):
        """AgentEvent.to_dict produces correct structure."""
        event = AgentEvent(
            event_type=EventType.BALANCE_CHANGED,
            agent_id="agent-456",
            data={"old_balance": 100.0, "new_balance": 150.0},
        )
        result = event.to_dict()

        assert result["event_type"] == "balance.changed"
        assert result["agent_id"] == "agent-456"
        assert result["data"]["old_balance"] == 100.0
        assert result["data"]["new_balance"] == 150.0
        assert "timestamp" in result


class TestEventBus:
    """Tests for EventBus pub/sub system."""

    def test_subscribe_and_publish(self):
        """EventBus delivers events to subscribers."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.TASK_COMPLETED, handler)
        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED, agent_id="agent-1"))

        assert len(received_events) == 1
        assert received_events[0].agent_id == "agent-1"

    def test_multiple_subscribers(self):
        """EventBus delivers to multiple subscribers."""
        bus = EventBus()
        results = {"handler1": [], "handler2": []}

        def handler1(event: AgentEvent):
            results["handler1"].append(event)

        def handler2(event: AgentEvent):
            results["handler2"].append(event)

        bus.subscribe(EventType.TASK_COMPLETED, handler1)
        bus.subscribe(EventType.TASK_COMPLETED, handler2)
        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))

        assert len(results["handler1"]) == 1
        assert len(results["handler2"]) == 1

    def test_event_filtering_by_type(self):
        """EventBus only delivers events of subscribed type."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.TASK_COMPLETED, handler)

        # This should be received
        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))
        # This should NOT be received
        bus.publish(AgentEvent(event_type=EventType.TASK_FAILED))

        assert len(received_events) == 1
        assert received_events[0].event_type == EventType.TASK_COMPLETED

    def test_subscribe_all(self):
        """subscribe_all receives all event types."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe_all(handler)

        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))
        bus.publish(AgentEvent(event_type=EventType.TASK_FAILED))
        bus.publish(AgentEvent(event_type=EventType.BALANCE_CHANGED))

        assert len(received_events) == 3

    def test_unsubscribe(self):
        """unsubscribe removes handler from specific event type."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.TASK_COMPLETED, handler)
        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))
        assert len(received_events) == 1

        bus.unsubscribe(EventType.TASK_COMPLETED, handler)
        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))
        assert len(received_events) == 1  # No new events

    def test_unsubscribe_all(self):
        """unsubscribe_all removes global handler."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe_all(handler)
        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))
        assert len(received_events) == 1

        bus.unsubscribe_all(handler)
        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))
        assert len(received_events) == 1  # No new events

    def test_clear(self):
        """clear removes all subscriptions."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.TASK_COMPLETED, handler)
        bus.subscribe_all(handler)

        bus.clear()

        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))
        assert len(received_events) == 0

    def test_handler_exception_doesnt_stop_others(self):
        """Handler exceptions don't prevent other handlers from running."""
        bus = EventBus()
        results = []

        def bad_handler(event: AgentEvent):
            raise ValueError("Handler error")

        def good_handler(event: AgentEvent):
            results.append(event)

        bus.subscribe(EventType.TASK_COMPLETED, bad_handler)
        bus.subscribe(EventType.TASK_COMPLETED, good_handler)

        # Should not raise, and good_handler should still run
        bus.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))
        assert len(results) == 1


class TestEventPublisher:
    """Tests for EventPublisher mixin."""

    def test_publisher_without_bus(self):
        """EventPublisher works without event bus (no-op)."""
        publisher = EventPublisher()
        # Should not raise
        publisher._publish(EventType.TASK_COMPLETED, {"task_id": "task-1"})

    def test_publisher_with_bus(self):
        """EventPublisher publishes to configured bus."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.TASK_COMPLETED, handler)

        publisher = EventPublisher(event_bus=bus, agent_id="agent-123")
        publisher._publish(EventType.TASK_COMPLETED, {"task_id": "task-1"})

        assert len(received_events) == 1
        assert received_events[0].agent_id == "agent-123"
        assert received_events[0].data["task_id"] == "task-1"

    def test_set_event_bus(self):
        """set_event_bus allows configuring bus after init."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.TASK_COMPLETED, handler)

        publisher = EventPublisher()
        publisher.set_event_bus(bus)
        publisher._publish(EventType.TASK_COMPLETED)

        assert len(received_events) == 1

    def test_publish_transaction(self):
        """publish_transaction emits TRANSACTION_COMPLETED event."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.TRANSACTION_COMPLETED, handler)

        publisher = EventPublisher(event_bus=bus, agent_id="agent-1")
        publisher.publish_transaction(
            transaction_type="earning",
            amount=50.0,
            balance_after=150.0,
            purpose="Task reward",
        )

        assert len(received_events) == 1
        assert received_events[0].data["transaction_type"] == "earning"
        assert received_events[0].data["amount"] == 50.0
        assert received_events[0].data["balance_after"] == 150.0
        assert received_events[0].data["purpose"] == "Task reward"

    def test_publish_task_completed(self):
        """publish_task_completed emits TASK_COMPLETED event."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.TASK_COMPLETED, handler)

        publisher = EventPublisher(event_bus=bus, agent_id="agent-1")
        publisher.publish_task_completed(
            task_id="task-1",
            task_title="Code Review",
            reward=25.0,
        )

        assert len(received_events) == 1
        assert received_events[0].data["task_id"] == "task-1"
        assert received_events[0].data["task_title"] == "Code Review"
        assert received_events[0].data["reward"] == 25.0

    def test_publish_task_failed(self):
        """publish_task_failed emits TASK_FAILED event."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.TASK_FAILED, handler)

        publisher = EventPublisher(event_bus=bus, agent_id="agent-1")
        publisher.publish_task_failed(
            task_id="task-2",
            task_title="Bug Fix",
            reason="Timeout exceeded",
        )

        assert len(received_events) == 1
        assert received_events[0].data["task_id"] == "task-2"
        assert received_events[0].data["reason"] == "Timeout exceeded"

    def test_publish_decision(self):
        """publish_decision emits DECISION_MADE event."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.DECISION_MADE, handler)

        publisher = EventPublisher(event_bus=bus, agent_id="agent-1")
        publisher.publish_decision(
            decision_type="resource_allocation",
            decision="Allocate 2 hours to task work",
            reasoning="Survival at risk",
            confidence=0.9,
        )

        assert len(received_events) == 1
        assert received_events[0].data["decision_type"] == "resource_allocation"
        assert received_events[0].data["confidence"] == 0.9

    def test_publish_cycle_completed(self):
        """publish_cycle_completed emits AGENT_CYCLE_COMPLETED event."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.AGENT_CYCLE_COMPLETED, handler)

        publisher = EventPublisher(event_bus=bus, agent_id="agent-1")
        publisher.publish_cycle_completed(
            cycle_number=5,
            balance=100.0,
            compute_hours=20.0,
            tasks_completed=3,
        )

        assert len(received_events) == 1
        assert received_events[0].data["cycle"] == 5
        assert received_events[0].data["balance"] == 100.0
        assert received_events[0].data["tasks_completed"] == 3

    def test_publish_company_formed(self):
        """publish_company_formed emits COMPANY_FORMED event."""
        bus = EventBus()
        received_events = []

        def handler(event: AgentEvent):
            received_events.append(event)

        bus.subscribe(EventType.COMPANY_FORMED, handler)

        publisher = EventPublisher(event_bus=bus, agent_id="agent-1")
        publisher.publish_company_formed(
            company_id="company-1",
            company_name="AI Solutions",
            capital=10000.0,
        )

        assert len(received_events) == 1
        assert received_events[0].data["company_id"] == "company-1"
        assert received_events[0].data["company_name"] == "AI Solutions"
        assert received_events[0].data["capital"] == 10000.0


class TestGlobalEventBus:
    """Tests for global event bus singleton."""

    def test_get_event_bus_returns_singleton(self):
        """get_event_bus returns the same instance."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_event_bus_clears_and_creates_new(self):
        """reset_event_bus clears subscriptions and resets singleton."""
        bus1 = get_event_bus()
        received = []

        def handler(event: AgentEvent):
            received.append(event)

        bus1.subscribe(EventType.TASK_COMPLETED, handler)

        reset_event_bus()

        bus2 = get_event_bus()
        assert bus1 is not bus2

        # Old handler should not receive events on new bus
        bus2.publish(AgentEvent(event_type=EventType.TASK_COMPLETED))
        assert len(received) == 0
