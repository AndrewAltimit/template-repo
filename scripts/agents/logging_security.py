#!/usr/bin/env python3
"""
Logging security utilities to prevent secret exposure.
"""

import logging
import re
from typing import List, Pattern


class SecretRedactionFilter(logging.Filter):
    """
    Logging filter that redacts sensitive information from log messages.

    This filter prevents accidental exposure of secrets like tokens,
    passwords, and API keys in log outputs.
    """

    def __init__(self):
        super().__init__()
        self.patterns: List[Pattern] = [
            # GitHub tokens (classic and fine-grained)
            re.compile(r"(ghp_[a-zA-Z0-9]{36,})", re.IGNORECASE),
            re.compile(r"(github_pat_[a-zA-Z0-9_]{36,})", re.IGNORECASE),
            # Generic token patterns
            re.compile(r'(token["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', re.IGNORECASE),
            re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', re.IGNORECASE),
            re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', re.IGNORECASE),
            re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', re.IGNORECASE),
            # Bearer tokens in headers
            re.compile(r"(Bearer\s+)([a-zA-Z0-9\-._~+/]+)", re.IGNORECASE),
            re.compile(r'(Authorization["\']?\s*[:=]\s*["\']?)([^"\'\s]+)', re.IGNORECASE),
            # URLs with embedded credentials
            re.compile(r"(https?://)([^:]+):([^@]+)@", re.IGNORECASE),
            # Environment variable values
            re.compile(r"(GITHUB_TOKEN=)([^\s]+)", re.IGNORECASE),
            re.compile(r"(GH_TOKEN=)([^\s]+)", re.IGNORECASE),
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records to redact sensitive information.

        Args:
            record: The log record to filter

        Returns:
            True (always allows the record through, but with redacted content)
        """
        # Redact message
        if hasattr(record, "msg"):
            record.msg = self._redact_secrets(str(record.msg))

        # Redact arguments
        if hasattr(record, "args") and record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(self._redact_secrets(str(arg)) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: self._redact_secrets(str(v)) for k, v in record.args.items()}

        return True

    def _redact_secrets(self, text: str) -> str:
        """
        Redact secrets from the given text.

        Args:
            text: Text to redact secrets from

        Returns:
            Text with secrets replaced by [REDACTED]
        """
        for pattern in self.patterns:
            if pattern.groups == 0:
                # Simple pattern - replace entire match
                text = pattern.sub("[REDACTED]", text)
            else:
                # Pattern with groups - preserve prefix, redact secret
                def replacer(match):
                    groups = match.groups()
                    if len(groups) >= 2:
                        # Keep prefix (like "token=") and redact the value
                        return groups[0] + "[REDACTED]"
                    else:
                        return "[REDACTED]"

                text = pattern.sub(replacer, text)

        return text


def setup_secure_logging():
    """
    Set up secure logging configuration with secret redaction.

    This should be called early in the application startup to ensure
    all loggers use the secure configuration.
    """
    # Get root logger
    root_logger = logging.getLogger()

    # Add redaction filter to all handlers
    redaction_filter = SecretRedactionFilter()

    for handler in root_logger.handlers:
        handler.addFilter(redaction_filter)

    # Also add to any future handlers by setting on the logger itself
    root_logger.addFilter(redaction_filter)


def get_secure_logger(name: str) -> logging.Logger:
    """
    Get a logger with secret redaction enabled.

    Args:
        name: Logger name

    Returns:
        Logger instance with redaction filter
    """
    logger = logging.getLogger(name)

    # Add redaction filter if not already present
    if not any(isinstance(f, SecretRedactionFilter) for f in logger.filters):
        logger.addFilter(SecretRedactionFilter())

    return logger


def mask_secrets(text: str) -> str:
    """
    Mask secrets in text using the same patterns as the logging filter.

    Args:
        text: Text to mask secrets in

    Returns:
        Text with secrets replaced by [REDACTED]
    """
    redaction_filter = SecretRedactionFilter()
    return redaction_filter._redact_secrets(text)
