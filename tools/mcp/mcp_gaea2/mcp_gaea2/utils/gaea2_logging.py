#!/usr/bin/env python3
"""
Comprehensive logging system for Gaea2 MCP
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Color codes for terminal output
COLORS = {
    "DEBUG": "\033[36m",  # Cyan
    "INFO": "\033[32m",  # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m",  # Reset
}


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for terminal output"""

    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if levelname in COLORS:
            record.levelname = f"{COLORS[levelname]}{levelname}{COLORS['RESET']}"

        # Format the message
        formatted = super().format(record)

        # Reset color at end
        return formatted


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, "node_type"):
            log_obj["node_type"] = record.node_type
        if hasattr(record, "node_id"):
            log_obj["node_id"] = record.node_id
        if hasattr(record, "operation"):
            log_obj["operation"] = record.operation
        if hasattr(record, "error_type"):
            log_obj["error_type"] = record.error_type

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


class Gaea2Logger:
    """Enhanced logger for Gaea2 operations"""

    def __init__(self, name: str = "gaea2_mcp", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False

        # Remove existing handlers
        self.logger.handlers.clear()

        # Console handler with color
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Use colored formatter for console
        console_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        console_formatter = ColoredFormatter(console_format, datefmt="%H:%M:%S")
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler with structured logging (optional)
        self.file_handler: Optional[logging.FileHandler] = None

    def enable_file_logging(self, log_dir: str, structured: bool = True):
        """Enable file logging"""
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Create file handler
        log_file = log_path / f"gaea2_mcp_{datetime.now().strftime('%Y%m%d')}.log"
        self.file_handler = logging.FileHandler(log_file)
        self.file_handler.setLevel(logging.DEBUG)

        # Use structured or plain formatter
        formatter: logging.Formatter
        if structured:
            formatter = StructuredFormatter()
        else:
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")

        self.file_handler.setFormatter(formatter)
        self.logger.addHandler(self.file_handler)

    def log_operation(self, operation: str, params: Dict[str, Any], level: int = logging.INFO):
        """Log an operation with parameters"""
        extra = {"operation": operation}
        self.logger.log(level, f"Operation: {operation}", extra=extra)

        if level == logging.DEBUG:
            self.logger.debug(f"Parameters: {json.dumps(params, indent=2)}")

    def log_node_operation(
        self,
        operation: str,
        node_type: str,
        node_id: Optional[int] = None,
        message: Optional[str] = None,
        level: int = logging.INFO,
    ):
        """Log node-specific operation"""
        extra: Dict[str, Any] = {"operation": operation, "node_type": node_type}

        if node_id is not None:
            extra["node_id"] = node_id

        msg = f"[{node_type}] {operation}"
        if message:
            msg += f": {message}"

        self.logger.log(level, msg, extra=extra)

    def log_validation_error(
        self,
        error_type: str,
        node_type: str,
        details: str,
        node_id: Optional[int] = None,
    ):
        """Log validation error"""
        extra: Dict[str, Any] = {"error_type": error_type, "node_type": node_type}

        if node_id is not None:
            extra["node_id"] = node_id

        self.logger.error(f"Validation error [{error_type}] for {node_type}: {details}", extra=extra)

    def log_performance(self, operation: str, duration: float, item_count: int = 0):
        """Log performance metrics"""
        msg = f"Performance: {operation} took {duration:.3f}s"
        if item_count > 0:
            msg += f" for {item_count} items ({duration/item_count*1000:.1f}ms per item)"

        level = logging.INFO
        if duration > 5.0:
            level = logging.WARNING
        elif duration > 10.0:
            level = logging.ERROR

        self.logger.log(level, msg)

    def get_logger(self) -> logging.Logger:
        """Get the underlying logger"""
        return self.logger


# Global logger instance
_global_logger = None


def get_logger(name: Optional[str] = None) -> Gaea2Logger:
    """Get logger instance"""
    global _global_logger

    if _global_logger is None:
        _global_logger = Gaea2Logger(name or "gaea2_mcp")

        # Enable file logging if in production
        import os

        if os.getenv("GAEA2_ENV") == "production":
            log_dir = os.getenv("GAEA2_LOG_DIR", "/var/log/gaea2_mcp")
            _global_logger.enable_file_logging(log_dir)

    return _global_logger


# Decorator for operation logging
def log_operation(operation_name: str):
    """Decorator to log function operations"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger()

            # Log start
            logger.log_operation(operation_name, kwargs, logging.DEBUG)

            # Time the operation
            import time

            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                # Log success
                duration = time.time() - start_time
                logger.log_performance(operation_name, duration)

                return result

            except Exception as e:
                # Log error
                logger.logger.error(f"Operation {operation_name} failed: {str(e)}", exc_info=True)
                raise

        return wrapper

    return decorator
