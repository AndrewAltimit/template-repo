"""Decisions endpoint router."""

from typing import List

from economic_agents.dashboard.agent_manager import agent_manager
from economic_agents.dashboard.dependencies import DashboardState, get_dashboard_state
from economic_agents.dashboard.models import DecisionResponse, LLMDecisionResponse
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


@router.get("/decisions/llm", response_model=List[LLMDecisionResponse])
async def get_llm_decisions(
    limit: int = Query(default=50, ge=1, le=1000),
):
    """Get LLM decision history from the current agent.

    Args:
        limit: Maximum number of decisions to return (1-1000)

    Returns:
        List of LLM decisions with full context
    """
    if not agent_manager.agent:
        return []

    # Check if agent has LLM decision engine
    if not hasattr(agent_manager.agent.decision_engine, "get_decisions"):
        return []

    # Get LLM decisions
    llm_decisions = agent_manager.agent.decision_engine.get_decisions()

    # Convert to response model
    responses = []
    for decision in llm_decisions[-limit:]:
        responses.append(
            LLMDecisionResponse(
                decision_id=decision.decision_id,
                timestamp=decision.timestamp,
                agent_type=decision.agent_type,
                state_snapshot=decision.state_snapshot,
                prompt=decision.prompt,
                raw_response=decision.raw_response,
                parsed_decision=decision.parsed_decision,
                validation_passed=decision.validation_passed,
                execution_time_seconds=decision.execution_time_seconds,
                fallback_used=decision.fallback_used,
            )
        )

    return responses
