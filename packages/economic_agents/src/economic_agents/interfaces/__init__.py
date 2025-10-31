"""Abstract interfaces for economic agent interactions."""

from economic_agents.interfaces.compute import ComputeInterface, ComputeStatus
from economic_agents.interfaces.marketplace import MarketplaceInterface, SubmissionStatus, Task, TaskSubmission
from economic_agents.interfaces.wallet import Transaction, WalletInterface

__all__ = [
    "MarketplaceInterface",
    "Task",
    "TaskSubmission",
    "SubmissionStatus",
    "WalletInterface",
    "Transaction",
    "ComputeInterface",
    "ComputeStatus",
]
