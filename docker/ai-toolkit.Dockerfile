# AI Toolkit with Web UI and MCP Server
FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    wget \
    ffmpeg \
    libsm6 \
    libxext6 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Clone AI Toolkit (pinned to specific commit for reproducibility)
RUN git clone https://github.com/ostris/ai-toolkit.git /ai-toolkit && \
    cd /ai-toolkit && \
    git checkout be71cc75

# Install AI Toolkit Python dependencies
WORKDIR /ai-toolkit
RUN pip3 install --no-cache-dir -r requirements.txt

# Build and install the Node.js UI
WORKDIR /ai-toolkit/ui
RUN npm install && npm run build

# Install additional dependencies for MCP server
RUN pip3 install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    httpx \
    httpx-sse \
    pydantic \
    pydantic-settings \
    aiofiles \
    psutil \
    jsonschema \
    anyio \
    sse-starlette \
    starlette \
    python-multipart \
    mcp

# Copy only necessary MCP server components for AI Toolkit
COPY tools/__init__.py /workspace/tools/__init__.py
COPY tools/mcp/__init__.py /workspace/tools/mcp/__init__.py
COPY tools/mcp/core /workspace/tools/mcp/core
COPY tools/mcp/ai_toolkit /workspace/tools/mcp/ai_toolkit

# Create directories
RUN mkdir -p /ai-toolkit/datasets \
    /ai-toolkit/outputs \
    /ai-toolkit/configs \
    /workspace/logs

# Environment variables
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
ENV PYTHONUNBUFFERED=1
ENV AI_TOOLKIT_PATH=/ai-toolkit
ENV NODE_ENV=production

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 -m appuser && \
    chown -R appuser:appuser /ai-toolkit /workspace

# Copy entrypoint script
COPY docker/entrypoints/ai-toolkit-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown appuser:appuser /entrypoint.sh

# Expose ports (8675 for Next.js UI, 8012 for MCP)
EXPOSE 8675 8012

# Health check for web UI
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8675/ || exit 1

# Switch to non-root user
USER appuser

# Run entrypoint
CMD ["/entrypoint.sh"]
