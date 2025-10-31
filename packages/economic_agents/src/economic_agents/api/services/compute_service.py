"""Compute API microservice.

Provides REST API for compute resource operations:
- Check available hours
- Allocate compute hours
- Tick time (decay hours)
"""

from datetime import datetime
from typing import Dict

from economic_agents.api.auth import verify_api_key
from economic_agents.api.models import (
    AllocateRequest,
    AllocationResponse,
    ComputeHours,
    ErrorResponse,
    TickResponse,
)
from economic_agents.api.rate_limit import check_rate_limit
from economic_agents.implementations.mock import MockCompute
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Create FastAPI app
app = FastAPI(
    title="Compute API",
    description="Compute resource allocation and time tracking service",
    version="1.0.0",
)

# Store compute instances per agent
compute_resources: Dict[str, MockCompute] = {}


def get_compute(agent_id: str) -> MockCompute:
    """Get or create compute resource for agent.

    Args:
        agent_id: Agent ID

    Returns:
        Compute instance for the agent
    """
    if agent_id not in compute_resources:
        # Create new compute with default hours and cost
        compute_resources[agent_id] = MockCompute(initial_hours=48.0, cost_per_hour=0.0)
    return compute_resources[agent_id]


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "service": "compute", "timestamp": datetime.now().isoformat()}


@app.get("/hours", response_model=ComputeHours)
async def get_hours(
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Get available compute hours.

    Args:
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Available compute hours
    """
    compute = get_compute(agent_id)
    return ComputeHours(hours_remaining=compute.hours_remaining, agent_id=agent_id)


@app.post("/allocate", response_model=AllocationResponse)
async def allocate_hours(
    request: AllocateRequest,
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Allocate compute hours for a task.

    Args:
        request: Allocation details
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Allocation result

    Raises:
        HTTPException: If allocation fails (e.g., insufficient hours)
    """
    compute = get_compute(agent_id)

    try:
        # Attempt allocation
        compute.allocate_hours(request.hours, request.purpose)

        return AllocationResponse(
            success=True,
            hours_allocated=request.hours,
            hours_remaining=compute.hours_remaining,
            message=f"Allocated {request.hours} hours for {request.purpose}",
        )

    except ValueError as e:
        # Insufficient hours
        return AllocationResponse(
            success=False,
            hours_allocated=0.0,
            hours_remaining=compute.hours_remaining,
            message=str(e),
        )


@app.post("/tick", response_model=TickResponse)
async def tick_time(
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Advance time by one cycle (decay compute hours).

    Args:
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Tick result with decay information
    """
    compute = get_compute(agent_id)

    hours_before = compute.hours_remaining
    compute.tick()
    hours_after = compute.hours_remaining
    hours_decayed = hours_before - hours_after

    return TickResponse(success=True, hours_decayed=hours_decayed, hours_remaining=hours_after)


@app.post("/initialize")
async def initialize_compute(
    initial_hours: float = 48.0,
    cost_per_hour: float = 0.0,
    agent_id: str = Depends(verify_api_key),
):
    """Initialize or reset compute resource with specific hours.

    Args:
        initial_hours: Initial compute hours to set
        cost_per_hour: Cost per compute hour
        agent_id: Agent ID from API key

    Returns:
        Compute hours
    """
    compute_resources[agent_id] = MockCompute(initial_hours=initial_hours, cost_per_hour=cost_per_hour)
    return ComputeHours(hours_remaining=initial_hours, agent_id=agent_id)


@app.get("/cost")
async def get_cost_per_hour(
    agent_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Get cost per compute hour.

    Args:
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Cost per hour
    """
    compute = get_compute(agent_id)
    return {"cost_per_hour": compute.cost_per_hour, "agent_id": agent_id}


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions with standard error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error="ComputeError", message=exc.detail).dict(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
