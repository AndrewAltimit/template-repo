# OpenCode MCP Server - Self-contained image with OpenCode CLI
FROM python:3.11-slim

# Define version arguments
ARG OPENCODE_VERSION=1.0.223
ARG OPENCODE_CHECKSUM_AMD64=6c1bf6114a0b08fdb4c15ceef9da4480df0297699e045db7dd9a2950b0b9cc09
ARG OPENCODE_CHECKSUM_ARM64=e6549b392ea52842a995da5eae4d35209df605066613b71e7883457d8ecaee9b

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCode from GitHub releases
# SECURITY: We verify checksums to ensure binary integrity
# Note: v1.0+ releases use tar.gz format instead of zip
ARG TARGETARCH=amd64
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        ARCH="x64"; \
        CHECKSUM="${OPENCODE_CHECKSUM_AMD64}"; \
    elif [ "$ARCH" = "arm64" ]; then \
        ARCH="arm64"; \
        CHECKSUM="${OPENCODE_CHECKSUM_ARM64}"; \
    fi && \
    wget -q "https://github.com/sst/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-${ARCH}.tar.gz" -O /tmp/opencode.tar.gz && \
    echo "${CHECKSUM}  /tmp/opencode.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/opencode.tar.gz -C /usr/local/bin/ && \
    rm /tmp/opencode.tar.gz && \
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
