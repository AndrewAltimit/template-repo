"""Base validator class and validation result structures.

This module provides the foundational classes for all Blender MCP validators.
Validators inherit from BaseValidator and implement domain-specific validation
logic while maintaining consistent error reporting.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ValidationResult:
    """Result of a validation operation.

    Attributes:
        valid: Whether validation passed.
        errors: List of error messages.
        warnings: List of warning messages.
        sanitized_value: Optionally sanitized/corrected value.
    """

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_value: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        result = {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }
        if self.sanitized_value is not None:
            result["sanitized_value"] = self.sanitized_value
        return result

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another validation result into this one."""
        return ValidationResult(
            valid=self.valid and other.valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )


class BaseValidator(ABC):
    """Base class for all validators.

    Subclasses implement domain-specific validation logic while
    inheriting common utilities and consistent error handling.
    """

    def __init__(self) -> None:
        """Initialize validator state."""
        self._errors: List[str] = []
        self._warnings: List[str] = []

    def reset(self) -> None:
        """Clear accumulated errors and warnings."""
        self._errors = []
        self._warnings = []

    def add_error(self, message: str) -> None:
        """Add a validation error."""
        self._errors.append(message)

    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self._warnings.append(message)

    @property
    def is_valid(self) -> bool:
        """Check if validation has passed (no errors)."""
        return len(self._errors) == 0

    def get_result(self, sanitized_value: Optional[Any] = None) -> ValidationResult:
        """Get validation result with current errors and warnings."""
        return ValidationResult(
            valid=self.is_valid,
            errors=list(self._errors),
            warnings=list(self._warnings),
            sanitized_value=sanitized_value,
        )

    def validate_required(self, value: Any, field_name: str) -> bool:
        """Validate that a required field is present.

        Args:
            value: The value to check.
            field_name: Name of the field for error messages.

        Returns:
            True if value is present, False otherwise.
        """
        if value is None:
            self.add_error(f"Required field '{field_name}' is missing")
            return False
        if isinstance(value, str) and not value.strip():
            self.add_error(f"Required field '{field_name}' cannot be empty")
            return False
        return True

    def validate_type(
        self,
        value: Any,
        expected_type: type,
        field_name: str,
    ) -> bool:
        """Validate that a value is of the expected type.

        Args:
            value: The value to check.
            expected_type: Expected Python type.
            field_name: Name of the field for error messages.

        Returns:
            True if type matches, False otherwise.
        """
        if value is not None and not isinstance(value, expected_type):
            self.add_error(f"Field '{field_name}' must be {expected_type.__name__}, got {type(value).__name__}")
            return False
        return True

    def validate_range(
        self,
        value: float,
        min_val: Optional[float],
        max_val: Optional[float],
        field_name: str,
    ) -> bool:
        """Validate that a numeric value is within range.

        Args:
            value: The value to check.
            min_val: Minimum allowed value (inclusive), or None.
            max_val: Maximum allowed value (inclusive), or None.
            field_name: Name of the field for error messages.

        Returns:
            True if in range, False otherwise.
        """
        if min_val is not None and value < min_val:
            self.add_error(f"Field '{field_name}' must be >= {min_val}, got {value}")
            return False
        if max_val is not None and value > max_val:
            self.add_error(f"Field '{field_name}' must be <= {max_val}, got {value}")
            return False
        return True

    def validate_in_set(
        self,
        value: Any,
        valid_values: set,
        field_name: str,
    ) -> bool:
        """Validate that a value is in a set of valid options.

        Args:
            value: The value to check.
            valid_values: Set of valid options.
            field_name: Name of the field for error messages.

        Returns:
            True if value is valid, False otherwise.
        """
        if value not in valid_values:
            valid_list = ", ".join(sorted(str(v) for v in valid_values))
            self.add_error(f"Invalid '{field_name}': '{value}'. Valid options: {valid_list}")
            return False
        return True

    def validate_list_length(
        self,
        value: list,
        min_length: Optional[int],
        max_length: Optional[int],
        field_name: str,
    ) -> bool:
        """Validate list length constraints.

        Args:
            value: The list to check.
            min_length: Minimum length, or None.
            max_length: Maximum length, or None.
            field_name: Name of the field for error messages.

        Returns:
            True if length is valid, False otherwise.
        """
        if min_length is not None and len(value) < min_length:
            self.add_error(f"Field '{field_name}' must have at least {min_length} items, got {len(value)}")
            return False
        if max_length is not None and len(value) > max_length:
            self.add_error(f"Field '{field_name}' must have at most {max_length} items, got {len(value)}")
            return False
        return True

    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate input data.

        Args:
            data: Dictionary of input parameters.

        Returns:
            ValidationResult with errors and warnings.
        """
        pass
