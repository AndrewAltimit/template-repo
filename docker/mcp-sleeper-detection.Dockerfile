# Sleeper Agent Detection Dockerfile
# Supports both CPU and GPU modes

FROM pytorch/pytorch:2.2.0-cuda11.8-cudnn8-runtime AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (will be overridden by docker-compose user directive)
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} appuser && \
    useradd -u ${USER_ID} -g ${GROUP_ID} -m appuser

# Create necessary directories with correct permissions
RUN mkdir -p /models /cache /output && \
    chown -R appuser:appuser /models /cache /output

# Install Python dependencies
COPY --chown=appuser:appuser config/python/requirements-sleeper-detection.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy application code
COPY --chown=appuser:appuser . /app

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PYTHONUNBUFFERED=1

# Model cache directories
ENV TRANSFORMERS_CACHE=/models
ENV HF_HOME=/models
ENV TORCH_HOME=/models

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8021/health || exit 1

# Default command (can be overridden)
CMD ["python", "-m", "tools.mcp.sleeper_detection.server", "--mode", "http"]
