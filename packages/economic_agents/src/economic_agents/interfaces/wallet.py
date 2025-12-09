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
