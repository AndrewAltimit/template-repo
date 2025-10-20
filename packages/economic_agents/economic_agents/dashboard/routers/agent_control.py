"""Agent control router for starting/stopping dashboard-controlled agents."""

from economic_agents.dashboard.agent_manager import agent_manager
from economic_agents.dashboard.models import (
    AgentControlStatusResponse,
    AgentStartRequest,
    AgentStartResponse,
    AgentStopResponse,
)
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/agent/start", response_model=AgentStartResponse)
async def start_agent(request: AgentStartRequest) -> AgentStartResponse:
    """Start an autonomous agent with specified configuration.

    Args:
        request: Agent configuration (mode, cycles, balance, etc.)

    Returns:
        AgentStartResponse with agent_id and configuration

    Raises:
        HTTPException: If agent is already running or invalid configuration
    """
    try:
        result = await agent_manager.start_agent(
            mode=request.mode,
            max_cycles=request.max_cycles,
            initial_balance=request.initial_balance,
            initial_compute_hours=request.initial_compute_hours,
            compute_cost_per_hour=request.compute_cost_per_hour,
        )
        return AgentStartResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/agent/stop", response_model=AgentStopResponse)
async def stop_agent() -> AgentStopResponse:
    """Stop the currently running agent.

    Returns:
        AgentStopResponse with final statistics
    """
    result = await agent_manager.stop_agent()
    return AgentStopResponse(**result)


@router.get("/agent/control-status", response_model=AgentControlStatusResponse)
async def get_agent_control_status() -> AgentControlStatusResponse:
    """Get current agent control status.

    Returns:
        AgentControlStatusResponse with running state and progress
    """
    status = await agent_manager.get_status()
    return AgentControlStatusResponse(**status)
