# ComfyUI with Web UI and MCP Server
FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgoogle-perftools4 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Clone ComfyUI (pinned to specific commit for reproducibility)
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui && \
    cd /comfyui && \
    git checkout 20a84166

# Install ComfyUI requirements
WORKDIR /comfyui
RUN pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
RUN pip3 install --no-cache-dir -r requirements.txt

# Install custom nodes (using latest versions)
WORKDIR /comfyui/custom_nodes
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    pip3 install --no-cache-dir -r requirements.txt
RUN git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git && \
    cd ComfyUI_IPAdapter_plus && \
    pip3 install --no-cache-dir -r requirements.txt || true
RUN git clone https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git
RUN git clone https://github.com/jags111/efficiency-nodes-comfyui.git
RUN git clone https://github.com/WASasquatch/was-node-suite-comfyui.git

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
    websocket-client \
    jsonschema \
    anyio \
    sse-starlette \
    starlette \
    python-multipart \
    mcp

# Copy only necessary MCP server components for ComfyUI
COPY tools/__init__.py /workspace/tools/__init__.py
COPY tools/mcp/__init__.py /workspace/tools/mcp/__init__.py
COPY tools/mcp/core /workspace/tools/mcp/core
COPY tools/mcp/comfyui /workspace/tools/mcp/comfyui

# Create directories
RUN mkdir -p /comfyui/models/checkpoints \
    /comfyui/models/vae \
    /comfyui/models/loras \
    /comfyui/models/embeddings \
    /comfyui/models/controlnet \
    /comfyui/output \
    /comfyui/input \
    /workspace/logs

# Environment variables
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
ENV PYTHONUNBUFFERED=1
ENV COMFYUI_PATH=/comfyui
ENV COMFYUI_DISABLE_XFORMERS=0

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 -m appuser && \
    chown -R appuser:appuser /comfyui /workspace

# Copy entrypoint script
COPY docker/entrypoints/comfyui-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown appuser:appuser /entrypoint.sh

# Expose ports
EXPOSE 8188 8013

# Health check for web UI
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8188/system_stats || exit 1

# Switch to non-root user
USER appuser

# Run entrypoint
CMD ["/entrypoint.sh"]
