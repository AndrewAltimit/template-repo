# Multi-stage build for ComfyUI with Rust MCP server (x86_64 version)
# For ARM64 systems, use comfyui-arm64.Dockerfile instead

# Stage 1: Build the Rust MCP binary
# Use bookworm-based rust image to match runtime glibc version
FROM rust:1.99-slim-bookworm AS builder

# Install build dependencies for OpenSSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy MCP core framework first (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy comfyui server
COPY tools/mcp/mcp_comfyui /build/tools/mcp/mcp_comfyui

# Build the binary
WORKDIR /build/tools/mcp/mcp_comfyui
RUN cargo build --release

# Stage 2: Runtime image with ComfyUI and CUDA
# CUDA 13.0 matches the cu130 PyTorch wheels below (host driver >= 580 required).
# Ubuntu 24.04 provides Python 3.12; jammy's 3.10 is no longer covered by current torch.
FROM nvidia/cuda:13.0.2-base-ubuntu24.04

# Container-only interpreter: allow pip to install into the system Python (PEP 668)
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    wget \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgoogle-perftools4t64 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Clone ComfyUI (latest version)
# To pin to a specific version, add: git checkout <commit-hash>
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /comfyui

# Install ComfyUI requirements
WORKDIR /comfyui
# Install PyTorch with CUDA 13.0 support (x86_64 only; driver >= 580). torchaudio is
# left out: the newest on the cu130 index is 2.11.0, built against torch 2.11, and
# ComfyUI does not require it.
RUN pip3 install --no-cache-dir \
    torch==2.14.1 \
    torchvision==0.29.1 \
    --index-url https://download.pytorch.org/whl/cu130 && \
    python3 -c "import torch; print(f'PyTorch {torch.__version__} with CUDA {torch.version.cuda}')"
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

# Create directories
RUN mkdir -p /comfyui/models/checkpoints \
    /comfyui/models/vae \
    /comfyui/models/loras \
    /comfyui/models/embeddings \
    /comfyui/models/controlnet \
    /comfyui/output \
    /comfyui/input \
    /workspace/logs

# Copy the Rust MCP binary from builder
COPY --from=builder /build/tools/mcp/mcp_comfyui/target/release/mcp-comfyui /usr/local/bin/
RUN chmod +x /usr/local/bin/mcp-comfyui

# Environment variables
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
ENV PYTHONUNBUFFERED=1
ENV COMFYUI_PATH=/comfyui
ENV COMFYUI_DISABLE_XFORMERS=0
ENV RUST_LOG=info
ENV COMFYUI_URL=http://localhost:8188

# Create non-root user (drop the stock ubuntu user that owns UID/GID 1000 on 24.04)
RUN (userdel -r ubuntu 2>/dev/null || true) && \
    groupadd --gid 1000 appuser && \
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

RUN rm -rf /comfyui/models

# Switch to non-root user
USER appuser

# Run entrypoint
CMD ["/entrypoint.sh"]
