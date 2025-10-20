"""FastAPI dashboard application for economic agents monitoring."""

from economic_agents.dashboard.routers import (
    agent_control,
    company,
    decisions,
    metrics,
    resources,
    status,
    websocket,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI app
app = FastAPI(
    title="Economic Agents Dashboard",
    description="Real-time monitoring dashboard for autonomous economic agents",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(decisions.router, prefix="/api", tags=["decisions"])
app.include_router(resources.router, prefix="/api", tags=["resources"])
app.include_router(company.router, prefix="/api", tags=["company"])
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(websocket.router, prefix="/api", tags=["websocket"])
app.include_router(agent_control.router, prefix="/api", tags=["agent-control"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Economic Agents Dashboard",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "status": "/api/status",
            "decisions": "/api/decisions",
            "resources": "/api/resources",
            "company": "/api/company",
            "sub_agents": "/api/sub-agents",
            "metrics": "/api/metrics",
            "updates": "/api/updates (WebSocket)",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
