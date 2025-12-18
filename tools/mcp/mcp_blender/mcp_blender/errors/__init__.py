"""Error handling module for Blender MCP operations.

This module provides a structured error handling system with severity levels,
error categories, and diagnostic collection. It enables consistent error
reporting and facilitates debugging across all Blender operations.

Example usage:
    handler = BlenderErrorHandler()
    handler.add_error(
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.RENDER,
        message="Render failed: out of memory",
        context={"samples": 4096, "resolution": [3840, 2160]}
    )

    if handler.has_critical():
        return handler.to_response()
"""

from .error_handler import (
    BlenderDiagnostic,
    BlenderErrorHandler,
    ErrorCategory,
    ErrorSeverity,
)

__all__ = [
    "BlenderDiagnostic",
    "BlenderErrorHandler",
    "ErrorCategory",
    "ErrorSeverity",
]
