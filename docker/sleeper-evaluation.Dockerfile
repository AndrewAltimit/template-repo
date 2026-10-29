# Sleeper Agent Detection - Evaluation System Dockerfile
# Optimized for batch evaluation and report generation

# CUDA 13.0 runtime to match the cu130 torch 2.14.1 wheels (NVIDIA driver >= 580).
# Not the pytorch/pytorch:2.14.1 image: it ships Ubuntu 24.04's system Python
# 3.12 (PEP 668 managed), and the package and its current deps need 3.13. Same
# base as packages/sleeper_agents/docker/Dockerfile.gpu, so the layers are shared.
FROM nvidia/cuda:13.0.2-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies (Python 3.13 from deadsnakes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    ca-certificates \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.13 \
    python3.13-venv \
    python3.13-dev \
    curl \
    git \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Run everything from a Python 3.13 virtualenv (pip comes from ensurepip)
RUN python3.13 -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

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
# torch comes from the cu130 index first; the package install then finds the
# torch>=2.14.1 requirement already satisfied and keeps the CUDA 13.0 build.
RUN pip install --no-cache-dir "torch==2.14.1" --index-url https://download.pytorch.org/whl/cu130
RUN pip install --no-cache-dir /app/packages/sleeper_agents[all]

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
