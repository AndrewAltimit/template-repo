"""Wallet interface for financial operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class Transaction:
    """Represents a financial transaction."""

    tx_id: str
    from_address: str
    to_address: str
    amount: float
    timestamp: datetime
    status: str  # "pending", "confirmed", "failed"
    memo: str


class WalletInterface(ABC):
    """Abstract interface for wallet operations."""

    @abstractmethod
    async def get_balance(self) -> float:
        """Returns current wallet balance."""

    @abstractmethod
    async def send_payment(self, to_address: str, amount: float, memo: str = "") -> Transaction:
        """Sends payment to specified address."""

    @abstractmethod
    async def get_address(self) -> str:
        """Returns wallet's receiving address."""

    @abstractmethod
    async def get_transaction_history(self, limit: int = 100) -> List[Transaction]:
        """Returns recent transactions."""

    @abstractmethod
    async def receive_payment(self, from_address: str, amount: float, memo: str = "") -> Transaction:
        """Records incoming payment and updates balance.

        In real implementations, this would be triggered by blockchain events.
        In simulation, this is called directly when tasks are completed.

        Args:
            from_address: Address funds are coming from
            amount: Payment amount (must be positive)
            memo: Optional transaction memo

        Returns:
            Transaction record for the incoming payment

        Raises:
            ValueError: If amount is not positive
        """
