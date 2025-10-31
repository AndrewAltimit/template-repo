"""Mock wallet implementation for simulation."""

import uuid
from datetime import datetime
from typing import List, Optional

from economic_agents.interfaces.wallet import Transaction, WalletInterface
from economic_agents.simulation.latency_simulator import LatencySimulator


class MockWallet(WalletInterface):
    """Mock wallet with in-memory balance tracking."""

    def __init__(
        self,
        initial_balance: float = 0.0,
        address: Optional[str] = None,
        enable_latency: bool = True,
        seed: Optional[int] = None,
    ):
        """Initialize mock wallet.

        Args:
            initial_balance: Starting balance
            address: Wallet address (generated if not provided)
            enable_latency: Enable realistic latency simulation
            seed: Random seed for latency simulation
        """
        self.balance = initial_balance
        self.address = address or f"mock_wallet_{uuid.uuid4().hex[:8]}"
        self._transactions: List[Transaction] = []  # Original Transaction objects
        self._api_transactions: List[dict] = []  # Simplified dicts for API
        self.enable_latency = enable_latency

        # Initialize latency simulator
        self.latency_sim = LatencySimulator(seed=seed) if enable_latency else None

    @property
    def transactions(self):
        """Return API-compatible transactions.

        Returns list of dict transactions for API compatibility.
        """
        return self._api_transactions

    async def get_balance(self) -> float:
        """Returns current wallet balance."""
        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

        return self.balance

    async def send_payment(self, to_address: str, amount: float, memo: str = "") -> Transaction:
        """Sends payment to specified address."""
        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

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

        self._transactions.append(tx)
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

        self._transactions.append(tx)
        return tx

    async def get_address(self) -> str:
        """Returns wallet's receiving address."""
        return self.address

    async def get_transaction_history(self, limit: int = 100) -> List[Transaction]:
        """Returns recent transactions."""
        return self._transactions[-limit:]

    async def deposit(self, amount: float, purpose: str = "") -> None:
        """Deposit funds into wallet (convenience method for API).

        Args:
            amount: Amount to deposit
            purpose: Purpose/memo for the transaction
        """
        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        # Add to balance
        self.balance += amount

        # Create transaction record in simplified format for API
        tx_record = {
            "timestamp": datetime.now().isoformat(),
            "type": "earning",
            "amount": amount,
            "balance_after": self.balance,
            "purpose": purpose,
        }

        # Store as dict for API compatibility
        self._api_transactions.append(tx_record)

    async def withdraw(self, amount: float, purpose: str = "") -> None:
        """Withdraw funds from wallet (convenience method for API).

        Args:
            amount: Amount to withdraw
            purpose: Purpose/memo for the transaction

        Raises:
            ValueError: If amount is invalid or insufficient balance
        """
        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        if amount > self.balance:
            raise ValueError(f"Insufficient balance: {self.balance} < {amount}")

        # Deduct from balance
        self.balance -= amount

        # Create transaction record in simplified format for API
        tx_record = {
            "timestamp": datetime.now().isoformat(),
            "type": "expense",
            "amount": -amount,  # Negative for withdrawal
            "balance_after": self.balance,
            "purpose": purpose,
        }

        # Store as dict for API compatibility
        self._api_transactions.append(tx_record)
