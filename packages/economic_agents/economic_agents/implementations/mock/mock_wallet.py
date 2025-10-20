"""Mock wallet implementation for simulation."""

import uuid
from datetime import datetime
from typing import List

from economic_agents.interfaces.wallet import Transaction, WalletInterface


class MockWallet(WalletInterface):
    """Mock wallet with in-memory balance tracking."""

    def __init__(self, initial_balance: float = 0.0, address: str | None = None):
        """Initialize mock wallet.

        Args:
            initial_balance: Starting balance
            address: Wallet address (generated if not provided)
        """
        self.balance = initial_balance
        self.address = address or f"mock_wallet_{uuid.uuid4().hex[:8]}"
        self.transactions: List[Transaction] = []

    def get_balance(self) -> float:
        """Returns current wallet balance."""
        return self.balance

    def send_payment(self, to_address: str, amount: float, memo: str = "") -> Transaction:
        """Sends payment to specified address."""
        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        if amount > self.balance:
            raise ValueError(f"Insufficient balance: {self.balance} < {amount}")

        # Deduct from balance
        self.balance -= amount

        # Create transaction record
        tx = Transaction(
            tx_id=str(uuid.uuid4()),
            from_address=self.address,
            to_address=to_address,
            amount=amount,
            timestamp=datetime.now(),
            status="confirmed",
            memo=memo,
        )

        self.transactions.append(tx)
        return tx

    def receive_payment(self, from_address: str, amount: float, memo: str = "") -> Transaction:
        """Receives payment (helper method for mock).

        Not part of the interface but useful for testing.
        """
        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        # Add to balance
        self.balance += amount

        # Create transaction record
        tx = Transaction(
            tx_id=str(uuid.uuid4()),
            from_address=from_address,
            to_address=self.address,
            amount=amount,
            timestamp=datetime.now(),
            status="confirmed",
            memo=memo,
        )

        self.transactions.append(tx)
        return tx

    def get_address(self) -> str:
        """Returns wallet's receiving address."""
        return self.address

    def get_transaction_history(self, limit: int = 100) -> List[Transaction]:
        """Returns recent transactions."""
        return self.transactions[-limit:]
