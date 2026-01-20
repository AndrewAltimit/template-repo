"""Protocol definitions for factory return types.

These protocols define the interface contracts for objects returned by BackendFactory.
Using Protocol (structural subtyping) allows both mock implementations and API clients
to satisfy the interface without explicit inheritance.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class WalletProtocol(Protocol):
    """Protocol for wallet implementations.

    Defines the common interface between MockWallet and WalletAPIClient
    that factory consumers can rely on.
    """

    @property
    def balance(self) -> float:
        """Current wallet balance."""
        ...

    @property
    def transactions(self) -> List[Dict[str, Any]]:
        """Transaction history in API-compatible format."""
        ...

    def deposit(self, amount: float, purpose: str = "") -> None:
        """Deposit funds into wallet.

        Args:
            amount: Amount to deposit (must be positive)
            purpose: Description of the deposit

        Raises:
            ValueError: If amount is not positive
        """
        ...

    def withdraw(self, amount: float, purpose: str = "") -> None:
        """Withdraw funds from wallet.

        Args:
            amount: Amount to withdraw (must be positive)
            purpose: Description of the withdrawal

        Raises:
            ValueError: If amount is not positive or insufficient funds
        """
        ...


@runtime_checkable
class ComputeProtocol(Protocol):
    """Protocol for compute implementations.

    Defines the common interface between MockCompute and ComputeAPIClient
    that factory consumers can rely on.
    """

    @property
    def hours_remaining(self) -> float:
        """Remaining compute hours."""
        ...

    @property
    def cost_per_hour(self) -> float:
        """Cost per compute hour."""
        ...

    def allocate_hours(self, hours: float, purpose: str = "") -> None:
        """Allocate compute hours for a task.

        Args:
            hours: Number of hours to allocate (must be positive)
            purpose: Description of the allocation

        Raises:
            ValueError: If hours is not positive or insufficient hours available
        """
        ...

    def tick(self) -> None:
        """Advance time by one cycle (apply decay)."""
        ...


@runtime_checkable
class MarketplaceProtocol(Protocol):
    """Protocol for marketplace implementations.

    Defines the common interface between MockMarketplace and MarketplaceAPIClient
    that factory consumers can rely on.
    """

    def generate_tasks(self, count: int = 5) -> List[Dict[str, Any]]:
        """Generate tasks from marketplace.

        Args:
            count: Number of tasks to generate

        Returns:
            List of task dictionaries with id, difficulty, reward,
            compute_hours_required, and description fields
        """
        ...

    def complete_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Complete a task.

        Args:
            task: Task dictionary with at least 'id' field

        Returns:
            Result dictionary with 'success', 'reward', and 'message' fields
        """
        ...


@runtime_checkable
class InvestorPortalProtocol(Protocol):
    """Protocol for investor portal implementations.

    Defines the interface for InvestorPortalAPIClient.
    In mock mode, investment functionality is built into agents directly,
    so this protocol is only implemented by the API client.
    """

    def submit_proposal(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Submit an investment proposal.

        Args:
            company: Company dictionary with proposal details

        Returns:
            Proposal submission result
        """
        ...

    def get_proposal_status(self, proposal_id: str) -> Dict[str, Any]:
        """Get status of a submitted proposal.

        Args:
            proposal_id: Proposal ID

        Returns:
            Investment decision
        """
        ...

    def list_investors(self) -> List[Dict[str, Any]]:
        """Get list of active investors.

        Returns:
            List of investor information
        """
        ...

    def list_proposals(self) -> List[Dict[str, Any]]:
        """List all proposals submitted by this agent.

        Returns:
            List of proposals
        """
        ...
