"""API layer for microservice-based architecture.

This module provides REST API services for:
- Wallet: Financial transactions and balance management
- Compute: Resource allocation and time tracking
- Marketplace: Task generation and completion
- Investor Portal: Investment proposals and evaluation

Each service can operate in mock or real mode via configuration.
"""

from economic_agents.api.factory import BackendFactory, create_backends
from economic_agents.api.protocols import (
    ComputeProtocol,
    InvestorPortalProtocol,
    MarketplaceProtocol,
    WalletProtocol,
)

__all__ = [
    "BackendFactory",
    "create_backends",
    "WalletProtocol",
    "ComputeProtocol",
    "MarketplaceProtocol",
    "InvestorPortalProtocol",
]
