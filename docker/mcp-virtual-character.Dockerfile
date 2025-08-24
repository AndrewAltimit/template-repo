# MCP Virtual Character Server Docker Image
#
# IMPORTANT: This container runs the middleware MCP server only.
# VRChat itself must run on a Windows machine with GPU (cannot be containerized).
# This server communicates with VRChat via OSC-over-HTTP bridge to a remote Windows host.
#
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dedicated requirements for this service
COPY docker/requirements/requirements-virtual-character.txt ./requirements.txt

# Install Python dependencies (minimal set for virtual character server)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the virtual character server code
COPY tools/mcp/virtual_character /app/tools/mcp/virtual_character
COPY tools/mcp/core /app/tools/mcp/core

# Copy any additional configuration files
COPY config/ /app/config/

# Create non-root user
RUN useradd -m -u 1000 mcp-user && \
    chown -R mcp-user:mcp-user /app

USER mcp-user

# Environment variables
ENV PYTHONPATH=/app
ENV VIRTUAL_CHARACTER_HOST=0.0.0.0
ENV VIRTUAL_CHARACTER_PORT=8020
ENV DEFAULT_BACKEND=mock

# Expose the server port
EXPOSE 8020

# Health check is defined in docker-compose.yml for consistency

# Run the server
CMD ["python", "-m", "tools.mcp.virtual_character.server"]
