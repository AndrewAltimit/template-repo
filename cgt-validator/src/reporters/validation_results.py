"""Classes for storing and managing validation results."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class Severity(Enum):
    """Severity levels for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Base class for validation issues."""

    code: str
    message: str
    location: str
    severity: Severity
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "message": self.message,
            "location": self.location,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
        }


class ValidationError(ValidationIssue):
    """Validation error - must be fixed."""

    def __init__(self, code: str, message: str, location: str, **kwargs):
        super().__init__(code, message, location, Severity.ERROR, **kwargs)


class ValidationWarning(ValidationIssue):
    """Validation warning - should be reviewed."""

    def __init__(self, code: str, message: str, location: str, **kwargs):
        super().__init__(code, message, location, Severity.WARNING, **kwargs)


class ValidationInfo(ValidationIssue):
    """Validation info - informational only."""

    def __init__(self, code: str, message: str, location: str, **kwargs):
        super().__init__(code, message, location, Severity.INFO, **kwargs)


class ValidationResults:
    """Container for all validation results."""

    def __init__(self, state: str, year: int):
        self.state = state
        self.year = year
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationWarning] = []
        self.info: List[ValidationInfo] = []

    def add_error(
        self, code: str, message: str, location: str, severity: Severity = Severity.ERROR
    ):  # pylint: disable=unused-argument
        """Add an error to the results."""
        self.errors.append(ValidationError(code, message, location))

    def add_warning(
        self, code: str, message: str, location: str, severity: Severity = Severity.WARNING
    ):  # pylint: disable=unused-argument
        """Add a warning to the results."""
        self.warnings.append(ValidationWarning(code, message, location))

    def add_info(
        self, code: str, message: str, location: str, severity: Severity = Severity.INFO
    ):  # pylint: disable=unused-argument
        """Add an info message to the results."""
        self.info.append(ValidationInfo(code, message, location))

    def add_issue(self, issue: ValidationIssue):
        """Add a validation issue based on its severity."""
        if issue.severity == Severity.ERROR:
            if isinstance(issue, ValidationError):
                self.errors.append(issue)
            else:
                self.errors.append(ValidationError(issue.code, issue.message, issue.location))
        elif issue.severity == Severity.WARNING:
            if isinstance(issue, ValidationWarning):
                self.warnings.append(issue)
            else:
                self.warnings.append(ValidationWarning(issue.code, issue.message, issue.location))
        else:
            if isinstance(issue, ValidationInfo):
                self.info.append(issue)
            else:
                self.info.append(ValidationInfo(issue.code, issue.message, issue.location))

    def merge(self, other: "ValidationResults"):
        """Merge another ValidationResults into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)

    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    def get_summary(self) -> Dict:
        """Get a summary of the validation results."""
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()

        return {
            "state": self.state,
            "year": self.year,
            "valid": self.is_valid(),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "info_count": len(self.info),
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
        }

    def get_issues_by_location(self) -> Dict[str, List[ValidationIssue]]:
        """Group issues by location."""
        issues_by_location: Dict[str, List[ValidationIssue]] = {}
        all_issues = self.errors + self.warnings + self.info

        for issue in all_issues:
            if issue.location not in issues_by_location:
                issues_by_location[issue.location] = []
            issues_by_location[issue.location].append(issue)

        return issues_by_location

    def get_issues_by_severity(self) -> Dict[Severity, List[ValidationIssue]]:
        """Group issues by severity."""
        return {
            Severity.ERROR: list(self.errors),  # type: ignore[arg-type]
            Severity.WARNING: list(self.warnings),  # type: ignore[arg-type]
            Severity.INFO: list(self.info),  # type: ignore[arg-type]
        }

    def to_dict(self) -> Dict:
        """Convert results to dictionary format."""
        return {
            "summary": self.get_summary(),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "info": [i.to_dict() for i in self.info],
        }

    def __str__(self) -> str:
        """String representation of results."""
        summary = self.get_summary()
        return (
            f"ValidationResults(state={self.state}, year={self.year}, "
            f"valid={summary['valid']}, errors={summary['error_count']}, "
            f"warnings={summary['warning_count']}, info={summary['info_count']})"
        )
