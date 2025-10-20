"""Status endpoint router."""

from datetime import datetime

from economic_agents.dashboard.dependencies import DashboardState, get_dashboard_state
from economic_agents.dashboard.models import AgentStatusResponse
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/status", response_model=AgentStatusResponse)
async def get_status(state: DashboardState = Depends(get_dashboard_state)):
    """Get current agent status.

    Returns:
        AgentStatusResponse with current agent status
    """
    agent_state = state.get_agent_state()

    # Default values if not set
    return AgentStatusResponse(
        agent_id=agent_state.get("agent_id", "unknown"),
        balance=agent_state.get("balance", 0.0),
        compute_hours_remaining=agent_state.get("compute_hours", 0.0),
        mode=agent_state.get("mode", "survival"),
        current_activity=agent_state.get("current_activity", "idle"),
        company_exists=agent_state.get("company_exists", False),
        company_id=agent_state.get("company_id"),
        last_updated=agent_state.get("last_updated", datetime.now()),
    )
