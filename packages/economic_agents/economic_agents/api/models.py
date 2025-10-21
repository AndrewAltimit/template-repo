"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Wallet API Models


class TransactionRequest(BaseModel):
    """Request to execute a transaction."""

    amount: float = Field(..., description="Transaction amount (positive for deposit, negative for withdrawal)")
    purpose: str = Field(..., description="Purpose/description of the transaction")


class Transaction(BaseModel):
    """Transaction record."""

    timestamp: datetime = Field(default_factory=datetime.now)
    type: str = Field(..., description="Transaction type: earning, expense, transfer")
    amount: float = Field(..., description="Transaction amount")
    balance_after: float = Field(..., description="Balance after transaction")
    purpose: str = Field(..., description="Purpose/description")


class WalletBalance(BaseModel):
    """Wallet balance response."""

    balance: float = Field(..., description="Current balance")
    agent_id: str = Field(..., description="Agent ID")


class TransactionHistory(BaseModel):
    """Transaction history response."""

    transactions: List[Transaction] = Field(default_factory=list)
    total_count: int = Field(..., description="Total number of transactions")


# Compute API Models


class ComputeHours(BaseModel):
    """Compute hours response."""

    hours_remaining: float = Field(..., description="Available compute hours")
    agent_id: str = Field(..., description="Agent ID")


class AllocateRequest(BaseModel):
    """Request to allocate compute hours."""

    hours: float = Field(..., gt=0, description="Hours to allocate")
    purpose: str = Field(..., description="Purpose of allocation")


class AllocationResponse(BaseModel):
    """Response from compute allocation."""

    success: bool = Field(..., description="Whether allocation succeeded")
    hours_allocated: float = Field(..., description="Hours actually allocated")
    hours_remaining: float = Field(..., description="Hours remaining after allocation")
    message: Optional[str] = Field(None, description="Error or status message")


class TickResponse(BaseModel):
    """Response from time tick."""

    success: bool = Field(..., description="Whether tick succeeded")
    hours_decayed: float = Field(..., description="Hours decayed this tick")
    hours_remaining: float = Field(..., description="Hours remaining after decay")


# Marketplace API Models


class Task(BaseModel):
    """Marketplace task."""

    id: str = Field(..., description="Task ID")
    difficulty: float = Field(..., description="Task difficulty (1-10)")
    reward: float = Field(..., description="Task reward amount")
    compute_hours_required: float = Field(..., description="Compute hours needed")
    description: str = Field(..., description="Task description")


class TaskList(BaseModel):
    """List of available tasks."""

    tasks: List[Task] = Field(default_factory=list)
    count: int = Field(..., description="Number of tasks available")


class CompleteTaskRequest(BaseModel):
    """Request to complete a task."""

    agent_id: str = Field(..., description="Agent completing the task")


class CompleteTaskResponse(BaseModel):
    """Response from task completion."""

    success: bool = Field(..., description="Whether task completed successfully")
    reward: float = Field(0.0, description="Reward amount")
    message: Optional[str] = Field(None, description="Error or status message")


# Investor Portal API Models


class InvestmentProposal(BaseModel):
    """Investment proposal submission."""

    company_id: str = Field(..., description="Company ID")
    company_name: str = Field(..., description="Company name")
    stage: str = Field(..., description="Development stage")
    business_plan: Dict[str, Any] = Field(..., description="Business plan details")
    funding_requested: float = Field(..., gt=0, description="Funding amount requested")
    use_of_funds: str = Field(..., description="How funds will be used")
    team_size: int = Field(..., ge=0, description="Number of team members")
    revenue: float = Field(default=0.0, description="Current revenue")
    monthly_burn_rate: float = Field(default=0.0, description="Monthly burn rate")


class ProposalResponse(BaseModel):
    """Response from proposal submission."""

    proposal_id: str = Field(..., description="Proposal ID")
    status: str = Field(..., description="Proposal status")
    message: str = Field(..., description="Status message")


class InvestmentDecision(BaseModel):
    """Investment decision response."""

    proposal_id: str = Field(..., description="Proposal ID")
    approved: bool = Field(..., description="Whether approved")
    investment_amount: float = Field(default=0.0, description="Investment amount")
    investor_name: str = Field(..., description="Investor name")
    conditions: List[str] = Field(default_factory=list, description="Investment conditions")
    feedback: str = Field(..., description="Investor feedback")


class InvestorInfo(BaseModel):
    """Investor information."""

    name: str = Field(..., description="Investor name")
    focus: List[str] = Field(default_factory=list, description="Investment focus areas")
    typical_check_size: float = Field(..., description="Typical investment amount")
    stage_preference: str = Field(..., description="Preferred company stage")


class InvestorList(BaseModel):
    """List of investors."""

    investors: List[InvestorInfo] = Field(default_factory=list)
    count: int = Field(..., description="Number of investors")


# Authentication Models


class APIKey(BaseModel):
    """API key for authentication."""

    key: str = Field(..., description="API key")
    agent_id: str = Field(..., description="Agent ID associated with key")
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = Field(None, description="Expiration time")


class AuthResponse(BaseModel):
    """Authentication response."""

    authenticated: bool = Field(..., description="Whether authentication succeeded")
    agent_id: Optional[str] = Field(None, description="Authenticated agent ID")
    message: Optional[str] = Field(None, description="Error or status message")


# Rate Limiting Models


class RateLimitInfo(BaseModel):
    """Rate limit information."""

    limit: int = Field(..., description="Request limit per window")
    remaining: int = Field(..., description="Requests remaining")
    reset_at: datetime = Field(..., description="When limit resets")


# Error Models


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
