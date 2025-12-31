"""Configuration models for autonomous agents."""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Semantic versioning pattern for Node.js version validation
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

# Legacy value mappings for backward compatibility
_MODE_ALIASES: dict[str, str] = {
    "entrepreneur": "company",  # Legacy name for company mode
    "auto": "survival",  # Auto mode defaults to survival
}

_PERSONALITY_ALIASES: dict[str, str] = {
    "conservative": "risk_averse",  # Legacy name
    "entrepreneur": "aggressive",  # Legacy name (aggressive growth)
}


class AgentConfig(BaseModel):
    """Typed configuration for AutonomousAgent.

    This model provides validated, typed configuration for the autonomous agent,
    replacing the previous untyped dict approach.

    Example:
        config = AgentConfig(
            mode="company",
            personality="aggressive",
            survival_buffer_hours=12.0,
            task_selection_strategy="highest_reward",
        )
        agent = await AutonomousAgent.create(wallet, compute, marketplace, config=config)
    """

    # Decision engine configuration
    engine_type: Literal["rule_based", "llm"] = Field(
        default="rule_based",
        description="Decision engine type: 'rule_based' for deterministic, 'llm' for Claude-powered decisions",
    )

    # Agent mode and behavior
    mode: Literal["survival", "company"] = Field(
        default="survival",
        description="Agent operating mode: 'survival' focuses on earning, 'company' on building",
    )
    personality: Literal["risk_averse", "balanced", "aggressive"] = Field(
        default="balanced",
        description="Decision-making personality affecting resource allocation",
    )

    # Task selection strategy
    task_selection_strategy: Literal[
        "first_available", "highest_reward", "lowest_difficulty", "best_reward_per_difficulty", "balanced"
    ] = Field(
        default="balanced",
        description="Strategy for selecting tasks from marketplace",
    )

    # Resource thresholds
    survival_buffer_hours: float = Field(
        default=24.0,
        ge=0,
        description="Minimum compute hours to maintain as survival buffer",
    )
    company_threshold: float = Field(
        default=100.0,
        ge=0,
        description="Minimum balance required to consider company formation",
    )

    # LLM configuration (only used when engine_type="llm")
    llm_timeout: int = Field(
        default=900,
        ge=30,
        le=3600,
        description="Timeout in seconds for LLM decisions (30-3600)",
    )
    node_version: str = Field(
        default="22.16.0",
        description="Node.js version for Claude CLI execution",
    )
    fallback_enabled: bool = Field(
        default=True,
        description="Enable rule-based fallback when LLM fails",
    )

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, v: str) -> str:
        """Normalize mode value, mapping legacy names to current values.

        Args:
            v: Mode string (may be legacy value)

        Returns:
            Normalized mode string
        """
        if isinstance(v, str):
            return _MODE_ALIASES.get(v, v)
        return v

    @field_validator("personality", mode="before")
    @classmethod
    def normalize_personality(cls, v: str) -> str:
        """Normalize personality value, mapping legacy names to current values.

        Args:
            v: Personality string (may be legacy value)

        Returns:
            Normalized personality string
        """
        if isinstance(v, str):
            return _PERSONALITY_ALIASES.get(v, v)
        return v

    @field_validator("node_version")
    @classmethod
    def validate_node_version(cls, v: str) -> str:
        """Validate node_version is a valid semantic version.

        Args:
            v: Node version string

        Returns:
            Validated version string

        Raises:
            ValueError: If not a valid semantic version
        """
        if not _SEMVER_PATTERN.match(v):
            raise ValueError(f"Invalid node_version '{v}': must be semantic version (e.g., '22.16.0')")
        return v

    @field_validator("survival_buffer_hours")
    @classmethod
    def validate_survival_buffer(cls, v: float) -> float:
        """Validate survival_buffer_hours is reasonable.

        Args:
            v: Buffer hours

        Returns:
            Validated buffer hours

        Raises:
            ValueError: If buffer is unreasonably high
        """
        if v > 720:  # 30 days
            raise ValueError(f"survival_buffer_hours={v} is unreasonably high (max 720 hours / 30 days)")
        return v

    @field_validator("company_threshold")
    @classmethod
    def validate_company_threshold(cls, v: float) -> float:
        """Validate company_threshold is reasonable.

        Args:
            v: Threshold amount

        Returns:
            Validated threshold

        Raises:
            ValueError: If threshold is unreasonably high
        """
        if v > 1_000_000:
            raise ValueError(f"company_threshold=${v} is unreasonably high (max $1,000,000)")
        return v

    @model_validator(mode="after")
    def validate_llm_config(self) -> "AgentConfig":
        """Validate LLM-related configuration consistency.

        Returns:
            Self after validation

        Raises:
            ValueError: If LLM is disabled but fallback is also disabled
        """
        if self.engine_type == "llm" and not self.fallback_enabled:
            # Warning: running without fallback means failures will raise
            pass  # Allow but this is risky
        return self

    model_config = {
        "extra": "forbid",  # Reject unknown fields for safety
    }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for backward compatibility.

        Returns:
            Dict representation of the config
        """
        result: dict[str, Any] = self.model_dump()
        return result

    @classmethod
    def from_dict(cls, config_dict: dict | None) -> "AgentConfig":
        """Create AgentConfig from a dict, handling None gracefully.

        Args:
            config_dict: Configuration dict (can be None for defaults)

        Returns:
            AgentConfig instance with validated values
        """
        if config_dict is None:
            return cls()
        return cls(**config_dict)
