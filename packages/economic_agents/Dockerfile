# Dockerfile for Autonomous Economic Agents
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy package files
COPY pyproject.toml README.md ./
COPY economic_agents/ ./economic_agents/
COPY tests/ ./tests/

# Install Python dependencies
# Install with all extras for full functionality
RUN pip install --no-cache-dir -e ".[all]"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command
CMD ["/bin/bash"]
