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
# Python 3.13 comes from the deadsnakes PPA into a venv, the same way as
# packages/sleeper_agents/docker/Dockerfile.gpu (Ubuntu itself ships 3.12).
FROM nvidia/cuda:13.0.2-base-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (Python 3.13 from deadsnakes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    ca-certificates \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python3.13 \
    python3.13-venv \
    python3.13-dev \
    build-essential \
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
    && rm -rf /var/lib/apt/lists/*

# Create the non-root user first (dropping the stock ubuntu user that owns
# UID/GID 1000 on 24.04) so the venv and the ComfyUI tree are created owned by
# it. That lets ComfyUI-Manager install node dependencies at runtime without a
# chown -R layer that would duplicate the whole venv in the image.
RUN (userdel -r ubuntu 2>/dev/null || true) && \
    groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 -m appuser && \
    mkdir -p /opt/venv /comfyui /workspace/logs && \
    chown appuser:appuser /opt/venv /comfyui /workspace /workspace/logs

USER appuser

# Run everything from a Python 3.13 virtualenv (pip comes from ensurepip)
RUN python3.13 -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN python3 -m pip install --no-cache-dir --upgrade pip

# Clone ComfyUI pinned to a release (v0.43.1) for reproducibility
ARG COMFYUI_COMMIT=086099f5d8886163ef77dc354f8382cb7431582a
RUN git clone https://github.com/Comfy-Org/ComfyUI.git /comfyui && \
    git -C /comfyui checkout ${COMFYUI_COMMIT}

WORKDIR /comfyui
# Install PyTorch with CUDA 13.0 support (x86_64 only; driver >= 580).
# torchaudio is in maintenance mode and no longer tied to one torch release:
# 2.11.1 on PyPI is built on the stable libtorch ABI and declares torch>=2.11,
# whereas the cu130 index stops at 2.11.0. ComfyUI's audio nodes use it.
# The constraints file keeps every later pip run (requirements, custom nodes,
# ComfyUI-Manager at runtime) from swapping the CUDA build for a PyPI one.
RUN printf '%s\n' \
    "torch==2.14.1+cu130" \
    "torchvision==0.29.1+cu130" \
    "torchaudio==2.11.1" > /opt/venv/torch-constraints.txt && \
    pip install --no-cache-dir \
    torch==2.14.1 \
    torchvision==0.29.1 \
    --index-url https://download.pytorch.org/whl/cu130 && \
    pip install --no-cache-dir torchaudio==2.11.1 && \
    python3 -c "import torch, torchvision, torchaudio; print(f'PyTorch {torch.__version__} with CUDA {torch.version.cuda}, torchvision {torchvision.__version__}, torchaudio {torchaudio.__version__}')"
ENV PIP_CONSTRAINT=/opt/venv/torch-constraints.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install custom nodes, each pinned to a commit. Nodes without a
# requirements.txt (IPAdapter_plus, AnimateDiff-Evolved, WAS) have no pip
# dependencies of their own; WAS lists only optional extras in its CONFIG.md.
# IPAdapter_plus's FaceID models additionally need insightface, which is not
# installed (it builds from source); the regular IPAdapter nodes work without it.
WORKDIR /comfyui/custom_nodes
# ComfyUI-Manager must live in custom_nodes/comfyui-manager (see its README)
ARG COMFYUI_MANAGER_COMMIT=8afdee041650a18e7b66b88a06668c7b684d7c6f
ARG IPADAPTER_PLUS_COMMIT=a0f451a5113cf9becb0847b92884cb10cbdec0ef
ARG ANIMATEDIFF_EVOLVED_COMMIT=9257651221002dcba0a12f9cff37e1944e58fb60
ARG EFFICIENCY_NODES_COMMIT=4579b7d6076b2870998a08f5d37883fbc8261ff2
ARG WAS_NODE_SUITE_COMMIT=7f30cf0f8fa62237900f21772857f1ec8014a538
RUN git clone https://github.com/Comfy-Org/ComfyUI-Manager.git comfyui-manager && \
    git -C comfyui-manager checkout ${COMFYUI_MANAGER_COMMIT} && \
    pip install --no-cache-dir -r comfyui-manager/requirements.txt
RUN git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git && \
    git -C ComfyUI_IPAdapter_plus checkout ${IPADAPTER_PLUS_COMMIT}
RUN git clone https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git && \
    git -C ComfyUI-AnimateDiff-Evolved checkout ${ANIMATEDIFF_EVOLVED_COMMIT}
RUN git clone https://github.com/jags111/efficiency-nodes-comfyui.git && \
    git -C efficiency-nodes-comfyui checkout ${EFFICIENCY_NODES_COMMIT} && \
    pip install --no-cache-dir -r efficiency-nodes-comfyui/requirements.txt
RUN git clone https://github.com/WASasquatch/was-node-suite-comfyui.git && \
    git -C was-node-suite-comfyui checkout ${WAS_NODE_SUITE_COMMIT}

# Fail the build on any broken dependency set
RUN pip check

# Clear the stock model folders: compose bind-mounts each model directory
# from ./comfyui/models on the host instead.
RUN rm -rf /comfyui/models

USER root

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

# Copy entrypoint script
COPY docker/entrypoints/comfyui-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown appuser:appuser /entrypoint.sh

# Expose ports
EXPOSE 8188 8013

# Health check for web UI
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8188/system_stats || exit 1

WORKDIR /comfyui

# Switch to non-root user
USER appuser

# Run entrypoint
CMD ["/entrypoint.sh"]
