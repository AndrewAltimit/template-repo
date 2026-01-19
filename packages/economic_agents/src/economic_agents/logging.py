"""Structured logging for economic agents.

Provides a consistent logging interface with structured output support.
Uses Python's logging module with optional JSON formatting for machine parsing.
"""

from datetime import datetime, timezone
from enum import Enum
import json
import logging
import sys
from typing import Any


class LogLevel(str, Enum):
    """Log levels for the agent logging system."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured log output.

    Produces machine-parseable JSON logs with consistent structure.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields from the record
        if hasattr(record, "event_type"):
            log_data["event_type"] = record.event_type
        if hasattr(record, "agent_id"):
            log_data["agent_id"] = record.agent_id
        if hasattr(record, "context"):
            log_data["context"] = record.context

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for console output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    def __init__(self, use_colors: bool = True):
        """Initialize formatter.

        Args:
            use_colors: Whether to use ANSI colors (default: True)
        """
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human reading."""
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        level = record.levelname

        if self.use_colors:
            color = self.COLORS.get(level, "")
            reset = self.COLORS["RESET"]
            level_str = f"{color}{level:8s}{reset}"
        else:
            level_str = f"{level:8s}"

        message = record.getMessage()

        # Build context string if present
        context_str = ""
        if hasattr(record, "event_type"):
            context_str += f" [{record.event_type}]"
        if hasattr(record, "agent_id"):
            context_str += f" agent={record.agent_id[:8]}"  # type: ignore[index]

        return f"{timestamp} {level_str} {record.name}{context_str}: {message}"


class AgentLogger:
    """Structured logger for economic agents.

    Provides a convenient interface for logging with automatic context injection.

    Example:
        logger = AgentLogger("my_agent", agent_id="abc123")
        logger.info("Task completed", context={"reward": 50.0, "task_id": "task-1"})
    """

    def __init__(
        self,
        name: str,
        agent_id: str | None = None,
        level: LogLevel | str = LogLevel.INFO,
    ):
        """Initialize agent logger.

        Args:
            name: Logger name (typically module or component name)
            agent_id: Optional agent ID for context
            level: Logging level
        """
        self._logger = logging.getLogger(f"economic_agents.{name}")
        self.agent_id = agent_id

        if isinstance(level, str):
            level = LogLevel(level.upper())
        self._logger.setLevel(getattr(logging, level.value))

    def _log(
        self,
        level: int,
        message: str,
        event_type: str | None = None,
        context: dict[str, Any] | None = None,
        exc_info: bool = False,
    ) -> None:
        """Internal log method with structured data."""
        extra: dict[str, Any] = {}
        if self.agent_id:
            extra["agent_id"] = self.agent_id
        if event_type:
            extra["event_type"] = event_type
        if context:
            extra["context"] = context

        self._logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(
        self,
        message: str,
        event_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, event_type, context)

    def info(
        self,
        message: str,
        event_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log info message."""
        self._log(logging.INFO, message, event_type, context)

    def warning(
        self,
        message: str,
        event_type: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, event_type, context)

    def error(
        self,
        message: str,
        event_type: str | None = None,
        context: dict[str, Any] | None = None,
        exc_info: bool = False,
    ) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, event_type, context, exc_info)

    def critical(
        self,
        message: str,
        event_type: str | None = None,
        context: dict[str, Any] | None = None,
        exc_info: bool = False,
    ) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, event_type, context, exc_info)

    # Event-specific logging methods
    def log_transaction(
        self,
        transaction_type: str,
        amount: float,
        balance_after: float,
        purpose: str = "",
    ) -> None:
        """Log a financial transaction."""
        self.info(
            f"Transaction: {transaction_type} ${amount:.2f}",
            event_type="transaction",
            context={
                "transaction_type": transaction_type,
                "amount": amount,
                "balance_after": balance_after,
                "purpose": purpose,
            },
        )

    def log_task_completed(
        self,
        task_id: str,
        task_title: str,
        reward: float,
        strategy_used: str = "",
    ) -> None:
        """Log task completion."""
        self.info(
            f"Task completed: {task_title}",
            event_type="task_completed",
            context={
                "task_id": task_id,
                "task_title": task_title,
                "reward": reward,
                "strategy": strategy_used,
            },
        )

    def log_decision(
        self,
        decision_type: str,
        decision: str,
        reasoning: str,
        confidence: float,
    ) -> None:
        """Log an agent decision."""
        self.info(
            f"Decision: {decision}",
            event_type="decision",
            context={
                "decision_type": decision_type,
                "reasoning": reasoning,
                "confidence": confidence,
            },
        )

    def log_cycle(
        self,
        cycle_number: int,
        balance: float,
        compute_hours: float,
        tasks_completed: int,
    ) -> None:
        """Log cycle completion."""
        self.debug(
            f"Cycle {cycle_number} completed",
            event_type="cycle_completed",
            context={
                "cycle": cycle_number,
                "balance": balance,
                "compute_hours": compute_hours,
                "tasks_completed": tasks_completed,
            },
        )


def configure_logging(
    level: LogLevel | str = LogLevel.INFO,
    structured: bool = False,
    log_file: str | None = None,
) -> None:
    """Configure the logging system for economic agents.

    Args:
        level: Logging level
        structured: Use JSON structured output (default: human readable)
        log_file: Optional file path for log output

    Example:
        # Development: human-readable console output
        configure_logging(level="DEBUG")

        # Production: structured JSON to file
        configure_logging(level="INFO", structured=True, log_file="/var/log/agent.log")
    """
    if isinstance(level, str):
        level = LogLevel(level.upper())

    root_logger = logging.getLogger("economic_agents")
    root_logger.setLevel(getattr(logging, level.value))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if structured:
        console_handler.setFormatter(StructuredFormatter())
    else:
        use_colors = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        console_handler.setFormatter(HumanReadableFormatter(use_colors=use_colors))
    root_logger.addHandler(console_handler)

    # File handler (always structured)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)


def get_logger(name: str, agent_id: str | None = None) -> AgentLogger:
    """Get or create a logger for a component.

    Args:
        name: Component name
        agent_id: Optional agent ID for context

    Returns:
        AgentLogger instance
    """
    return AgentLogger(name, agent_id)
