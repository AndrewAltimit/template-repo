"""Configuration models for autonomous agents."""

from typing import Any, Literal

from pydantic import BaseModel, Field


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
        ge=0,
        description="Timeout in seconds for LLM decisions",
    )
    node_version: str = Field(
        default="22.16.0",
        description="Node.js version for Claude CLI execution",
    )
    fallback_enabled: bool = Field(
        default=True,
        description="Enable rule-based fallback when LLM fails",
    )

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
