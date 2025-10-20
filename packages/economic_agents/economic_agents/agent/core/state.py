"""Agent state management."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentState:
    """Represents the current state of an autonomous agent."""

    # Resources
    balance: float = 0.0
    compute_hours_remaining: float = 0.0

    # Status
    mode: str = "survival"  # "survival", "entrepreneur", "auto"
    is_active: bool = True
    cycles_completed: int = 0

    # History
    total_earned: float = 0.0
    total_spent: float = 0.0
    tasks_completed: int = 0
    tasks_failed: int = 0

    # Company (if exists)
    company_id: str | None = None
    has_company: bool = False

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_cycle_at: datetime = field(default_factory=datetime.now)

    # Metrics
    survival_buffer_hours: float = 24.0  # Minimum hours to maintain

    def update_balance(self, amount: float):
        """Update balance and track earnings/spending."""
        if amount > 0:
            self.total_earned += amount
        else:
            self.total_spent += abs(amount)
        self.balance += amount

    def is_survival_at_risk(self) -> bool:
        """Check if agent is at risk of running out of compute."""
        return self.compute_hours_remaining < self.survival_buffer_hours

    def has_surplus_capital(self, threshold: float) -> bool:
        """Check if agent has surplus capital above threshold."""
        return self.balance > threshold

    def to_dict(self) -> dict:
        """Convert state to dictionary for logging."""
        return {
            "balance": self.balance,
            "compute_hours_remaining": self.compute_hours_remaining,
            "mode": self.mode,
            "is_active": self.is_active,
            "cycles_completed": self.cycles_completed,
            "total_earned": self.total_earned,
            "total_spent": self.total_spent,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "has_company": self.has_company,
            "company_id": self.company_id,
        }
