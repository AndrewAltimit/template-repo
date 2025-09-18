# Sleeper Agent Detection - Evaluation System Dockerfile
# Optimized for batch evaluation and report generation

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

# Copy only the pyproject.toml for dependency installation
COPY --chown=evaluator:evaluator packages/sleeper_detection/pyproject.toml /tmp/pyproject.toml

# Install all dependencies in a single layer
# Using the 'all' optional dependencies group for complete environment
RUN pip install --no-cache-dir "/tmp[all]" && \
    rm /tmp/pyproject.toml

# Copy application code
COPY --chown=evaluator:evaluator . /app

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

# Default command - run CLI help
CMD ["python", "-m", "packages.sleeper_detection.cli", "--help"]
