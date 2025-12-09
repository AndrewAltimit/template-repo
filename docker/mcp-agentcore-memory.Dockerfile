FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY docker/requirements/requirements-agentcore-memory.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP core (shared base)
COPY tools/mcp/mcp_core /app/tools/mcp/mcp_core

# Copy agentcore-memory server
COPY tools/mcp/mcp_agentcore_memory /app/tools/mcp/mcp_agentcore_memory

# Install MCP packages
RUN pip install --no-cache-dir /app/tools/mcp/mcp_core && \
    pip install --no-cache-dir "/app/tools/mcp/mcp_agentcore_memory[all]"

# Set Python path
ENV PYTHONPATH=/app

# Create a non-root user
RUN useradd -m -u 1000 appuser

# Switch to non-root user
USER appuser

# Expose port for HTTP mode
EXPOSE 8023

# Default to STDIO mode for Claude Code integration
CMD ["python", "-m", "mcp_agentcore_memory.server", "--mode", "stdio"]
