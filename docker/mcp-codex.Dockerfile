# Dockerfile for Codex MCP Server
FROM python:3.11-slim

# Install system dependencies including Node.js for Codex CLI
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Codex CLI globally
RUN npm install -g @openai/codex

# Create non-root user
RUN useradd -m -u 1000 user && \
    mkdir -p /home/user/.codex && \
    chown -R user:user /home/user/.codex

# Set working directory
WORKDIR /workspace

# Copy requirements
COPY config/python/requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy the MCP core modules
COPY tools/mcp/core /workspace/tools/mcp/core

# Copy the Codex MCP server
COPY tools/mcp/codex /workspace/tools/mcp/codex

# Set Python path
ENV PYTHONPATH=/workspace:$PYTHONPATH
ENV NODE_ENV=production

# Create a writable directory for Codex runtime
RUN mkdir -p /tmp/codex-runtime && \
    chown -R user:user /tmp/codex-runtime

# Set HOME to user's home directory
ENV HOME=/home/user

# Switch to non-root user
USER user

# Default command
CMD ["python", "-m", "tools.mcp.codex.server", "--mode", "http", "--host", "0.0.0.0", "--port", "8021"]
