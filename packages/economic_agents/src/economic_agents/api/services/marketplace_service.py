"""Marketplace API microservice.

Provides REST API for task marketplace operations:
- List available tasks
- Get task details
- Complete tasks
"""

from datetime import datetime
from typing import Dict, Optional

from economic_agents.api.models import (
    CompleteTaskRequest,
    CompleteTaskResponse,
    ErrorResponse,
    Task,
    TaskList,
)
from economic_agents.api.rate_limit import verify_and_rate_limit
from economic_agents.implementations.mock import MockMarketplace
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

# Create FastAPI app
app = FastAPI(
    title="Marketplace API",
    description="Task marketplace and completion service",
    version="1.0.0",
)

# Store marketplace instances per agent
marketplaces: Dict[str, MockMarketplace] = {}


def get_marketplace(agent_id: str) -> MockMarketplace:
    """Get or create marketplace for agent.

    Args:
        agent_id: Agent ID

    Returns:
        Marketplace instance for the agent
    """
    if agent_id not in marketplaces:
        # Create new marketplace with default seed
        marketplaces[agent_id] = MockMarketplace(seed=None)
    return marketplaces[agent_id]


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy", "service": "marketplace", "timestamp": datetime.now().isoformat()}


@app.get("/tasks", response_model=TaskList)
async def get_tasks(
    count: int = 5,
    agent_id: str = Depends(verify_and_rate_limit()),
):
    """Get available tasks from marketplace.

    Args:
        count: Number of tasks to generate
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        List of available tasks
    """
    marketplace = get_marketplace(agent_id)

    # Generate tasks
    tasks = marketplace.generate_tasks(count)

    # Convert to Task models
    task_models = [
        Task(
            id=task["id"],
            difficulty=task["difficulty"],
            reward=task["reward"],
            compute_hours_required=task["compute_hours_required"],
            description=task["description"],
        )
        for task in tasks
    ]

    return TaskList(tasks=task_models, count=len(task_models))


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    agent_id: str = Depends(verify_and_rate_limit()),
):
    """Get task details by ID.

    Args:
        task_id: Task ID
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Task details

    Raises:
        HTTPException: If task not found
    """
    marketplace = get_marketplace(agent_id)

    # Generate some tasks to search (in real implementation would have persistent storage)
    tasks = marketplace.generate_tasks(10)

    # Find task by ID
    for task in tasks:
        if task["id"] == task_id:
            return Task(
                id=task["id"],
                difficulty=task["difficulty"],
                reward=task["reward"],
                compute_hours_required=task["compute_hours_required"],
                description=task["description"],
            )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")


@app.post("/tasks/{task_id}/complete", response_model=CompleteTaskResponse)
async def complete_task(
    task_id: str,
    request: CompleteTaskRequest,
    agent_id: str = Depends(verify_and_rate_limit()),
):
    """Complete a task and get reward.

    Args:
        task_id: Task ID
        request: Completion request
        agent_id: Agent ID from API key
        _rate_limit: Rate limit check

    Returns:
        Completion result

    Raises:
        HTTPException: If task not found or completion fails
    """
    marketplace = get_marketplace(agent_id)

    # In a real implementation, would validate task exists and agent has required resources
    # For now, use MockMarketplace.complete_task which simulates success/failure

    # Generate tasks to find the one being completed
    tasks = marketplace.generate_tasks(10)

    # Find task
    task = None
    for t in tasks:
        if t["id"] == task_id:
            task = t
            break

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")

    # Simulate completion
    try:
        result = marketplace.complete_task(task)

        if result["success"]:
            return CompleteTaskResponse(
                success=True, reward=result["reward"], message=f"Task {task_id} completed successfully"
            )
        else:
            return CompleteTaskResponse(success=False, reward=0.0, message=result.get("message", "Task failed"))

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/initialize")
async def initialize_marketplace(
    seed: Optional[int] = None,
    agent_id: str = Depends(verify_and_rate_limit()),
):
    """Initialize or reset marketplace with specific seed.

    Args:
        seed: Random seed for task generation
        agent_id: Agent ID from API key

    Returns:
        Success message
    """
    marketplaces[agent_id] = MockMarketplace(seed=seed)
    return {"message": "Marketplace initialized", "agent_id": agent_id, "seed": seed}


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions with standard error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error="MarketplaceError", message=exc.detail).dict(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
