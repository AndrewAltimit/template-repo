"""Factory for creating backend implementations.

Supports swapping between mock implementations and API clients based on configuration.
"""

from typing import Tuple

from economic_agents.api.clients.compute_client import ComputeAPIClient
from economic_agents.api.clients.investor_client import InvestorPortalAPIClient
from economic_agents.api.clients.marketplace_client import MarketplaceAPIClient
from economic_agents.api.clients.wallet_client import WalletAPIClient
from economic_agents.api.config import BackendConfig, BackendMode
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet


class BackendFactory:
    """Factory for creating backend resource providers.

    Creates either mock implementations or API clients based on configuration.
    """

    def __init__(self, config: BackendConfig):
        """Initialize factory with configuration.

        Args:
            config: Backend configuration
        """
        self.config = config

        # Validate API mode if selected
        if config.mode == BackendMode.API:
            config.validate_api_mode()

    def create_wallet(self):
        """Create wallet implementation.

        Returns:
            Wallet instance (MockWallet or WalletAPIClient)

        Raises:
            ValueError: If API mode configuration is invalid
        """
        if self.config.mode == BackendMode.MOCK:
            return MockWallet(initial_balance=self.config.initial_balance)
        return WalletAPIClient(
            api_url=self.config.api_config.wallet_api_url,
            api_key=self.config.api_key,
            initial_balance=self.config.initial_balance,
        )

    def create_compute(self):
        """Create compute implementation.

        Returns:
            Compute instance (MockCompute or ComputeAPIClient)

        Raises:
            ValueError: If API mode configuration is invalid
        """
        if self.config.mode == BackendMode.MOCK:
            return MockCompute(
                initial_hours=self.config.initial_compute_hours,
                cost_per_hour=self.config.compute_cost_per_hour,
            )
        return ComputeAPIClient(
            api_url=self.config.api_config.compute_api_url,
            api_key=self.config.api_key,
            initial_hours=self.config.initial_compute_hours,
            cost_per_hour=self.config.compute_cost_per_hour,
        )

    def create_marketplace(self):
        """Create marketplace implementation.

        Returns:
            Marketplace instance (MockMarketplace or MarketplaceAPIClient)

        Raises:
            ValueError: If API mode configuration is invalid
        """
        if self.config.mode == BackendMode.MOCK:
            return MockMarketplace(seed=self.config.marketplace_seed)
        return MarketplaceAPIClient(
            api_url=self.config.api_config.marketplace_api_url,
            api_key=self.config.api_key,
            seed=self.config.marketplace_seed,
        )

    def create_investor_portal(self):
        """Create investor portal client.

        Returns:
            Investor portal instance (InvestorPortalAPIClient or None)

        Note:
            In mock mode, investment functionality is built into the agent/company
            directly, so this returns None. In API mode, returns the API client.

        Raises:
            ValueError: If API mode configuration is invalid
        """
        if self.config.mode == BackendMode.MOCK:
            # In mock mode, investment is handled internally
            return None
        return InvestorPortalAPIClient(
            api_url=self.config.api_config.investor_api_url,
            api_key=self.config.api_key,
        )

    def create_all(self) -> Tuple:
        """Create all backend implementations.

        Returns:
            Tuple of (wallet, compute, marketplace, investor_portal)

        Raises:
            ValueError: If API mode configuration is invalid
        """
        return (
            self.create_wallet(),
            self.create_compute(),
            self.create_marketplace(),
            self.create_investor_portal(),
        )


def create_backends(config: BackendConfig = None) -> Tuple:
    """Convenience function to create backends.

    Args:
        config: Backend configuration (defaults to environment-based config)

    Returns:
        Tuple of (wallet, compute, marketplace, investor_portal)

    Example:
        # Mock mode (default)
        wallet, compute, marketplace, investor = create_backends()

        # API mode
        config = BackendConfig(
            mode=BackendMode.API,
            api_config=APIConfig(),
            api_key="ea_your_api_key_here"
        )
        wallet, compute, marketplace, investor = create_backends(config)
    """
    if config is None:
        config = BackendConfig.from_env()

    factory = BackendFactory(config)
    return factory.create_all()
