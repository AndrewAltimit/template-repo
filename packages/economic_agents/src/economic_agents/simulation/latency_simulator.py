"""Latency simulation for realistic API response times."""

import asyncio
from datetime import datetime, time as dt_time
import random
import time
from typing import Optional


class LatencySimulator:
    """Simulates realistic network latency and processing delays.

    Implements variable delays based on:
    - Operation complexity (simple vs. complex operations)
    - Time of day (business hours are slower)
    - Random jitter to prevent pattern detection
    - Occasional timeouts for realism
    """

    def __init__(
        self,
        base_latency_ms: tuple[float, float] = (50.0, 500.0),
        complex_processing_s: tuple[float, float] = (3.0, 30.0),
        business_hours_multiplier: float = 1.5,
        timeout_probability: float = 0.02,
        seed: Optional[int] = None,
    ):
        """Initialize latency simulator.

        Args:
            base_latency_ms: Range for basic API response latency in milliseconds
            complex_processing_s: Range for complex operations in seconds
            business_hours_multiplier: Slowdown factor during business hours (9am-5pm PST)
            timeout_probability: Probability of timeout (504 error) on complex ops
            seed: Random seed for reproducibility
        """
        self.base_latency_ms = base_latency_ms
        self.complex_processing_s = complex_processing_s
        self.business_hours_multiplier = business_hours_multiplier
        self.timeout_probability = timeout_probability
        self.rng = random.Random(seed)

    def _is_business_hours(self) -> bool:
        """Check if current time is during business hours (9am-5pm PST).

        Returns:
            True if during business hours, False otherwise
        """
        now = datetime.now()
        # Business hours: 9am-5pm
        business_start = dt_time(9, 0)
        business_end = dt_time(17, 0)
        return business_start <= now.time() <= business_end

    def simulate_base_latency(self) -> None:
        """Simulate basic API response latency (50-500ms).

        This adds realistic network delay with jitter to prevent
        agents from detecting deterministic patterns.
        """
        latency = self.rng.uniform(*self.base_latency_ms) / 1000.0  # Convert to seconds

        # Apply business hours slowdown
        if self._is_business_hours():
            latency *= self.business_hours_multiplier

        time.sleep(latency)

    async def simulate_base_latency_async(self) -> None:
        """Async version of base latency simulation.

        Use this in async contexts to avoid blocking the event loop.
        """
        latency = self.rng.uniform(*self.base_latency_ms) / 1000.0

        if self._is_business_hours():
            latency *= self.business_hours_multiplier

        await asyncio.sleep(latency)

    def simulate_complex_processing(self, timeout_enabled: bool = True) -> bool:
        """Simulate complex operation processing (3-30 seconds).

        Args:
            timeout_enabled: Whether to simulate occasional timeouts

        Returns:
            True if operation completed, False if timed out

        Raises:
            TimeoutError: If timeout occurs and timeout_enabled is True
        """
        # Check for timeout
        if timeout_enabled and self.rng.random() < self.timeout_probability:
            # Simulate partial processing before timeout
            partial_delay = self.rng.uniform(self.complex_processing_s[0], self.complex_processing_s[1] * 0.5)
            time.sleep(partial_delay)
            raise TimeoutError("Operation timed out (504)")

        # Normal processing delay
        processing_time = self.rng.uniform(*self.complex_processing_s)

        # Apply business hours slowdown
        if self._is_business_hours():
            processing_time *= self.business_hours_multiplier

        time.sleep(processing_time)
        return True

    async def simulate_complex_processing_async(self, timeout_enabled: bool = True) -> bool:
        """Async version of complex processing simulation.

        Args:
            timeout_enabled: Whether to simulate occasional timeouts

        Returns:
            True if operation completed, False if timed out

        Raises:
            asyncio.TimeoutError: If timeout occurs and timeout_enabled is True
        """
        if timeout_enabled and self.rng.random() < self.timeout_probability:
            partial_delay = self.rng.uniform(self.complex_processing_s[0], self.complex_processing_s[1] * 0.5)
            await asyncio.sleep(partial_delay)
            raise asyncio.TimeoutError("Operation timed out (504)")

        processing_time = self.rng.uniform(*self.complex_processing_s)

        if self._is_business_hours():
            processing_time *= self.business_hours_multiplier

        await asyncio.sleep(processing_time)
        return True

    def simulate_review_delay(self, min_hours: float = 24.0, max_hours: float = 168.0) -> float:
        """Simulate investor/reviewer response delay (1-7 days).

        This is for operations that don't complete immediately but return
        a "pending" status. The return value indicates when to expect a response.

        Args:
            min_hours: Minimum delay in hours (default: 24 = 1 day)
            max_hours: Maximum delay in hours (default: 168 = 7 days)

        Returns:
            Delay in hours until response is ready
        """
        return self.rng.uniform(min_hours, max_hours)

    def get_jittered_delay(self, base_seconds: float, jitter_percent: float = 0.2) -> float:
        """Get a delay with random jitter applied.

        Args:
            base_seconds: Base delay in seconds
            jitter_percent: Percentage of base to use for jitter (0.0-1.0)

        Returns:
            Delay in seconds with jitter applied
        """
        jitter = base_seconds * jitter_percent
        return base_seconds + self.rng.uniform(-jitter, jitter)
