"""Decisions endpoint router."""

from typing import List

from economic_agents.dashboard.dependencies import DashboardState, get_dashboard_state
from economic_agents.dashboard.models import DecisionResponse
from fastapi import APIRouter, Depends, Query

router = APIRouter()


@router.get("/decisions", response_model=List[DecisionResponse])
async def get_decisions(
    limit: int = Query(default=50, ge=1, le=1000),
    state: DashboardState = Depends(get_dashboard_state),
):
    """Get recent decisions.

    Args:
        limit: Maximum number of decisions to return (1-1000)
        state: Dashboard state dependency

    Returns:
        List of recent decisions
    """
    agent_state = state.get_agent_state()
    decisions = agent_state.get("decisions", [])

    # Return most recent decisions up to limit
    return decisions[-limit:]
