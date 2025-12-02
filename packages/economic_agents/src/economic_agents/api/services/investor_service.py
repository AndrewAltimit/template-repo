"""Investor Portal API microservice.

Provides REST API for investment operations:
- Submit investment proposals
- Check proposal status
- Get investor information
"""

from datetime import datetime
from typing import Dict
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from economic_agents.api.models import (
    ErrorResponse,
    InvestmentDecision,
    InvestmentProposal,
    InvestorInfo,
    InvestorList,
    ProposalResponse,
)
from economic_agents.api.rate_limit import verify_and_rate_limit
from economic_agents.investment.investor_agent import InvestorAgent
from economic_agents.investment.models import (
    InvestmentCriteria,
    InvestmentProposal as ProposalModel,
    InvestmentStage,
    InvestorProfile,
    InvestorType,
)

# Create FastAPI app
app = FastAPI(
    title="Investor Portal API",
    description="Investment proposal and evaluation service",
    version="1.0.0",
)

# Store proposals and decisions
proposals: Dict[str, dict] = {}
decisions: Dict[str, InvestmentDecision] = {}

# Create investor agents with profiles
investor_agents = [
    InvestorAgent(
        profile=InvestorProfile(
            id="investor-1",
            name="TechVentures Capital",
            type=InvestorType.VENTURE_CAPITAL,
            available_capital=10000000.0,
            total_invested=0.0,
            portfolio_size=0,
            criteria=InvestmentCriteria(
                preferred_stages=[InvestmentStage.SEED],
                min_market_size=100000000.0,
                min_revenue_projection=1000000.0,
                max_burn_rate=50000.0,
                required_team_size=3,
                preferred_markets=["AI", "SaaS", "Enterprise"],
                risk_tolerance=0.7,
                min_roi_expectation=10.0,
            ),
        )
    ),
    InvestorAgent(
        profile=InvestorProfile(
            id="investor-2",
            name="Growth Equity Partners",
            type=InvestorType.VENTURE_CAPITAL,
            available_capital=50000000.0,
            total_invested=0.0,
            portfolio_size=0,
            criteria=InvestmentCriteria(
                preferred_stages=[InvestmentStage.SERIES_A],
                min_market_size=500000000.0,
                min_revenue_projection=5000000.0,
                max_burn_rate=200000.0,
                required_team_size=10,
                preferred_markets=["FinTech", "HealthTech", "SaaS"],
                risk_tolerance=0.6,
                min_roi_expectation=8.0,
            ),
        )
    ),
    InvestorAgent(
        profile=InvestorProfile(
            id="investor-3",
            name="Seed Stage Investors",
            type=InvestorType.ANGEL,
            available_capital=5000000.0,
            total_invested=0.0,
            portfolio_size=0,
            criteria=InvestmentCriteria(
                preferred_stages=[InvestmentStage.SEED, InvestmentStage.PRE_SEED],
                min_market_size=50000000.0,
                min_revenue_projection=500000.0,
                max_burn_rate=25000.0,
                required_team_size=2,
                preferred_markets=["AI", "ML", "Data"],
                risk_tolerance=0.8,
                min_roi_expectation=12.0,
            ),
        )
    ),
]


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
    agent_id: str = Depends(verify_and_rate_limit()),
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
    best_investor_agent = None
    best_score = 0.0
    best_decision = None

    for investor_agent in investor_agents:
        # Create InvestmentProposal model for evaluation
        # Map stage string to InvestmentStage enum
        try:
            stage_enum = InvestmentStage[proposal.stage.upper()]
        except KeyError:
            stage_enum = InvestmentStage.SEED

        proposal_model = ProposalModel(
            id=proposal_id,
            company_id=proposal.company_id,
            company_name=proposal.company_name,
            stage=stage_enum,
            amount_requested=proposal.funding_requested,
            valuation=proposal.funding_requested * 5,  # 5x multiple
            equity_offered=20.0,  # Default equity %
            use_of_funds={"product_development": proposal.funding_requested * 0.6, "hiring": proposal.funding_requested * 0.4},
            revenue_projections=[
                proposal.funding_requested * 2,
                proposal.funding_requested * 5,
                proposal.funding_requested * 10,
            ],
            market_size=1000000000.0,  # Default large market
            team_size=proposal.team_size,
            competitive_advantages=["Innovative approach", "Strong team", "Market opportunity"],
            risks=["Market competition", "Execution risk"],
            milestones=[{"month": 6, "target": "Product launch"}, {"month": 12, "target": "Revenue target"}],
        )

        # Evaluate
        decision = investor_agent.evaluate_proposal(proposal_model)

        # Calculate overall score from evaluation scores
        if decision.evaluation_scores:
            avg_score = sum(decision.evaluation_scores.values()) / len(decision.evaluation_scores)
        else:
            avg_score = 0.0

        if decision.approved and avg_score > best_score:
            best_score = avg_score
            best_investor_agent = investor_agent
            best_decision = decision

    # Store decision
    if best_decision and best_investor_agent:
        decisions[proposal_id] = InvestmentDecision(
            proposal_id=proposal_id,
            approved=True,
            investment_amount=best_decision.amount_offered,
            investor_name=best_investor_agent.profile.name,
            conditions=best_decision.conditions,
            feedback=best_decision.reasoning,
        )
        proposals[proposal_id]["status"] = "approved"
        status_message = f"Proposal approved by {best_investor_agent.profile.name}"
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
    agent_id: str = Depends(verify_and_rate_limit()),
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
    agent_id: str = Depends(verify_and_rate_limit()),
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
            name=inv_agent.profile.name,
            focus=inv_agent.profile.criteria.preferred_markets,
            typical_check_size=inv_agent.profile.available_capital * 0.05,  # 5% of available capital
            stage_preference=(
                inv_agent.profile.criteria.preferred_stages[0].value if inv_agent.profile.criteria.preferred_stages else "seed"
            ),
        )
        for inv_agent in investor_agents
    ]

    return InvestorList(investors=investor_models, count=len(investor_models))


@app.get("/proposals")
async def list_proposals(
    agent_id: str = Depends(verify_and_rate_limit()),
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
