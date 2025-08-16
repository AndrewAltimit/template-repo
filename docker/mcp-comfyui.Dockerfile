# ComfyUI MCP Server with GPU support
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
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone ComfyUI (if needed for integration)
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /comfyui || true

# Copy requirements
COPY docker/requirements-comfyui.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy the MCP server code
COPY tools/mcp /app/tools/mcp
COPY config /app/config

# Create output directories
RUN mkdir -p /comfyui/models /comfyui/output /comfyui/input /app/logs

# Environment variables for GPU
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
ENV PYTHONUNBUFFERED=1
ENV PORT=8013
ENV COMFYUI_PATH=/comfyui

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Default command to run the MCP server
CMD ["python3", "-m", "tools.mcp.comfyui.server", "--mode", "http", "--host", "0.0.0.0"]
