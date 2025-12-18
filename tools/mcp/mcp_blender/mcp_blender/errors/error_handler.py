"""Error handler with severity and category classification.

This module provides a centralized error collection and reporting system
for Blender MCP operations. Errors are classified by severity (critical,
error, warning, info) and category (validation, execution, asset, etc.)
to enable appropriate handling and user feedback.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Severity levels for error classification.

    Attributes:
        CRITICAL: Operation cannot continue; requires immediate attention.
        ERROR: Operation failed but server remains operational.
        WARNING: Operation completed with issues that may affect results.
        INFO: Informational message about operation behavior.
    """

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __lt__(self, other: "ErrorSeverity") -> bool:
        """Compare severity levels for sorting."""
        order = [ErrorSeverity.INFO, ErrorSeverity.WARNING, ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]
        return order.index(self) < order.index(other)


class ErrorCategory(Enum):
    """Categories for error classification.

    Categories help identify the source and type of error for
    appropriate handling and user guidance.
    """

    VALIDATION = "validation"
    EXECUTION = "execution"
    ASSET = "asset"
    RENDER = "render"
    PHYSICS = "physics"
    ANIMATION = "animation"
    PROJECT = "project"
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    CONFIGURATION = "configuration"


@dataclass
class BlenderDiagnostic:
    """A single diagnostic entry with severity, category, and context.

    Attributes:
        severity: How severe the issue is.
        category: What type of issue occurred.
        message: Human-readable description of the issue.
        context: Additional context data for debugging.
        auto_fixable: Whether this issue can be automatically resolved.
        suggestion: Suggested action to resolve the issue.
    """

    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    auto_fixable: bool = False
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert diagnostic to dictionary for serialization."""
        result: Dict[str, Any] = {
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
        }
        if self.context:
            result["context"] = self.context
        if self.auto_fixable:
            result["auto_fixable"] = True
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result


class BlenderErrorHandler:
    """Collects and manages diagnostics during Blender operations.

    This class provides methods to collect errors, warnings, and info
    messages during operation execution, then generate appropriate
    responses based on the collected diagnostics.

    Example:
        handler = BlenderErrorHandler()
        handler.add_warning(
            ErrorCategory.RENDER,
            "Using CPU rendering (GPU not available)"
        )
        handler.add_error(
            ErrorCategory.ASSET,
            "Texture not found: wood.png",
            context={"path": "/app/assets/textures/wood.png"}
        )

        if handler.has_errors():
            return {"success": False, "diagnostics": handler.to_list()}
    """

    def __init__(self) -> None:
        """Initialize empty diagnostics list."""
        self.diagnostics: List[BlenderDiagnostic] = []

    def add_diagnostic(
        self,
        severity: ErrorSeverity,
        category: ErrorCategory,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        auto_fixable: bool = False,
        suggestion: Optional[str] = None,
    ) -> None:
        """Add a diagnostic entry.

        Args:
            severity: Severity level of the diagnostic.
            category: Category of the diagnostic.
            message: Human-readable description.
            context: Additional context data.
            auto_fixable: Whether issue can be auto-resolved.
            suggestion: Suggested fix action.
        """
        diagnostic = BlenderDiagnostic(
            severity=severity,
            category=category,
            message=message,
            context=context or {},
            auto_fixable=auto_fixable,
            suggestion=suggestion,
        )
        self.diagnostics.append(diagnostic)

        # Log based on severity
        log_message = f"[{category.value}] {message}"
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif severity == ErrorSeverity.ERROR:
            logger.error(log_message)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

    def add_critical(
        self,
        category: ErrorCategory,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        """Add a critical error diagnostic."""
        self.add_diagnostic(ErrorSeverity.CRITICAL, category, message, context, suggestion=suggestion)

    def add_error(
        self,
        category: ErrorCategory,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        auto_fixable: bool = False,
        suggestion: Optional[str] = None,
    ) -> None:
        """Add an error diagnostic."""
        self.add_diagnostic(ErrorSeverity.ERROR, category, message, context, auto_fixable=auto_fixable, suggestion=suggestion)

    def add_warning(
        self,
        category: ErrorCategory,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        auto_fixable: bool = False,
        suggestion: Optional[str] = None,
    ) -> None:
        """Add a warning diagnostic."""
        self.add_diagnostic(
            ErrorSeverity.WARNING, category, message, context, auto_fixable=auto_fixable, suggestion=suggestion
        )

    def add_info(
        self,
        category: ErrorCategory,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an info diagnostic."""
        self.add_diagnostic(ErrorSeverity.INFO, category, message, context)

    def has_critical(self) -> bool:
        """Check if any critical errors exist."""
        return any(d.severity == ErrorSeverity.CRITICAL for d in self.diagnostics)

    def has_errors(self) -> bool:
        """Check if any errors (including critical) exist."""
        return any(d.severity in (ErrorSeverity.CRITICAL, ErrorSeverity.ERROR) for d in self.diagnostics)

    def has_warnings(self) -> bool:
        """Check if any warnings exist."""
        return any(d.severity == ErrorSeverity.WARNING for d in self.diagnostics)

    def count_by_severity(self, severity: ErrorSeverity) -> int:
        """Count diagnostics of a specific severity."""
        return len([d for d in self.diagnostics if d.severity == severity])

    def count_auto_fixable(self) -> int:
        """Count diagnostics that can be automatically fixed."""
        return len([d for d in self.diagnostics if d.auto_fixable])

    def get_by_category(self, category: ErrorCategory) -> List[BlenderDiagnostic]:
        """Get all diagnostics of a specific category."""
        return [d for d in self.diagnostics if d.category == category]

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all diagnostics.

        Returns:
            Dictionary with counts by severity and auto-fixable count.
        """
        return {
            "critical": self.count_by_severity(ErrorSeverity.CRITICAL),
            "errors": self.count_by_severity(ErrorSeverity.ERROR),
            "warnings": self.count_by_severity(ErrorSeverity.WARNING),
            "info": self.count_by_severity(ErrorSeverity.INFO),
            "auto_fixable": self.count_auto_fixable(),
            "total": len(self.diagnostics),
        }

    def to_list(self) -> List[Dict[str, Any]]:
        """Convert all diagnostics to list of dictionaries."""
        return [d.to_dict() for d in self.diagnostics]

    def to_response(self, include_summary: bool = True) -> Dict[str, Any]:
        """Generate a response dictionary with diagnostics.

        Args:
            include_summary: Whether to include summary counts.

        Returns:
            Dictionary suitable for API response.
        """
        response = {
            "success": not self.has_errors(),
            "diagnostics": self.to_list(),
        }
        if include_summary:
            response["summary"] = self.get_summary()
        return response

    def merge(self, other: "BlenderErrorHandler") -> None:
        """Merge diagnostics from another handler into this one."""
        self.diagnostics.extend(other.diagnostics)

    def clear(self) -> None:
        """Clear all diagnostics."""
        self.diagnostics.clear()

    def get_highest_severity(self) -> Optional[ErrorSeverity]:
        """Get the highest severity level among all diagnostics."""
        if not self.diagnostics:
            return None
        return max(d.severity for d in self.diagnostics)

    def __len__(self) -> int:
        """Return number of diagnostics."""
        return len(self.diagnostics)

    def __bool__(self) -> bool:
        """Return True if any diagnostics exist."""
        return len(self.diagnostics) > 0
