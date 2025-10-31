"""Compute interface for managing agent compute resources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ComputeStatus:
    """Status of compute resources."""

    hours_remaining: float
    cost_per_hour: float
    balance: float
    expires_at: datetime
    status: str  # "active", "low", "expired"


class ComputeInterface(ABC):
    """Abstract interface for compute resource management."""

    @abstractmethod
    def get_status(self) -> ComputeStatus:
        """Returns current compute status."""
        pass

    @abstractmethod
    def add_funds(self, amount: float) -> bool:
        """Adds funds to compute account."""
        pass

    @abstractmethod
    def get_cost_per_hour(self) -> float:
        """Returns current cost rate per hour."""
        pass

    @abstractmethod
    def consume_time(self, hours: float) -> bool:
        """Consumes compute time, returns True if successful."""
        pass
