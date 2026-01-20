"""Factory for creating backend implementations.

Supports swapping between mock implementations and API clients based on configuration.
"""

from typing import NamedTuple, Optional, Union

from economic_agents.api.clients.compute_client import ComputeAPIClient
from economic_agents.api.clients.investor_client import InvestorPortalAPIClient
from economic_agents.api.clients.marketplace_client import MarketplaceAPIClient
from economic_agents.api.clients.wallet_client import WalletAPIClient
from economic_agents.api.config import BackendConfig, BackendMode
from economic_agents.implementations.mock import MockCompute, MockMarketplace, MockWallet
from economic_agents.interfaces import ComputeInterface, MarketplaceInterface, WalletInterface


class BackendComponents(NamedTuple):
    """Typed container for backend components returned by the factory.

    Provides named access to each component with proper type annotations.
    """

    wallet: Union[WalletInterface, WalletAPIClient]
    compute: Union[ComputeInterface, ComputeAPIClient]
    marketplace: Union[MarketplaceInterface, MarketplaceAPIClient]
    investor_portal: Optional[InvestorPortalAPIClient]


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

    def create_wallet(self) -> Union[WalletInterface, WalletAPIClient]:
        """Create wallet implementation.

        Returns:
            Wallet instance (MockWallet or WalletAPIClient)

        Raises:
            ValueError: If API mode configuration is invalid
        """
        if self.config.mode == BackendMode.MOCK:
            return MockWallet(initial_balance=self.config.initial_balance)
        # API mode - config is validated in __init__
        assert self.config.api_config is not None
        assert self.config.api_key is not None
        return WalletAPIClient(
            api_url=self.config.api_config.wallet_api_url,
            api_key=self.config.api_key,
            initial_balance=self.config.initial_balance,
        )

    def create_compute(self) -> Union[ComputeInterface, ComputeAPIClient]:
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
        # API mode - config is validated in __init__
        assert self.config.api_config is not None
        assert self.config.api_key is not None
        return ComputeAPIClient(
            api_url=self.config.api_config.compute_api_url,
            api_key=self.config.api_key,
            initial_hours=self.config.initial_compute_hours,
            cost_per_hour=self.config.compute_cost_per_hour,
        )

    def create_marketplace(self) -> Union[MarketplaceInterface, MarketplaceAPIClient]:
        """Create marketplace implementation.

        Returns:
            Marketplace instance (MockMarketplace or MarketplaceAPIClient)

        Raises:
            ValueError: If API mode configuration is invalid
        """
        if self.config.mode == BackendMode.MOCK:
            return MockMarketplace(seed=self.config.marketplace_seed)
        # API mode - config is validated in __init__
        assert self.config.api_config is not None
        assert self.config.api_key is not None
        return MarketplaceAPIClient(
            api_url=self.config.api_config.marketplace_api_url,
            api_key=self.config.api_key,
            seed=self.config.marketplace_seed,
        )

    def create_investor_portal(self) -> Optional[InvestorPortalAPIClient]:
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
        # API mode - config is validated in __init__
        assert self.config.api_config is not None
        assert self.config.api_key is not None
        return InvestorPortalAPIClient(
            api_url=self.config.api_config.investor_api_url,
            api_key=self.config.api_key,
        )

    def create_all(self) -> BackendComponents:
        """Create all backend implementations.

        Returns:
            BackendComponents with wallet, compute, marketplace, and investor_portal

        Raises:
            ValueError: If API mode configuration is invalid
        """
        return BackendComponents(
            wallet=self.create_wallet(),
            compute=self.create_compute(),
            marketplace=self.create_marketplace(),
            investor_portal=self.create_investor_portal(),
        )


def create_backends(config: Optional[BackendConfig] = None) -> BackendComponents:
    """Convenience function to create backends.

    Args:
        config: Backend configuration (defaults to environment-based config)

    Returns:
        BackendComponents with wallet, compute, marketplace, and investor_portal

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

        # Named access (preferred)
        backends = create_backends()
        balance = await backends.wallet.get_balance()
    """
    if config is None:
        config = BackendConfig.from_env()

    factory = BackendFactory(config)
    return factory.create_all()
