"""Centralized logging configuration for sleeper detection package.

This module provides:
1. Consistent logging setup across all modules
2. Optional structured JSON logging for machine parsing
3. Environment variable configuration

Usage:
    from sleeper_agents.utils.logging_config import get_logger, setup_logging

    # Get a logger for your module
    logger = get_logger(__name__)

    # Or setup logging with custom configuration
    setup_logging(level="DEBUG", json_format=True)
"""

from datetime import datetime, timezone
import json
import logging
import os
import sys
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """Console formatter with optional color support."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        """Initialize formatter.

        Args:
            use_colors: Whether to use ANSI colors
        """
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console.

        Args:
            record: Log record to format

        Returns:
            Formatted log string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname

        if self.use_colors:
            color = self.COLORS.get(level, "")
            level_str = f"{color}{level:<8}{self.RESET}"
        else:
            level_str = f"{level:<8}"

        message = record.getMessage()

        # Format: timestamp - level - logger - message
        formatted = f"{timestamp} - {level_str} - {record.name} - {message}"

        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def setup_logging(
    level: Optional[str] = None,
    json_format: bool = False,
    log_file: Optional[str] = None,
) -> None:
    """Configure logging for the sleeper detection package.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to LOG_LEVEL env var or INFO.
        json_format: Use JSON format for structured logging.
                     Defaults to LOG_JSON env var or False.
        log_file: Optional file path to write logs to.
                  Defaults to LOG_FILE env var or None.
    """
    # Get configuration from environment or arguments
    log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    use_json = json_format or os.getenv("LOG_JSON", "").lower() == "true"
    file_path = log_file or os.getenv("LOG_FILE")

    # Get the root logger for sleeper_agents
    root_logger = logging.getLogger("sleeper_agents")
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))

    if use_json:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ConsoleFormatter())

    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if file_path:
        file_handler = logging.FileHandler(file_path)
        file_handler.setLevel(getattr(logging, log_level, logging.INFO))
        # Always use JSON format for file logs
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # Prevent propagation to root logger
    root_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    # Ensure the logger is under sleeper_agents namespace
    if not name.startswith("sleeper_agents"):
        name = f"sleeper_agents.{name}"

    logger = logging.getLogger(name)

    # If no handlers are configured, set up default logging
    root_logger = logging.getLogger("sleeper_agents")
    if not root_logger.handlers:
        setup_logging()

    return logger


# Default setup when module is imported
_default_setup_done = False


def _ensure_default_setup() -> None:
    """Ensure default logging is configured."""
    global _default_setup_done
    if not _default_setup_done:
        root_logger = logging.getLogger("sleeper_agents")
        if not root_logger.handlers:
            setup_logging()
        _default_setup_done = True
