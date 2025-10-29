"""Custom exceptions for board module."""


class BoardError(Exception):
    """Base exception for board-related errors."""

    pass


class BoardNotFoundError(BoardError):
    """Raised when a GitHub Project board is not found."""

    def __init__(self, project_number: int, owner: str):
        """
        Initialize BoardNotFoundError.

        Args:
            project_number: The project number that wasn't found
            owner: The owner (user or organization) of the project
        """
        self.project_number = project_number
        self.owner = owner
        super().__init__(f"Project #{project_number} not found for owner '{owner}'")


class GraphQLError(BoardError):
    """Raised when GraphQL API request fails."""

    def __init__(self, message: str, status_code: int | None = None, errors: list | None = None):
        """
        Initialize GraphQLError.

        Args:
            message: Error message
            status_code: HTTP status code if available
            errors: List of GraphQL error objects
        """
        self.status_code = status_code
        self.errors = errors or []
        error_details = f" (HTTP {status_code})" if status_code else ""
        super().__init__(f"GraphQL error{error_details}: {message}")


class RateLimitError(BoardError):
    """Raised when GitHub API rate limit is exceeded."""

    def __init__(self, reset_at: str | None = None, remaining: int = 0):
        """
        Initialize RateLimitError.

        Args:
            reset_at: ISO 8601 timestamp when rate limit resets
            remaining: Number of API points remaining
        """
        self.reset_at = reset_at
        self.remaining = remaining
        reset_msg = f" Resets at {reset_at}" if reset_at else ""
        super().__init__(f"Rate limit exceeded. {remaining} points remaining.{reset_msg}")


class ClaimError(BoardError):
    """Raised when claim operation fails."""

    pass


class DependencyError(BoardError):
    """Raised when dependency graph operation fails."""

    pass


class ValidationError(BoardError):
    """Raised when input validation fails."""

    pass
