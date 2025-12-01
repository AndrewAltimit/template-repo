"""Wallet API client.

Provides the same interface as MockWallet but uses REST API.
"""

from datetime import datetime
import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)


class WalletAPIClient:
    """Client for Wallet API service.

    Implements the same interface as MockWallet for seamless swapping.
    """

    def __init__(self, api_url: str, api_key: str, initial_balance: float = 100.0):
        """Initialize wallet API client.

        Args:
            api_url: Base URL of Wallet API (e.g., http://localhost:8001)
            api_key: API key for authentication
            initial_balance: Initial balance (only used if wallet doesn't exist)
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"X-API-Key": api_key}

        # Initialize wallet on server if needed
        try:
            response = httpx.get(f"{self.api_url}/balance", headers=self.headers)
            if response.status_code == 200:
                # Wallet exists, nothing to do
                logger.debug("Wallet already initialized")
        except httpx.ConnectError:
            # Server not available - will fail on first use
            logger.debug("Wallet API server not available, initialization deferred")
        except Exception:
            # Try to initialize
            try:
                httpx.post(
                    f"{self.api_url}/initialize",
                    headers=self.headers,
                    params={"initial_balance": initial_balance},
                )
            except Exception as e:
                logger.debug("Wallet API initialization deferred: %s", e)

    @property
    def balance(self) -> float:
        """Get current balance.

        Returns:
            Current balance

        Raises:
            ValueError: If API call fails
        """
        try:
            response = httpx.get(f"{self.api_url}/balance", headers=self.headers)
            response.raise_for_status()
            return float(response.json()["balance"])
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to get balance: {e}") from e

    @property
    def transactions(self) -> List[dict]:
        """Get transaction history.

        Returns:
            List of transactions

        Raises:
            ValueError: If API call fails
        """
        try:
            response = httpx.get(f"{self.api_url}/transactions", headers=self.headers)
            response.raise_for_status()
            data = response.json()

            # Convert to MockWallet format
            return [
                {
                    "timestamp": datetime.fromisoformat(tx["timestamp"]),
                    "type": tx["type"],
                    "amount": tx["amount"],
                    "balance_after": tx["balance_after"],
                    "purpose": tx["purpose"],
                }
                for tx in data["transactions"]
            ]
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to get transactions: {e}") from e

    def deposit(self, amount: float, purpose: str = "deposit"):
        """Deposit funds.

        Args:
            amount: Amount to deposit
            purpose: Purpose of deposit

        Raises:
            ValueError: If amount invalid or API call fails
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        try:
            response = httpx.post(
                f"{self.api_url}/transact",
                headers=self.headers,
                json={"amount": amount, "purpose": purpose},
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to deposit: {e}") from e

    def withdraw(self, amount: float, purpose: str = "withdrawal"):
        """Withdraw funds.

        Args:
            amount: Amount to withdraw
            purpose: Purpose of withdrawal

        Raises:
            ValueError: If insufficient funds or API call fails
        """
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        try:
            response = httpx.post(
                f"{self.api_url}/transact",
                headers=self.headers,
                json={"amount": -amount, "purpose": purpose},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise ValueError(f"Insufficient funds: {e.response.json()['message']}") from e
            raise ValueError(f"Failed to withdraw: {e}") from e

    def __repr__(self) -> str:
        """String representation."""
        return f"WalletAPIClient(balance={self.balance:.2f}, api_url={self.api_url})"
