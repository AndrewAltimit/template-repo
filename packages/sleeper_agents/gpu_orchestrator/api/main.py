"""Main FastAPI application for GPU Orchestrator."""

import logging
import threading
import time
from contextlib import asynccontextmanager

from api.models import HealthResponse
from api.routes import jobs, logs, system
from core.config import settings
from core.container_manager import ContainerManager
from core.database import Database
from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
db: Database = None  # type: ignore
container_manager: ContainerManager = None  # type: ignore
start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db, container_manager, start_time

    # Startup
    logger.info("Starting GPU Orchestrator API...")
    start_time = time.time()

    try:
        db = Database()
        logger.info("Database initialized at %s", settings.database_path)

        container_manager = ContainerManager()
        logger.info("Container manager initialized")

        # Ensure logs directory exists
        settings.logs_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Logs directory: {settings.logs_directory}")

        # Start log cleanup worker in background
        from workers.log_cleanup import start_log_cleanup_worker

        cleanup_thread = threading.Thread(target=start_log_cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Log cleanup worker started")

        # Recover running jobs (mark orphaned jobs as failed)
        jobs_list, _ = db.list_jobs(status=None, limit=1000)
        for job in jobs_list:
            if job["status"].value == "running":
                if job["container_id"]:
                    try:
                        status = container_manager.get_container_status(job["container_id"])
                        if status != "running":
                            logger.warning(f"Job {job['job_id']} container is {status}, marking as failed")
                            db.update_job_status(
                                job["job_id"],
                                status="failed",  # type: ignore
                                error_message="Container stopped unexpectedly",
                            )
                    except Exception as e:
                        logger.error(f"Failed to check job {job['job_id']}: {e}")
                        db.update_job_status(
                            job["job_id"],
                            status="failed",  # type: ignore
                            error_message=f"Failed to recover: {str(e)}",
                        )

        logger.info("GPU Orchestrator API started successfully")

    except Exception as e:
        logger.error(f"Failed to start GPU Orchestrator API: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down GPU Orchestrator API...")


# Create FastAPI app
app = FastAPI(
    title="GPU Orchestrator API",
    description="API for managing GPU-based sleeper detection jobs",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key from header."""
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


# Include routers
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"], dependencies=[Security(verify_api_key)])
app.include_router(logs.router, prefix="/api/jobs", tags=["Logs"], dependencies=[Security(verify_api_key)])
app.include_router(system.router, prefix="/api/system", tags=["System"], dependencies=[Security(verify_api_key)])


# Health check endpoint (no auth required)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = time.time() - start_time
    return HealthResponse(status="healthy", uptime_seconds=uptime)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "GPU Orchestrator API",
        "version": "1.0.0",
        "status": "running",
        "docs_url": "/docs",
        "health_url": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
