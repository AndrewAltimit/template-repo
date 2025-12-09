"""Mock compute provider implementation for simulation."""

from datetime import datetime, timedelta
from typing import Optional

from economic_agents.interfaces.compute import ComputeInterface, ComputeStatus
from economic_agents.simulation.latency_simulator import LatencySimulator


class MockCompute(ComputeInterface):
    """Mock compute provider with time decay simulation."""

    def __init__(
        self,
        initial_hours: float = 24.0,
        cost_per_hour: float = 2.0,
        enable_latency: bool = True,
        seed: Optional[int] = None,
    ):
        """Initialize mock compute provider.

        Args:
            initial_hours: Starting compute hours
            cost_per_hour: Hourly cost rate
            enable_latency: Enable realistic latency simulation
            seed: Random seed for latency simulation
        """
        self.hours_remaining = initial_hours
        self.cost_per_hour = cost_per_hour
        self.balance = initial_hours * cost_per_hour
        self.last_update = datetime.now()
        self.enable_latency = enable_latency

        # Initialize latency simulator
        self.latency_sim = LatencySimulator(seed=seed) if enable_latency else None

    def _update_time_decay(self):
        """Apply time decay since last update."""
        now = datetime.now()
        elapsed = (now - self.last_update).total_seconds() / 3600.0  # Convert to hours

        if elapsed > 0:
            self.hours_remaining = max(0.0, self.hours_remaining - elapsed)
            self.balance = self.hours_remaining * self.cost_per_hour
            self.last_update = now

    async def get_status(self) -> ComputeStatus:
        """Returns current compute status."""
        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

        self._update_time_decay()

        if self.hours_remaining <= 0:
            status = "expired"
        elif self.hours_remaining < 4.0:
            status = "low"
        else:
            status = "active"

        return ComputeStatus(
            hours_remaining=self.hours_remaining,
            cost_per_hour=self.cost_per_hour,
            balance=self.balance,
            expires_at=self.last_update + timedelta(hours=self.hours_remaining),
            status=status,
        )

    async def add_funds(self, amount: float) -> bool:
        """Adds funds to compute account."""
        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

        if amount <= 0:
            return False

        self._update_time_decay()

        additional_hours = amount / self.cost_per_hour
        self.hours_remaining += additional_hours
        self.balance += amount

        return True

    async def get_cost_per_hour(self) -> float:
        """Returns current cost rate per hour."""
        return self.cost_per_hour

    async def consume_time(self, hours: float) -> bool:
        """Consumes compute time."""
        if hours <= 0:
            return False

        self._update_time_decay()

        if hours > self.hours_remaining:
            return False

        self.hours_remaining -= hours

        # Round to 0 if very small to avoid floating point issues
        if self.hours_remaining < 0.0001:
            self.hours_remaining = 0.0

        self.balance = self.hours_remaining * self.cost_per_hour

        return True

    async def allocate_hours(self, hours: float, purpose: str = "") -> None:
        """Allocate compute hours for a task (convenience method for API).

        Args:
            hours: Number of hours to allocate
            purpose: Purpose/description of allocation

        Raises:
            ValueError: If hours is invalid or insufficient hours available
        """
        # Simulate base API latency
        if self.latency_sim:
            await self.latency_sim.simulate_base_latency_async()

        if hours <= 0:
            raise ValueError("Hours must be positive")

        self._update_time_decay()

        if hours > self.hours_remaining:
            raise ValueError(f"Insufficient compute hours: {self.hours_remaining:.2f}h available, {hours:.2f}h requested")

        # Allocate the hours (consume them)
        self.hours_remaining -= hours

        # Round to 0 if very small to avoid floating point issues
        if self.hours_remaining < 0.0001:
            self.hours_remaining = 0.0

        self.balance = self.hours_remaining * self.cost_per_hour

    def tick(self) -> None:
        """Manual time tick for API (applies decay).

        This is a convenience method that forces a time decay update.
        """
        self._update_time_decay()
