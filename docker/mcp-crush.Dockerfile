# Crush MCP Server - Self-contained image with Go and Crush CLI
FROM node:20-slim

# Define version arguments
ARG CRUSH_VERSION=0.30.0
ARG CRUSH_CHECKSUM_AMD64=8497f7ed533e93ec27d478afeca33e1157faafb83c37ea2d5dbdaa2dee9abd1d
ARG CRUSH_CHECKSUM_ARM64=810673903482180dc37e04254c61edf770383c0d927de10783fd42fed6e2e770

# Install Python 3.11 and all system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    git \
    curl \
    wget \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for Python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Install Crush from pre-built binaries
ARG TARGETARCH=amd64
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        ARCH="x86_64"; \
        CHECKSUM="${CRUSH_CHECKSUM_AMD64}"; \
    elif [ "$ARCH" = "arm64" ]; then \
        ARCH="arm64"; \
        CHECKSUM="${CRUSH_CHECKSUM_ARM64}"; \
    fi && \
    wget -q "https://github.com/charmbracelet/crush/releases/download/v${CRUSH_VERSION}/crush_${CRUSH_VERSION}_Linux_${ARCH}.tar.gz" -O /tmp/crush.tar.gz && \
    echo "${CHECKSUM}  /tmp/crush.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/crush.tar.gz -C /tmp && \
    mv "/tmp/crush_${CRUSH_VERSION}_Linux_${ARCH}/crush" /usr/local/bin/crush && \
    chmod +x /usr/local/bin/crush && \
    rm -rf "/tmp/crush_${CRUSH_VERSION}_Linux_${ARCH}" /tmp/crush.tar.gz

# Install Python MCP dependencies
RUN pip install --no-cache-dir --break-system-packages \
    aiohttp>=3.8.0 \
    click>=8.0.0 \
    python-dotenv \
    mcp \
    uvicorn \
    fastapi \
    pydantic

# Create necessary directories for node user
RUN mkdir -p /home/node/.config/crush \
    /home/node/.cache/crush \
    /home/node/.local/share/crush \
    /home/node/.crush \
    /home/node/workspace

# Copy Crush configurations
COPY --chown=node:node packages/github_agents/configs/crush.json /home/node/.config/crush/crush.json
COPY --chown=node:node packages/github_agents/configs/crush-data.json /home/node/.local/share/crush/crush.json

# Create app directory
WORKDIR /app

# Copy MCP server code (specific packages only)
COPY --chown=node:node tools/mcp/mcp_core /app/tools/mcp/mcp_core
COPY --chown=node:node tools/mcp/mcp_crush /app/tools/mcp/mcp_crush

# Install MCP packages
RUN pip install --no-cache-dir --break-system-packages /app/tools/mcp/mcp_core && \
    pip install --no-cache-dir --break-system-packages /app/tools/mcp/mcp_crush

# Set ownership for all node user directories
RUN chown -R node:node /home/node /app \
    && chmod -R 755 /home/node/.crush /home/node/workspace

# Switch to node user
USER node

# Set HOME to ensure crush finds its config
ENV HOME=/home/node

# Verify crush is installed
RUN which crush

# Set working directory to a writable location
WORKDIR /home/node/workspace

# Default command
CMD ["python", "-m", "mcp_crush.server", "--mode", "http"]
