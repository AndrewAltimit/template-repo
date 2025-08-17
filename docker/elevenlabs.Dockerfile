# ElevenLabs Speech MCP Server Container
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY docker/requirements/requirements-elevenlabs.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the MCP server code
COPY tools/mcp/elevenlabs_speech /app/tools/mcp/elevenlabs_speech
COPY tools/mcp/core /app/tools/mcp/core

# Create output directory
RUN mkdir -p /app/outputs/elevenlabs_speech

# Create non-root user for security
RUN useradd -m -u 1000 mcp && \
    chown -R mcp:mcp /app

USER mcp

# Expose port for HTTP mode
EXPOSE 8018

# Default to HTTP mode for container
CMD ["python", "-m", "tools.mcp.elevenlabs_speech.server", "--mode", "http"]
