"""Pydantic models for dashboard API responses."""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AgentStatusResponse(BaseModel):
    """Agent status information."""

    agent_id: str
    balance: float
    compute_hours_remaining: float
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
