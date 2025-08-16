# AI Toolkit MCP Server with GPU support
FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY docker/requirements-ai-toolkit.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy the MCP server code
COPY tools/mcp /app/tools/mcp
COPY config /app/config

# Create output directories
RUN mkdir -p /ai-toolkit/datasets /ai-toolkit/outputs /ai-toolkit/configs /app/logs

# Environment variables for GPU
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
ENV PYTHONUNBUFFERED=1
ENV PORT=8012

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Default command to run the MCP server
CMD ["python3", "-m", "tools.mcp.ai_toolkit.server", "--mode", "http", "--host", "0.0.0.0"]
