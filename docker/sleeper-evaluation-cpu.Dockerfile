# Sleeper Agent Detection - CPU-only Evaluation Dockerfile
# Lightweight version for quick testing without GPU

FROM python:3.11-slim AS base

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

# Copy the consolidated requirements file
COPY --chown=evaluator:evaluator config/python/requirements-sleeper-all.txt /tmp/requirements-all.txt

# Install PyTorch CPU version and all dependencies in a single layer
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r /tmp/requirements-all.txt && \
    rm /tmp/requirements-all.txt

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
