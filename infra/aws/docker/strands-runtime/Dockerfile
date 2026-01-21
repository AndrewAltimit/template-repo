# Strands Agent Runtime for AWS Bedrock AgentCore
#
# ARM64 container image implementing the AgentCore HTTP protocol contract.

FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml ./

RUN uv pip install --system --no-cache -r pyproject.toml

COPY agent.py ./

RUN useradd --create-home --shell /bin/bash agentuser && \
    chown -R agentuser:agentuser /app

USER agentuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/ping').raise_for_status()" || exit 1

CMD ["opentelemetry-instrument", \
     "--service_name", "strands-agent-runtime", \
     "--traces_exporter", "otlp", \
     "--metrics_exporter", "otlp", \
     "--logs_exporter", "otlp", \
     "uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]
