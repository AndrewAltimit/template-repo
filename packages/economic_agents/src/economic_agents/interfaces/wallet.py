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
    def get_balance(self) -> float:
        """Returns current wallet balance."""
        pass

    @abstractmethod
    def send_payment(self, to_address: str, amount: float, memo: str = "") -> Transaction:
        """Sends payment to specified address."""
        pass

    @abstractmethod
    def get_address(self) -> str:
        """Returns wallet's receiving address."""
        pass

    @abstractmethod
    def get_transaction_history(self, limit: int = 100) -> List[Transaction]:
        """Returns recent transactions."""
        pass
