# syntax=docker/dockerfile:1.4
# Python CI/CD Image with all testing and linting tools
# Performance optimizations:
# - uv package manager (10-100x faster than pip)
# - BuildKit cache mounts for apt and uv
# - Python 3.11 (10-60% faster than 3.10)
FROM python:3.11-slim

# Install uv - Rust-based package manager (10-100x faster than pip)
# Using official installer which handles architecture detection
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install system dependencies with BuildKit cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    ffmpeg \
    shellcheck \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI with BuildKit cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /workspace

# Copy requirements first to leverage Docker layer caching
COPY config/python/requirements.txt ./

# Install all dependencies from the requirements file using uv (with cache)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

# Install workspace packages
# Note: This happens before copying the full codebase to leverage caching
# The actual code will be mounted at runtime via docker-compose volumes
COPY pyproject.toml /app/pyproject.toml
COPY tools /app/tools
COPY automation /app/automation

# Copy main packages
COPY packages/github_agents /app/packages/github_agents
COPY packages/sleeper_agents /app/packages/sleeper_agents
COPY packages/economic_agents /app/packages/economic_agents

# Install all workspace packages in a single uv command (with cache)
# This is ~10-100x faster than individual pip install commands
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system \
    /app/tools/mcp/mcp_core \
    /app/tools/mcp/mcp_ai_toolkit \
    /app/tools/mcp/mcp_blender \
    /app/tools/mcp/mcp_code_quality \
    /app/tools/mcp/mcp_codex \
    /app/tools/mcp/mcp_comfyui \
    /app/tools/mcp/mcp_content_creation \
    /app/tools/mcp/mcp_crush \
    /app/tools/mcp/mcp_elevenlabs_speech \
    /app/tools/mcp/mcp_gaea2 \
    /app/tools/mcp/mcp_gemini \
    /app/tools/mcp/mcp_github_board \
    /app/tools/mcp/mcp_meme_generator \
    /app/tools/mcp/mcp_opencode \
    /app/tools/mcp/mcp_video_editor \
    /app/tools/mcp/mcp_virtual_character \
    /app/packages/github_agents \
    /app/packages/sleeper_agents \
    /app/packages/economic_agents

# Copy linting configuration files to both /workspace and /app
# Note: Files are copied to both locations to support different tool contexts:
# - /workspace is the primary working directory for most CI operations
# - /app is used by some tools that expect absolute paths or when running
#   with read-only mounts where the code is mounted at /app
COPY .flake8 .pylintrc ./
COPY .flake8 .pylintrc /app/
# Copy pyproject.toml files for proper isort and black configuration
# Duplicated to ensure tools can find configs regardless of working directory
COPY pyproject.toml ./pyproject.toml
COPY pyproject.toml /app/pyproject.toml
# Create directory structure for package configs
RUN mkdir -p packages/github_agents /app/packages/github_agents
COPY packages/github_agents/pyproject.toml ./packages/github_agents/
COPY packages/github_agents/pyproject.toml /app/packages/github_agents/

# Python environment configuration to prevent cache issues
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 ciuser

# Copy security hooks and set up universal gh alias
COPY automation/security /app/security
RUN chmod +x /app/security/*.sh && \
    echo 'alias gh="/app/security/gh-wrapper.sh"' >> /etc/bash.bashrc

# Default command
CMD ["bash"]
