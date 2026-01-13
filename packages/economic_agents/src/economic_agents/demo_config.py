"""Configuration for demo scripts with documented presets.

This module provides typed configuration for running demo agents, externalizing
magic numbers that were previously hardcoded in run_demo.py.

The configuration values represent meaningful thresholds:
- SURVIVAL_INITIAL_BALANCE (100.0): Minimal starting capital forcing task-focused gameplay
- COMPANY_INITIAL_BALANCE (50000.0): Substantial capital enabling company formation
- SURVIVAL_COMPANY_THRESHOLD (50000.0): Unreachably high to prevent accidental company formation
- COMPANY_FORMATION_THRESHOLD (150.0): Low threshold allowing quick company formation
- SURVIVAL_BUFFER_HOURS (20.0): ~1 day buffer before compute resources are critical
- INITIAL_COMPUTE_HOURS (100.0): 4+ days of operation at typical usage rates
"""

from enum import Enum
import os
from typing import Optional

from pydantic import BaseModel, Field


class DemoMode(str, Enum):
    """Demo operating modes."""

    SURVIVAL = "survival"
    COMPANY = "company"


class DemoPreset(BaseModel):
    """Preset configuration values for a demo mode.

    Each preset represents a coherent set of values designed to produce
    specific agent behaviors during demos.

    Attributes:
        initial_balance: Starting wallet balance in dollars.
            - Survival: Low (100.0) - forces reliance on task completion
            - Company: High (50000.0) - enables immediate company formation
        company_threshold: Minimum balance to consider forming a company.
            - Survival: Very high (50000.0) - effectively disables company formation
            - Company: Low (150.0) - allows quick formation with starting capital
        description: Human-readable explanation of the preset's purpose.
    """

    initial_balance: float = Field(description="Starting wallet balance in dollars")
    company_threshold: float = Field(description="Minimum balance to consider forming a company")
    description: str = Field(description="Human-readable explanation of this preset")


# Pre-defined demo presets with documented reasoning
DEMO_PRESETS: dict[DemoMode, DemoPreset] = {
    DemoMode.SURVIVAL: DemoPreset(
        initial_balance=100.0,
        company_threshold=50000.0,
        description=(
            "Survival mode: Agent starts with minimal capital ($100) and must "
            "complete tasks to survive. Company threshold is set extremely high "
            "($50,000) to prevent company formation, keeping focus on task work."
        ),
    ),
    DemoMode.COMPANY: DemoPreset(
        initial_balance=50000.0,
        company_threshold=150.0,
        description=(
            "Company mode: Agent starts with substantial capital ($50,000) enabling "
            "company formation. Low threshold ($150) allows quick transition to "
            "company operations, demonstrating the full agent lifecycle."
        ),
    ),
}


class DemoConfig(BaseModel):
    """Configuration for running demo agents.

    This class centralizes all demo configuration values, replacing scattered
    magic numbers with documented, validated settings. Values can be loaded
    from environment variables for flexibility.

    Example:
        # Use a preset
        config = DemoConfig.for_mode(DemoMode.SURVIVAL)

        # Override from environment
        config = DemoConfig.from_env()

        # Custom configuration
        config = DemoConfig(
            mode=DemoMode.COMPANY,
            initial_balance=25000.0,
            company_threshold=500.0,
        )
    """

    mode: DemoMode = Field(default=DemoMode.SURVIVAL, description="Demo operating mode")

    # Resource settings with documented defaults
    initial_balance: float = Field(
        default=100.0,
        ge=0,
        description=("Starting wallet balance in dollars. Survival: 100.0 (minimal), Company: 50000.0 (substantial)"),
    )
    company_threshold: float = Field(
        default=50000.0,
        ge=0,
        description=("Minimum balance to consider forming a company. Set high to prevent formation in survival mode."),
    )
    survival_buffer_hours: float = Field(
        default=20.0,
        ge=0,
        le=720,
        description=("Hours of compute to maintain as emergency buffer. 20 hours provides roughly one day of safety margin."),
    )
    initial_compute_hours: float = Field(
        default=100.0,
        ge=0,
        description=("Starting compute hours available. 100 hours allows 4+ days of typical operation."),
    )
    compute_cost_per_hour: float = Field(
        default=0.0,
        ge=0,
        description=("Cost per compute hour in dollars. 0.0 for free compute in demos."),
    )
    marketplace_seed: Optional[int] = Field(
        default=42,
        description=("Random seed for marketplace task generation. Fixed seed ensures reproducible demo behavior."),
    )

    # Execution settings
    max_cycles: int = Field(default=50, ge=1, le=10000, description="Maximum number of agent cycles to run")
    cycle_delay_seconds: float = Field(
        default=0.5,
        ge=0,
        le=60,
        description=("Delay between cycles in seconds. 0.5s makes updates visible in dashboard."),
    )

    @classmethod
    def for_mode(cls, mode: DemoMode) -> "DemoConfig":
        """Create configuration for a specific demo mode.

        Uses the preset values for the given mode while keeping other
        settings at their defaults.

        Args:
            mode: Demo mode to configure for

        Returns:
            DemoConfig with preset values applied

        Example:
            config = DemoConfig.for_mode(DemoMode.SURVIVAL)
            print(config.initial_balance)  # 100.0
        """
        preset = DEMO_PRESETS[mode]
        return cls(
            mode=mode,
            initial_balance=preset.initial_balance,
            company_threshold=preset.company_threshold,
        )

    @classmethod
    def from_env(cls, mode: Optional[DemoMode] = None) -> "DemoConfig":
        """Create configuration from environment variables.

        Environment variables (all optional):
            DEMO_MODE: "survival" or "company" (default: survival)
            DEMO_INITIAL_BALANCE: Starting balance (overrides mode preset)
            DEMO_COMPANY_THRESHOLD: Company formation threshold
            DEMO_SURVIVAL_BUFFER_HOURS: Compute buffer hours
            DEMO_INITIAL_COMPUTE_HOURS: Starting compute hours
            DEMO_COMPUTE_COST_PER_HOUR: Cost per compute hour
            DEMO_MARKETPLACE_SEED: Random seed (omit for random)
            DEMO_MAX_CYCLES: Maximum cycles to run
            DEMO_CYCLE_DELAY: Delay between cycles in seconds

        Args:
            mode: Override mode (ignores DEMO_MODE env var if provided)

        Returns:
            DemoConfig with environment values applied

        Example:
            # Run with: DEMO_MODE=company DEMO_MAX_CYCLES=100 python run_demo.py
            config = DemoConfig.from_env()
        """
        # Determine mode
        if mode is None:
            mode_str = os.getenv("DEMO_MODE", "survival").lower()
            mode = DemoMode(mode_str)

        # Start with mode preset
        preset = DEMO_PRESETS[mode]
        initial_balance = preset.initial_balance
        company_threshold = preset.company_threshold

        # Override with environment variables if present
        if env_balance := os.getenv("DEMO_INITIAL_BALANCE"):
            initial_balance = float(env_balance)
        if env_threshold := os.getenv("DEMO_COMPANY_THRESHOLD"):
            company_threshold = float(env_threshold)

        # Parse optional environment variables
        survival_buffer = float(os.getenv("DEMO_SURVIVAL_BUFFER_HOURS", "20.0"))
        initial_compute = float(os.getenv("DEMO_INITIAL_COMPUTE_HOURS", "100.0"))
        compute_cost = float(os.getenv("DEMO_COMPUTE_COST_PER_HOUR", "0.0"))
        max_cycles = int(os.getenv("DEMO_MAX_CYCLES", "50"))
        cycle_delay = float(os.getenv("DEMO_CYCLE_DELAY", "0.5"))

        # Marketplace seed (None for random if not specified)
        seed_str = os.getenv("DEMO_MARKETPLACE_SEED")
        marketplace_seed = int(seed_str) if seed_str is not None else 42

        return cls(
            mode=mode,
            initial_balance=initial_balance,
            company_threshold=company_threshold,
            survival_buffer_hours=survival_buffer,
            initial_compute_hours=initial_compute,
            compute_cost_per_hour=compute_cost,
            marketplace_seed=marketplace_seed,
            max_cycles=max_cycles,
            cycle_delay_seconds=cycle_delay,
        )

    def get_preset_description(self) -> str:
        """Get the description for the current mode's preset.

        Returns:
            Human-readable description of the preset
        """
        return DEMO_PRESETS[self.mode].description
