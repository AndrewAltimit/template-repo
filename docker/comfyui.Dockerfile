# Full ComfyUI with Web UI and MCP Server
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

# Clone ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui

# Install ComfyUI requirements
WORKDIR /comfyui
RUN pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
RUN pip3 install --no-cache-dir -r requirements.txt

# Install custom nodes
WORKDIR /comfyui/custom_nodes
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && pip3 install --no-cache-dir -r requirements.txt
RUN git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git && \
    cd ComfyUI_IPAdapter_plus && pip3 install --no-cache-dir -r requirements.txt || true
RUN git clone https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git
RUN git clone https://github.com/jags111/efficiency-nodes-comfyui.git
RUN git clone https://github.com/WASasquatch/was-node-suite-comfyui.git

# Install additional dependencies for MCP server
RUN pip3 install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    httpx \
    pydantic \
    aiofiles \
    psutil \
    websocket-client \
    mcp

# Copy entire tools directory to maintain proper Python module structure
COPY tools /workspace/tools

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

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Start ComfyUI web UI in background\n\
echo "Starting ComfyUI Web UI on port 8188..."\n\
cd /comfyui\n\
python3 main.py --listen 0.0.0.0 --port 8188 --highvram &\n\
COMFYUI_PID=$!\n\
\n\
# Give the web UI time to start\n\
sleep 10\n\
\n\
# Start MCP server\n\
echo "Starting ComfyUI MCP Server on port 8189..."\n\
cd /workspace\n\
python3 -m tools.mcp.comfyui.server --mode http --host 0.0.0.0 --port 8189 &\n\
MCP_PID=$!\n\
\n\
# Keep container running and handle shutdown\n\
trap "kill $COMFYUI_PID $MCP_PID; exit" SIGTERM SIGINT\n\
\n\
echo "ComfyUI Web UI: http://0.0.0.0:8188"\n\
echo "ComfyUI MCP Server: http://0.0.0.0:8189"\n\
\n\
# Wait for processes\n\
wait $COMFYUI_PID $MCP_PID\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

# Expose ports
EXPOSE 8188 8189

# Health check for web UI
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8188/system_stats || exit 1

# Run entrypoint
CMD ["/entrypoint.sh"]
