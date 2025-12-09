"""Company and sub-agents endpoint router."""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from economic_agents.dashboard.dependencies import DashboardState, get_dashboard_state
from economic_agents.dashboard.models import CompanyResponse, SubAgentResponse

router = APIRouter()


@router.get("/company", response_model=CompanyResponse)
async def get_company(state: DashboardState = Depends(get_dashboard_state)):
    """Get company information.

    Returns:
        CompanyResponse with company details

    Raises:
        HTTPException: If no company exists
    """
    agent_state = state.get_agent_state()
    company_registry = state.get_company_registry()

    company_id = agent_state.get("company_id")
    if not company_id:
        raise HTTPException(status_code=404, detail="No company exists")

    # Get company from registry
    company = company_registry.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found in registry")

    # Handle both dict and Company object
    if isinstance(company, dict):
        return CompanyResponse(
            company_id=company.get("id", company_id),
            name=company.get("name", "Unknown"),
            stage=company.get("stage", "unknown"),
            capital=company.get("capital", 0.0),
            funding_status=company.get("funding_status", "unknown"),
            team_size=company.get("team_size", 0),
            products_count=company.get("products_count", 0),
            created_at=company.get("created_at", datetime.now()),
            business_plan_exists=company.get("business_plan_exists", False),
            mission=company.get("mission", ""),
        )
    else:
        # Company object
        return CompanyResponse(
            company_id=company.id,
            name=company.name,
            stage=company.stage,
            capital=company.capital,
            funding_status=company.funding_status,
            team_size=len(company.board_member_ids) + len(company.executive_ids) + len(company.employee_ids),
            products_count=len(company.products),
            created_at=company.created_at,
            business_plan_exists=company.business_plan is not None,
            mission=company.mission,
        )


@router.get("/sub-agents", response_model=List[SubAgentResponse])
async def get_sub_agents(state: DashboardState = Depends(get_dashboard_state)):
    """Get sub-agent roster and status.

    Returns:
        List of sub-agents

    Raises:
        HTTPException: If no company exists
    """
    agent_state = state.get_agent_state()

    company_id = agent_state.get("company_id")
    if not company_id:
        raise HTTPException(status_code=404, detail="No company exists")

    # Get sub-agents from agent state
    sub_agents = agent_state.get("sub_agents", [])

    return [
        SubAgentResponse(
            agent_id=sa.get("id", "unknown"),
            role=sa.get("role", "unknown"),
            status=sa.get("status", "unknown"),
            created_at=sa.get("created_at"),
            tasks_completed=sa.get("tasks_completed", 0),
        )
        for sa in sub_agents
    ]
