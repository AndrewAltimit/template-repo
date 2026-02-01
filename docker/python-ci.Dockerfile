# syntax=docker/dockerfile:1.4
# Python CI/CD Image with all testing and linting tools
# Performance optimizations:
# - uv package manager (10-100x faster than pip)
# - BuildKit cache mounts for apt and uv
# - Python 3.11 (10-60% faster than 3.10)

# Stage 1: Build gh-validator from source
FROM rust:1.93-slim AS gh-validator-builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY tools/rust/gh-validator/Cargo.toml tools/rust/gh-validator/Cargo.lock* ./
RUN mkdir -p src && echo "fn main() {}" > src/main.rs
RUN cargo build --release 2>/dev/null || true
COPY tools/rust/gh-validator/src ./src
RUN touch src/main.rs && cargo build --release

# Stage 2: Main Python CI image
FROM python:3.11-slim

# Install uv - Rust-based package manager (10-100x faster than pip)
# Using official installer which handles architecture detection
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Configure uv to use system Python (avoids --system flag on every command)
ENV UV_SYSTEM_PYTHON=1

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

# Install gh-validator - shadows system gh via PATH priority
# /usr/local/bin comes before /usr/bin in PATH, so our validator runs first
# The validator finds the real gh at /usr/bin/gh automatically
COPY --from=gh-validator-builder /build/target/release/gh /usr/local/bin/gh
RUN chmod +x /usr/local/bin/gh

# Create working directory
WORKDIR /workspace

# Copy requirements first to leverage Docker layer caching
COPY config/python/requirements.txt ./

# Install all dependencies from the requirements file using uv (with cache)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements.txt

# Install workspace packages
# Note: This happens before copying the full codebase to leverage caching
# The actual code will be mounted at runtime via docker compose volumes
COPY pyproject.toml /app/pyproject.toml
COPY tools /app/tools
COPY automation /app/automation

# Copy main packages
# Note: economic_agents is a Rust package, built separately via rust-ci container
COPY packages/sleeper_agents /app/packages/sleeper_agents

# Install all workspace packages in a single uv command (with cache)
# This is ~10-100x faster than individual pip install commands
# Note: The following are Rust packages, built separately via rust-ci container:
#   - mcp_codex, mcp_reaction_search, mcp_gemini, mcp_crush, mcp_opencode
#   - mcp_code_quality, mcp_content_creation, mcp_meme_generator
#   - mcp_github_board, mcp_elevenlabs_speech, mcp_agentcore_memory
#   - mcp_desktop_control, mcp_blender, mcp_comfyui, mcp_ai_toolkit
#   - mcp_video_editor, mcp_virtual_character, mcp_gaea2, mcp_memory_explorer
#   - mcp_core (Python version deprecated - all MCP servers are now Rust)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install \
    /app/packages/sleeper_agents

# Copy linting configuration files to both /workspace and /app
# Note: Files are copied to both locations to support different tool contexts:
# - /workspace is the primary working directory for most CI operations
# - /app is used by some tools that expect absolute paths or when running
#   with read-only mounts where the code is mounted at /app
COPY .flake8 ./
COPY .flake8 /app/
# Copy pyproject.toml files for proper isort and black configuration
# Duplicated to ensure tools can find configs regardless of working directory
COPY pyproject.toml ./pyproject.toml
COPY pyproject.toml /app/pyproject.toml

# Python environment configuration to prevent cache issues
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUTF8=1

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 ciuser

# Security: gh-validator is installed at /usr/local/bin/gh and shadows /usr/bin/gh
# All gh commands pass through the validator which provides:
# - Secret masking (prevents accidental credential exposure)
# - Unicode emoji blocking (prevents display corruption)
# - Formatting enforcement (requires --body-file for reaction images)
# - URL validation with SSRF protection
# The real gh binary remains at /usr/bin/gh and is found automatically by the validator.

# Default command
CMD ["bash"]
