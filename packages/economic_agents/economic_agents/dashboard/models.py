"""Pydantic models for dashboard API responses."""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AgentStatusResponse(BaseModel):
    """Agent status information."""

    agent_id: str
    balance: float
    compute_hours_remaining: float
    current_cycle: int = 0
    mode: str  # "survival", "entrepreneur", "auto"
    current_activity: str  # "task_work", "company_work", "idle"
    company_exists: bool
    company_id: str | None = None
    last_updated: datetime


class DecisionResponse(BaseModel):
    """Decision information."""

    id: str
    timestamp: datetime
    decision_type: str
    reasoning: str
    confidence: float
    outcome: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # LLM-specific fields
    engine_type: str | None = None  # "llm" or "rule_based"
    execution_time_seconds: float | None = None
    fallback_used: bool | None = None
    validation_passed: bool | None = None
    raw_response: str | None = None  # Full Claude response


class ResourceStatusResponse(BaseModel):
    """Resource status and history."""

    current_balance: float
    compute_hours_remaining: float
    total_earnings: float
    total_expenses: float
    net_profit: float
    recent_transactions: List[Dict[str, Any]]
    balance_trend: List[float]  # Last N snapshots
    compute_trend: List[float]  # Last N snapshots


class CompanyResponse(BaseModel):
    """Company information."""

    company_id: str
    name: str
    stage: str
    capital: float
    funding_status: str
    team_size: int
    products_count: int
    created_at: datetime
    business_plan_exists: bool
    mission: str


class SubAgentResponse(BaseModel):
    """Sub-agent information."""

    agent_id: str
    role: str
    status: str
    created_at: datetime
    tasks_completed: int


class MetricsResponse(BaseModel):
    """Performance metrics."""

    overall_health_score: float
    financial_health: float
    operational_health: float
    growth_trajectory: float
    risk_level: str
    warnings: List[str]
    recommendations: List[str]
    alignment_score: float | None = None
    anomaly_count: int = 0


class UpdateMessage(BaseModel):
    """WebSocket update message."""

    type: str  # "status", "decision", "transaction", "metric", "company"
    timestamp: datetime
    data: Dict[str, Any]


class AgentStartRequest(BaseModel):
    """Request to start an agent."""

    mode: str = Field(
        default="survival",
        description="Agent mode: 'survival' (no company) or 'company' (form company)",
    )
    max_cycles: int = Field(default=50, ge=1, le=1000, description="Maximum cycles to run")
    initial_balance: float = Field(default=100.0, ge=0.0, description="Starting balance in dollars")
    initial_compute_hours: float = Field(default=100.0, ge=0.0, description="Starting compute hours available")
    compute_cost_per_hour: float = Field(default=0.0, ge=0.0, description="Cost per compute hour")
    engine_type: str = Field(
        default="rule_based",
        description="Decision engine: 'rule_based' (fast, deterministic) or 'llm' (Claude-powered, autonomous)",
    )
    llm_timeout: int = Field(
        default=120,
        ge=30,
        le=900,
        description="Timeout for LLM decisions in seconds (only used if engine_type='llm')",
    )


class AgentStartResponse(BaseModel):
    """Response from starting an agent."""

    status: str
    agent_id: str
    mode: str
    max_cycles: int
    initial_balance: float


class AgentStopResponse(BaseModel):
    """Response from stopping an agent."""

    status: str
    cycles_completed: int = 0
    final_balance: float = 0.0
    compute_remaining: float = 0.0
    tasks_completed: int = 0
    company_formed: bool = False


class AgentControlStatusResponse(BaseModel):
    """Current agent control status."""

    is_running: bool
    cycle_count: int = 0
    max_cycles: int = 0
    config: Dict[str, Any] = Field(default_factory=dict)
    agent_id: str | None = None
    balance: float | None = None
    compute_hours: float | None = None
    has_company: bool | None = None
    tasks_completed: int | None = None


class LLMDecisionResponse(BaseModel):
    """Detailed LLM decision information."""

    decision_id: str
    timestamp: datetime
    agent_type: str
    state_snapshot: Dict[str, Any]
    prompt: str
    raw_response: str
    parsed_decision: Dict[str, Any]
    validation_passed: bool
    execution_time_seconds: float
    fallback_used: bool
