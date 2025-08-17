# ElevenLabs Speech MCP Server Container
# Stage 1: Builder
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements and build wheels
COPY docker/requirements/requirements-elevenlabs.txt .
RUN pip wheel --no-cache-dir --wheel-dir=/build/wheels -r requirements-elevenlabs.txt

# Stage 2: Final Image
FROM python:3.11-slim

# Create non-root user for security
RUN useradd -m -u 1000 mcp

WORKDIR /app

# Copy wheels from builder and install
COPY --from=builder /build/wheels /build/wheels
RUN pip install --no-cache-dir --no-index --find-links=/build/wheels /build/wheels/* && \
    rm -rf /build/wheels

# Copy the MCP server code
COPY tools/mcp/elevenlabs_speech /app/tools/mcp/elevenlabs_speech
COPY tools/mcp/core /app/tools/mcp/core

# Set ownership to non-root user
RUN chown -R mcp:mcp /app

USER mcp

# Expose port for HTTP mode
EXPOSE 8018

# Default to HTTP mode for container
CMD ["python", "-m", "tools.mcp.elevenlabs_speech.server", "--mode", "http"]
