# AI Toolkit with Web UI and MCP Server (Rust)
# Stage 1: Build Rust MCP server
# Use bookworm-based rust image to match runtime glibc version
FROM rust:1.99-slim-bookworm AS mcp-builder

# Install OpenSSL for reqwest
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy MCP core first for dependency caching
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy AI Toolkit MCP server
COPY tools/mcp/mcp_ai_toolkit /build/tools/mcp/mcp_ai_toolkit

# Build the MCP server
WORKDIR /build/tools/mcp/mcp_ai_toolkit
RUN cargo build --release

# Stage 2: Runtime image
# CUDA 13.0 matches the cu130 PyTorch wheels below (host driver >= 580 required).
# Python 3.13 comes from the deadsnakes PPA into a venv, the same way as
# packages/sleeper_agents/docker/Dockerfile.gpu (Ubuntu itself ships 3.12).
FROM nvidia/cuda:13.0.2-base-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (Python 3.13 from deadsnakes, Node.js 24 as
# upstream's own Dockerfile uses). libgl1/libglib2.0-0 are needed by the
# opencv-python wheel that the requirements pull in.
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
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# npm is upgraded within the 11.x line: the bundled copy vendors undici and
# brace-expansion releases with HIGH advisories (same as the other node images)
RUN npm install -g npm@11.21.1 && node --version && npm --version

# Create the non-root user first (dropping the stock ubuntu user that owns
# UID/GID 1000 on 24.04) so the venv and the AI Toolkit tree are created owned
# by it; the UI writes its SQLite DB inside /ai-toolkit at runtime. This avoids
# a chown -R layer that would duplicate the venv and node_modules in the image.
RUN (userdel -r ubuntu 2>/dev/null || true) && \
    groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 -m appuser && \
    mkdir -p /opt/venv /ai-toolkit /workspace/logs && \
    chown appuser:appuser /opt/venv /ai-toolkit /workspace /workspace/logs

USER appuser

# Run everything from a Python 3.13 virtualenv (pip comes from ensurepip). The
# venv also provides the `python` name the UI uses to launch training jobs.
RUN python3.13 -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN python3 -m pip install --no-cache-dir --upgrade pip

# Clone AI Toolkit (pinned to specific commit for reproducibility)
ARG AI_TOOLKIT_COMMIT=b69b98314557f7c8b08e11bbb14e48d959e6ab26
RUN git clone https://github.com/ostris/ai-toolkit.git /ai-toolkit && \
    git -C /ai-toolkit checkout ${AI_TOOLKIT_COMMIT}

WORKDIR /ai-toolkit

# PyTorch with CUDA 13.0 support, installed before the requirements and then
# held in place by a constraints file (upstream's manager/spec.py does the same),
# so no later pip run can swap the CUDA build for a PyPI one. Upstream pins
# torch 2.13.0 on Python 3.12; this image uses the repo-wide torch 2.14.1 on
# Python 3.13. torchaudio is in maintenance mode and torch-version-agnostic:
# 2.11.1 on PyPI declares torch>=2.11 (the cu130 index stops at 2.11.0).
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

# Install AI Toolkit Python dependencies. requirements.txt pins scipy==1.12.0,
# which has no Python 3.13 wheels and does not build on 3.13; it is dropped
# here so scipy resolves to a current release (`pip check` below stays clean).
# (The filtered copy sits next to the original so its `-r requirements_base.txt`
# include still resolves.)
RUN grep -vE '^scipy==' requirements.txt > requirements-py313.txt && \
    pip install --no-cache-dir -r requirements-py313.txt && \
    rm requirements-py313.txt

# Accelerators from upstream's manager/spec.py linux cu130 set, rebuilt for
# torch 2.14 / cp313: flash-attn 2.8.3 (mjun0812 prebuilt wheel for
# cu130 + torch 2.14 + cp313) and flash-linear-attention 0.5.2 (pure Python;
# installed bare so it cannot upgrade the pinned transformers). NATTEN is left
# out: whl.natten.org only has 0.21.7 builds for torch 2.12 and 2.13, and
# upstream treats it as optional.
RUN pip install --no-cache-dir \
    https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.10.0/flash_attn-2.8.3+cu130torch2.14-cp313-cp313-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl \
    flash-linear-attention==0.5.2 && \
    python3 -c "import flash_attn, fla, torchcodec, transformers; print('accelerators OK: flash_attn', flash_attn.__version__, 'fla', fla.__version__, 'torchcodec', torchcodec.__version__, 'transformers', transformers.__version__)"

# Fail the build on any broken dependency set
RUN pip check

# Build and install the Node.js UI. update_db runs `prisma generate` (the TS
# build needs the generated client) and creates the SQLite job database.
WORKDIR /ai-toolkit/ui
RUN npm ci && npm run update_db && npm run build

# Create directories
RUN mkdir -p /ai-toolkit/datasets \
    /ai-toolkit/outputs \
    /ai-toolkit/configs

USER root

# Copy the Rust MCP server binary
COPY --from=mcp-builder /build/tools/mcp/mcp_ai_toolkit/target/release/mcp-ai-toolkit /usr/local/bin/mcp-ai-toolkit
RUN chmod +x /usr/local/bin/mcp-ai-toolkit

# Environment variables
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
ENV PYTHONUNBUFFERED=1
ENV AI_TOOLKIT_PATH=/ai-toolkit
ENV NODE_ENV=production

# Copy entrypoint script
COPY docker/entrypoints/ai-toolkit-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown appuser:appuser /entrypoint.sh

# Expose ports (8675 for Next.js UI, 8020 for MCP)
EXPOSE 8675 8020

# Health check for web UI
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8675/ || exit 1

WORKDIR /workspace

# Switch to non-root user
USER appuser

# Run entrypoint
CMD ["/entrypoint.sh"]
