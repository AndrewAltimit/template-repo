"""Configuration for API backend selection.

Supports swapping between mock implementations and real API services.
"""

from enum import Enum
import os
from typing import Optional

from pydantic import BaseModel


class BackendMode(str, Enum):
    """Backend implementation mode."""

    MOCK = "mock"  # Direct mock implementations (no network)
    API = "api"  # API microservices (network-based)


class APIConfig(BaseModel):
    """API service configuration."""

    wallet_api_url: str = "http://localhost:8001"
    compute_api_url: str = "http://localhost:8002"
    marketplace_api_url: str = "http://localhost:8003"
    investor_api_url: str = "http://localhost:8004"


class BackendConfig(BaseModel):
    """Backend configuration for resource providers."""

    mode: BackendMode = BackendMode.MOCK
    api_config: Optional[APIConfig] = None
    api_key: Optional[str] = None

    # Mock configuration (when mode = MOCK)
    initial_balance: float = 100.0
    initial_compute_hours: float = 48.0
    compute_cost_per_hour: float = 0.0
    marketplace_seed: Optional[int] = None

    @classmethod
    def from_env(cls) -> "BackendConfig":
        """Create configuration from environment variables.

        Environment variables:
            BACKEND_MODE: "mock" or "api"
            WALLET_API_URL: Wallet API URL (default: http://localhost:8001)
            COMPUTE_API_URL: Compute API URL (default: http://localhost:8002)
            MARKETPLACE_API_URL: Marketplace API URL (default: http://localhost:8003)
            INVESTOR_API_URL: Investor API URL (default: http://localhost:8004)
            API_KEY: API key for authentication (required for API mode)
            INITIAL_BALANCE: Initial wallet balance for mock mode
            INITIAL_COMPUTE_HOURS: Initial compute hours for mock mode
            COMPUTE_COST_PER_HOUR: Cost per compute hour for mock mode
            MARKETPLACE_SEED: Random seed for marketplace in mock mode

        Returns:
            Backend configuration
        """
        mode = BackendMode(os.getenv("BACKEND_MODE", "mock"))

        api_config = None
        if mode == BackendMode.API:
            api_config = APIConfig(
                wallet_api_url=os.getenv("WALLET_API_URL", "http://localhost:8001"),
                compute_api_url=os.getenv("COMPUTE_API_URL", "http://localhost:8002"),
                marketplace_api_url=os.getenv("MARKETPLACE_API_URL", "http://localhost:8003"),
                investor_api_url=os.getenv("INVESTOR_API_URL", "http://localhost:8004"),
            )

        marketplace_seed_str = os.getenv("MARKETPLACE_SEED")
        marketplace_seed = int(marketplace_seed_str) if marketplace_seed_str is not None else None

        return cls(
            mode=mode,
            api_config=api_config,
            api_key=os.getenv("API_KEY"),
            initial_balance=float(os.getenv("INITIAL_BALANCE", "100.0")),
            initial_compute_hours=float(os.getenv("INITIAL_COMPUTE_HOURS", "48.0")),
            compute_cost_per_hour=float(os.getenv("COMPUTE_COST_PER_HOUR", "0.0")),
            marketplace_seed=marketplace_seed,
        )

    def validate_api_mode(self):
        """Validate configuration for API mode.

        Raises:
            ValueError: If API mode is selected but required config is missing
        """
        if self.mode == BackendMode.API:
            if not self.api_config:
                raise ValueError("API mode requires api_config to be set")
            if not self.api_key:
                raise ValueError("API mode requires api_key to be set")


# Global default configuration
default_config = BackendConfig()
