# ComfyUI with Web UI and MCP Server (ARM64/aarch64 version)
# Uses NVIDIA NGC PyTorch image which includes CUDA support for ARM64
# Standard pytorch.org wheels only provide CPU builds for ARM64
# Using 25.11 for Blackwell (sm_120/121) support
FROM nvcr.io/nvidia/pytorch:25.11-py3

# Install additional system dependencies
# Note: libgl1-mesa-glx renamed to libgl1 in Ubuntu 24.04+
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Verify PyTorch has CUDA support compiled in (runtime availability checked at startup)
RUN python3 -c "import torch; print(f'PyTorch {torch.__version__} with CUDA {torch.version.cuda}'); assert torch.version.cuda is not None, 'PyTorch not compiled with CUDA'"

# Set working directory
WORKDIR /workspace

# Clone ComfyUI (latest version)
# To pin to a specific version, add: git checkout <commit-hash>
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /comfyui

# Install ComfyUI requirements (excluding torch/torchvision/torchaudio to preserve NGC's CUDA-enabled PyTorch)
WORKDIR /comfyui
RUN grep -vE "^torch$|^torchvision$|^torchaudio$" requirements.txt > requirements-filtered.txt && \
    pip3 install --no-cache-dir -r requirements-filtered.txt && \
    rm requirements-filtered.txt

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
# Note: __init__.py files not needed - packages installed via pip below
COPY tools/mcp/mcp_core /workspace/tools/mcp/mcp_core
COPY tools/mcp/mcp_comfyui /workspace/tools/mcp/mcp_comfyui

# Install MCP packages
RUN pip3 install --no-cache-dir /workspace/tools/mcp/mcp_core &&\
    pip3 install --no-cache-dir /workspace/tools/mcp/mcp_comfyui

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

# Create non-root user (handle case where GID/UID already exists in NGC image)
RUN (groupadd --gid 1000 appuser 2>/dev/null || true) && \
    (useradd --uid 1000 --gid 1000 -m appuser 2>/dev/null || true) && \
    chown -R 1000:1000 /comfyui /workspace

# Copy entrypoint script
COPY docker/entrypoints/comfyui-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown 1000:1000 /entrypoint.sh

# Expose ports
EXPOSE 8188 8013

# Health check for web UI
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8188/system_stats || exit 1

RUN rm -rf /comfyui/models

# Switch to non-root user (use UID for compatibility with NGC base image)
USER 1000

# Run entrypoint
CMD ["/entrypoint.sh"]
