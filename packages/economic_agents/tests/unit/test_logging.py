"""Tests for structured logging module."""

import json
import logging

import pytest

from economic_agents.logging import (
    AgentLogger,
    HumanReadableFormatter,
    LogLevel,
    StructuredFormatter,
    configure_logging,
    get_logger,
)


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration after each test."""
    yield
    # Clear handlers from economic_agents logger
    logger = logging.getLogger("economic_agents")
    logger.handlers.clear()
    logger.setLevel(logging.WARNING)


def test_structured_formatter_basic():
    """StructuredFormatter produces valid JSON."""
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    data = json.loads(output)

    assert data["level"] == "INFO"
    assert data["logger"] == "test"
    assert data["message"] == "Test message"
    assert "timestamp" in data


def test_structured_formatter_with_extras():
    """StructuredFormatter includes extra fields."""
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.event_type = "transaction"
    record.agent_id = "agent-123"
    record.context = {"amount": 50.0}

    output = formatter.format(record)
    data = json.loads(output)

    assert data["event_type"] == "transaction"
    assert data["agent_id"] == "agent-123"
    assert data["context"]["amount"] == 50.0


def test_human_readable_formatter_basic():
    """HumanReadableFormatter produces readable output."""
    formatter = HumanReadableFormatter(use_colors=False)
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)

    assert "INFO" in output
    assert "test" in output
    assert "Test message" in output


def test_agent_logger_basic():
    """AgentLogger logs messages with context."""
    logger = AgentLogger("test", agent_id="agent-123")

    # Should not raise
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")


def test_agent_logger_transaction():
    """AgentLogger logs transactions with structured data."""
    logger = AgentLogger("test", agent_id="agent-123")

    # Should not raise
    logger.log_transaction(
        transaction_type="earning",
        amount=50.0,
        balance_after=150.0,
        purpose="Task completion",
    )


def test_agent_logger_task_completed():
    """AgentLogger logs task completions."""
    logger = AgentLogger("test", agent_id="agent-123")

    # Should not raise
    logger.log_task_completed(
        task_id="task-1",
        task_title="Code Review",
        reward=25.0,
        strategy_used="highest_reward",
    )


def test_agent_logger_decision():
    """AgentLogger logs decisions."""
    logger = AgentLogger("test", agent_id="agent-123")

    # Should not raise
    logger.log_decision(
        decision_type="resource_allocation",
        decision="Allocate 2 hours to task work",
        reasoning="Survival at risk",
        confidence=0.9,
    )


def test_agent_logger_cycle():
    """AgentLogger logs cycles."""
    logger = AgentLogger("test", agent_id="agent-123")

    # Should not raise
    logger.log_cycle(
        cycle_number=5,
        balance=100.0,
        compute_hours=20.0,
        tasks_completed=3,
    )


def test_configure_logging_human():
    """configure_logging sets up human-readable output."""
    configure_logging(level="DEBUG", structured=False)

    logger = logging.getLogger("economic_agents")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0].formatter, HumanReadableFormatter)


def test_configure_logging_structured():
    """configure_logging sets up JSON output."""
    configure_logging(level="INFO", structured=True)

    logger = logging.getLogger("economic_agents")
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0].formatter, StructuredFormatter)


def test_configure_logging_with_enum():
    """configure_logging accepts LogLevel enum."""
    configure_logging(level=LogLevel.WARNING)

    logger = logging.getLogger("economic_agents")
    assert logger.level == logging.WARNING


def test_get_logger():
    """get_logger creates AgentLogger instances."""
    logger = get_logger("test_component", agent_id="agent-456")

    assert isinstance(logger, AgentLogger)
    assert logger.agent_id == "agent-456"


def test_log_level_enum():
    """LogLevel enum has correct values."""
    assert LogLevel.DEBUG.value == "DEBUG"
    assert LogLevel.INFO.value == "INFO"
    assert LogLevel.WARNING.value == "WARNING"
    assert LogLevel.ERROR.value == "ERROR"
    assert LogLevel.CRITICAL.value == "CRITICAL"
