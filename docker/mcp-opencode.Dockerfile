# OpenCode MCP Server - Self-contained image with OpenCode CLI
FROM python:3.11-slim

# Define version arguments
ARG OPENCODE_VERSION=0.5.7
ARG OPENCODE_CHECKSUM_AMD64=4850ccbda4ab9de82fe1bd22b5b0f5704a36e36f0d532ed1d35b40293bde27da
ARG OPENCODE_CHECKSUM_ARM64=356bf8981172cc9806f2d393a068dff33812da917d6f7879aa3c3d2d7823ed6f

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCode from GitHub releases
# SECURITY: We verify checksums to ensure binary integrity
ARG TARGETARCH=amd64
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        ARCH="x64"; \
        CHECKSUM="${OPENCODE_CHECKSUM_AMD64}"; \
    elif [ "$ARCH" = "arm64" ]; then \
        ARCH="arm64"; \
        CHECKSUM="${OPENCODE_CHECKSUM_ARM64}"; \
    fi && \
    wget -q "https://github.com/sst/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-${ARCH}.zip" -O /tmp/opencode.zip && \
    echo "${CHECKSUM}  /tmp/opencode.zip" | sha256sum -c - && \
    unzip -q /tmp/opencode.zip -d /usr/local/bin/ && \
    rm /tmp/opencode.zip && \
    chmod +x /usr/local/bin/opencode

# Install Python MCP dependencies
RUN pip install --no-cache-dir \
    aiohttp>=3.8.0 \
    click>=8.0.0 \
    python-dotenv \
    mcp \
    uvicorn \
    fastapi \
    pydantic

# Create a non-root user
RUN useradd -m -u 1000 appuser

# Create necessary directories for appuser
RUN mkdir -p /home/appuser/.config/opencode \
    /home/appuser/.cache/opencode \
    /home/appuser/.local/share/opencode

# Copy OpenCode configuration
COPY --chown=appuser:appuser packages/github_agents/configs/opencode-config.json /home/appuser/.config/opencode/.opencode.json

# Create app directory
WORKDIR /app

# Copy only necessary MCP packages
COPY tools/mcp/mcp_core /app/tools/mcp/mcp_core
COPY tools/mcp/mcp_opencode /app/tools/mcp/mcp_opencode

# Install MCP packages
RUN pip install --no-cache-dir /app/tools/mcp/mcp_core && \
    pip install --no-cache-dir /app/tools/mcp/mcp_opencode

# Set Python path
ENV PYTHONPATH=/app

# Set ownership for all appuser directories
RUN chown -R appuser:appuser /home/appuser /app

# Switch to non-root user
USER appuser

# Set HOME to ensure opencode finds its config
ENV HOME=/home/appuser

# Verify opencode is installed
RUN which opencode

# Default command
CMD ["python", "-m", "mcp_opencode.server", "--mode", "http"]
