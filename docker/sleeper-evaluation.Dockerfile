# Sleeper Agent Detection - Evaluation System Dockerfile
# Optimized for batch evaluation and report generation

# torch 2.14.1 bundles CUDA 13.0 (NVIDIA driver >= 580)
FROM pytorch/pytorch:2.14.1-cuda13.0-cudnn9-runtime AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} evaluator && \
    useradd -u ${USER_ID} -g ${GROUP_ID} -m evaluator

# Create necessary directories with correct permissions
RUN mkdir -p /models /results /db && \
    chown -R evaluator:evaluator /models /results /db

# Upgrade pip and install build tools
RUN pip install --upgrade pip setuptools wheel

# Copy application code first for pyproject.toml access
COPY --chown=evaluator:evaluator . /app

# Install dependencies from pyproject.toml - single source of truth
# Install in editable mode with 'all' extras for complete environment
# torch is pinned to the base image's version so pip never replaces it, which would
# leave the base image's torchvision/torchaudio built against a different torch
# (importing transformers then fails with "operator torchvision::nms does not exist").
RUN pip install --no-cache-dir "torch==2.14.1" /app/packages/sleeper_agents[all]

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PYTHONUNBUFFERED=1

# Model cache directories
ENV TRANSFORMERS_CACHE=/models
ENV HF_HOME=/models
ENV TORCH_HOME=/models

# Evaluation settings
ENV EVAL_RESULTS_DIR=/results
ENV EVAL_DB_PATH=/db/evaluation_results.db

# Switch to non-root user
USER evaluator

# Health check - verify Python and packages are working
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import sleeper_agents; print('OK')" || exit 1

# Default command - run CLI help
CMD ["python", "-m", "sleeper_agents.cli", "--help"]
