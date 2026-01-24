"""
Strands-based AI Agent Runtime for AWS Bedrock AgentCore

Implements the HTTP protocol contract:
- POST /invocations - Main agent invocation endpoint
- GET /ping - Health check endpoint
"""

import logging
import os
from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel

log_level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Strands Agent Runtime",
    description="AWS Bedrock AgentCore Runtime using Strands",
    version="0.1.0",
)

agentcore_app = BedrockAgentCoreApp()


class InvocationRequest(BaseModel):
    prompt: str
    session_id: str | None = None
    context: dict[str, Any] | None = None


class InvocationResponse(BaseModel):
    completion: str
    session_id: str | None = None
    metadata: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    version: str


_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent

    if _agent is None:
        logger.info("Initializing Strands agent...")

        model_id = os.environ.get("MODEL_ID", "anthropic.claude-sonnet-4-20250514")
        region = os.environ.get("AWS_REGION", "us-east-1")

        logger.info(f"Using model: {model_id} in region: {region}")

        model = BedrockModel(model_id=model_id, region_name=region)

        system_prompt = os.environ.get(
            "SYSTEM_PROMPT",
            "You are a helpful AI assistant. Provide clear, accurate, and helpful responses.",
        )

        _agent = Agent(model=model, system_prompt=system_prompt)
        logger.info("Strands agent initialized successfully")

    return _agent


@app.get("/ping", response_model=HealthResponse)
async def ping() -> HealthResponse:
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/invocations", response_model=InvocationResponse)
async def invoke(request: InvocationRequest) -> InvocationResponse:
    try:
        logger.info(f"Received invocation request: session_id={request.session_id}")

        agent = get_agent()
        response = agent(request.prompt)
        completion = str(response)

        logger.info(f"Invocation completed: response_length={len(completion)}")

        return InvocationResponse(
            completion=completion,
            session_id=request.session_id,
            metadata={"model": os.environ.get("MODEL_ID", "anthropic.claude-sonnet-4-20250514")},
        )

    except Exception as e:
        logger.exception(f"Error during invocation: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


@agentcore_app.entrypoint
async def agentcore_invoke(request: dict[str, Any]) -> dict[str, Any]:
    invocation_request = InvocationRequest(
        prompt=request.get("prompt", ""),
        session_id=request.get("session_id"),
        context=request.get("context"),
    )

    response = await invoke(invocation_request)

    return {
        "completion": response.completion,
        "session_id": response.session_id,
        "metadata": response.metadata,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
