"""Investor Portal API microservice.

Provides REST API for investment operations:
- Submit investment proposals
- Check proposal status
- Get investor information
"""

import uuid
from datetime import datetime
from typing import Dict

from economic_agents.api.auth import verify_api_key
from economic_agents.api.models import (
    ErrorResponse,
    InvestmentDecision,
    InvestmentProposal,
    InvestorInfo,
    InvestorList,
    ProposalResponse,
)
from economic_agents.api.rate_limit import check_rate_limit
from economic_agents.investment.evaluator import InvestmentEvaluator
from economic_agents.investment.investor import Investor
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

# Create FastAPI app
app = FastAPI(
    title="Investor Portal API",
    description="Investment proposal and evaluation service",
    version="1.0.0",
)

# Store proposals and decisions
proposals: Dict[str, dict] = {}
decisions: Dict[str, InvestmentDecision] = {}

# Create investors
investors = [
    Investor(
        name="TechVentures Capital",
        capital=10000000.0,
        focus=["AI", "SaaS", "Enterprise"],
        stage_preference="seed",
    ),
    Investor(
        name="Growth Equity Partners",
        capital=50000000.0,
        focus=["FinTech", "HealthTech", "SaaS"],
        stage_preference="series_a",
    ),
    Investor(
        name="Seed Stage Investors",
        capital=5000000.0,
        focus=["AI", "ML", "Data"],
        stage_preference="seed",
    ),
]

evaluator = InvestmentEvaluator()


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "service": "investor_portal", "timestamp": datetime.now().isoformat()}


@app.post("/proposals", response_model=ProposalResponse)
async def submit_proposal(
    proposal: InvestmentProposal,
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Submit an investment proposal.

    Args:
        proposal: Investment proposal details
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Proposal submission result
    """
    # Generate unique proposal ID
    proposal_id = str(uuid.uuid4())

    # Store proposal
    proposals[proposal_id] = {
        "id": proposal_id,
        "agent_id": agent_id,
        "submitted_at": datetime.now(),
        "status": "pending",
        **proposal.dict(),
    }

    # Evaluate proposal with all investors
    # In a real system, this would be async
    best_investor = None
    best_score = 0
    best_decision = None

    for investor in investors:
        # Create proposal object (simplified version of Company for evaluation)
        company_data = {
            "id": proposal.company_id,
            "name": proposal.company_name,
            "stage": proposal.stage,
            "business_plan": proposal.business_plan,
            "capital": 0,  # Seeking funding
            "team": [],  # Simplified
        }

        # Evaluate
        decision = evaluator.evaluate_proposal(company_data, investor)

        if decision["approved"] and decision["score"] > best_score:
            best_score = decision["score"]
            best_investor = investor
            best_decision = decision

    # Store decision
    if best_decision and best_investor:
        decisions[proposal_id] = InvestmentDecision(
            proposal_id=proposal_id,
            approved=True,
            investment_amount=best_decision["investment_amount"],
            investor_name=best_investor.name,
            conditions=best_decision.get("conditions", []),
            feedback=best_decision.get("feedback", "Investment approved"),
        )
        proposals[proposal_id]["status"] = "approved"
        status_message = f"Proposal approved by {best_investor.name}"
    else:
        decisions[proposal_id] = InvestmentDecision(
            proposal_id=proposal_id,
            approved=False,
            investment_amount=0.0,
            investor_name="N/A",
            conditions=[],
            feedback="Proposal did not meet investor criteria",
        )
        proposals[proposal_id]["status"] = "rejected"
        status_message = "Proposal rejected by all investors"

    return ProposalResponse(proposal_id=proposal_id, status=proposals[proposal_id]["status"], message=status_message)


@app.get("/proposals/{proposal_id}", response_model=InvestmentDecision)
async def get_proposal_status(
    proposal_id: str,
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Get investment decision for a proposal.

    Args:
        proposal_id: Proposal ID
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Investment decision

    Raises:
        HTTPException: If proposal not found or not owned by agent
    """
    if proposal_id not in proposals:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proposal {proposal_id} not found")

    # Verify ownership
    if proposals[proposal_id]["agent_id"] != agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this proposal")

    if proposal_id not in decisions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal is still being evaluated")

    return decisions[proposal_id]


@app.get("/investors", response_model=InvestorList)
async def get_investors(
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Get list of active investors.

    Args:
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        List of investors
    """
    investor_models = [
        InvestorInfo(
            name=inv.name,
            focus=inv.focus,
            typical_check_size=inv.typical_check_size,
            stage_preference=inv.stage_preference,
        )
        for inv in investors
    ]

    return InvestorList(investors=investor_models, count=len(investor_models))


@app.get("/proposals")
async def list_proposals(
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """List all proposals for this agent.

    Args:
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        List of proposals
    """
    agent_proposals = [p for p in proposals.values() if p["agent_id"] == agent_id]

    return {"proposals": agent_proposals, "count": len(agent_proposals)}


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions with standard error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error="InvestorPortalError", message=exc.detail).dict(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
