"""Custom exceptions for economic agents framework."""


class EconomicAgentError(Exception):
    """Base exception for all economic agent errors."""

    pass


class InsufficientCapitalError(EconomicAgentError):
    """Raised when operation requires more capital than available."""

    def __init__(self, required: float, available: float, operation: str = "operation"):
        """Initialize error with capital details.

        Args:
            required: Amount of capital required
            available: Amount of capital available
            operation: Description of the operation
        """
        self.required = required
        self.available = available
        self.operation = operation
        super().__init__(f"Insufficient capital for {operation}: need ${required:,.2f}, have ${available:,.2f}")


class CompanyBankruptError(EconomicAgentError):
    """Raised when company runs out of capital."""

    def __init__(self, company_name: str, deficit: float):
        """Initialize error with bankruptcy details.

        Args:
            company_name: Name of the bankrupt company
            deficit: Amount by which company is in debt
        """
        self.company_name = company_name
        self.deficit = deficit
        super().__init__(f"Company '{company_name}' has gone bankrupt with deficit of ${deficit:,.2f}")


class InvalidStageTransitionError(EconomicAgentError):
    """Raised when attempting invalid company stage transition."""

    def __init__(self, current_stage: str, target_stage: str):
        """Initialize error with stage transition details.

        Args:
            current_stage: Current company stage
            target_stage: Attempted target stage
        """
        self.current_stage = current_stage
        self.target_stage = target_stage
        super().__init__(f"Invalid stage transition from '{current_stage}' to '{target_stage}'")


class CompanyNotFoundError(EconomicAgentError):
    """Raised when company not found in registry."""

    def __init__(self, company_id: str, available_ids: list | None = None):
        """Initialize error with company details.

        Args:
            company_id: ID of company that was not found
            available_ids: List of available company IDs (optional)
        """
        self.company_id = company_id
        self.available_ids = available_ids or []
        message = f"Company '{company_id}' not found in registry"
        if available_ids:
            message += f". Available companies: {', '.join(available_ids[:5])}"
            if len(available_ids) > 5:
                message += f" (and {len(available_ids) - 5} more)"
        super().__init__(message)


class InsufficientInvestorCapitalError(EconomicAgentError):
    """Raised when investor lacks capital for investment."""

    def __init__(self, investor_name: str, required: float, available: float):
        """Initialize error with investor capital details.

        Args:
            investor_name: Name of the investor
            required: Amount required for investment
            available: Amount available to investor
        """
        self.investor_name = investor_name
        self.required = required
        self.available = available
        super().__init__(
            f"Investor '{investor_name}' has insufficient capital: " f"need ${required:,.2f}, have ${available:,.2f}"
        )
