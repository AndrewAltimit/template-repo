# Crush MCP Server - Self-contained image with Go and Crush CLI
FROM node:20-slim

# Define version arguments
ARG GO_VERSION=1.24.5
ARG GO_CHECKSUM_AMD64=10ad9e86233e74c0f6590fe5426895de6bf388964210eac34a6d83f38918ecdc
ARG GO_CHECKSUM_ARM64=44e2d8b8e1b24a87dcab8c0bbf673cfcf92dc2ac0b3094df48b5c7fdb670cd5e

# Install Python 3.11 and all system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    git \
    curl \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for Python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Install Go for building Crush
ARG TARGETARCH=amd64
RUN wget -q https://go.dev/dl/go${GO_VERSION}.linux-${TARGETARCH}.tar.gz && \
    if [ "${TARGETARCH}" = "amd64" ]; then \
        echo "${GO_CHECKSUM_AMD64}  go${GO_VERSION}.linux-${TARGETARCH}.tar.gz" | sha256sum -c -; \
    elif [ "${TARGETARCH}" = "arm64" ]; then \
        echo "${GO_CHECKSUM_ARM64}  go${GO_VERSION}.linux-${TARGETARCH}.tar.gz" | sha256sum -c -; \
    fi && \
    tar -C /usr/local -xzf go${GO_VERSION}.linux-${TARGETARCH}.tar.gz && \
    rm go${GO_VERSION}.linux-${TARGETARCH}.tar.gz

# Set Go environment variables
ENV PATH="/usr/local/go/bin:/home/node/go/bin:${PATH}"
ENV GOPATH="/home/node/go"

# Install Crush from Charm Bracelet
ENV GOBIN=/usr/local/bin
RUN go install github.com/charmbracelet/crush@latest

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
COPY --chown=node:node packages/github_ai_agents/configs/crush.json /home/node/.config/crush/crush.json
COPY --chown=node:node packages/github_ai_agents/configs/crush-data.json /home/node/.local/share/crush/crush.json

# Create app directory
WORKDIR /app

# Copy MCP server code
COPY --chown=node:node tools/mcp /app/tools/mcp

# Set Python path
ENV PYTHONPATH=/app

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
CMD ["python", "-m", "tools.mcp.crush.server", "--mode", "http"]
