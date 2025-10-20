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


class ProductDevelopmentFailure(EconomicAgentError):
    """Raised when product development fails."""

    def __init__(self, product_name: str, reason: str, completion_percentage: float):
        """Initialize error with product failure details.

        Args:
            product_name: Name of the product that failed
            reason: Reason for failure
            completion_percentage: How far the product got before failure
        """
        self.product_name = product_name
        self.reason = reason
        self.completion_percentage = completion_percentage
        super().__init__(f"Product '{product_name}' development failed at {completion_percentage:.1f}% completion: {reason}")


class StageRegressionError(EconomicAgentError):
    """Raised when company regresses to previous stage."""

    def __init__(self, company_name: str, from_stage: str, to_stage: str, reason: str):
        """Initialize error with stage regression details.

        Args:
            company_name: Name of the company
            from_stage: Stage company is regressing from
            to_stage: Stage company is regressing to
            reason: Reason for regression
        """
        self.company_name = company_name
        self.from_stage = from_stage
        self.to_stage = to_stage
        self.reason = reason
        super().__init__(f"Company '{company_name}' regressed from '{from_stage}' to '{to_stage}': {reason}")


class InvestmentRejectionError(EconomicAgentError):
    """Raised when investment proposal is rejected."""

    def __init__(self, company_name: str, investor_name: str, reason: str, evaluation_score: float):
        """Initialize error with investment rejection details.

        Args:
            company_name: Name of the company seeking investment
            investor_name: Name of the investor who rejected
            reason: Reason for rejection
            evaluation_score: Overall evaluation score
        """
        self.company_name = company_name
        self.investor_name = investor_name
        self.reason = reason
        self.evaluation_score = evaluation_score
        super().__init__(
            f"Investment proposal from '{company_name}' rejected by '{investor_name}' "
            f"(score: {evaluation_score:.2f}): {reason}"
        )
