# Unified Codex Dockerfile
# Supports both codex-agent (CLI) and mcp-codex (MCP server) modes
# Build with: docker build --build-arg MODE=agent (or MODE=mcp)

ARG MODE=agent

# Stage 1: Build gh-validator from source
FROM rust:1.85-slim AS gh-validator-builder

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

# Stage 2: Build mcp-codex Rust server
FROM rust:1.85-slim AS mcp-codex-builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy Cargo files first for dependency caching
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust
COPY tools/mcp/mcp_codex/Cargo.toml tools/mcp/mcp_codex/Cargo.lock* /build/tools/mcp/mcp_codex/

# Create dummy source file for dependency compilation
WORKDIR /build/tools/mcp/mcp_codex
RUN mkdir -p src && echo "fn main() {}" > src/main.rs
RUN cargo build --release 2>/dev/null || true

# Copy actual source and rebuild
COPY tools/mcp/mcp_codex/src ./src
RUN touch src/main.rs && cargo build --release

# Stage 3: Main Codex image
# Use Python as base since both modes need it
FROM python:3.11-slim

# Install Node.js 20 and system dependencies in a single layer
RUN apt-get update && apt-get install -y \
    curl \
    git \
    wget \
    jq \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI (for agent operations)
RUN wget -q -O- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /usr/share/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install gh-validator - shadows system gh via PATH priority
# /usr/local/bin comes before /usr/bin in PATH, so our validator runs first
# The validator finds the real gh at /usr/bin/gh automatically
COPY --from=gh-validator-builder /build/target/release/gh /usr/local/bin/gh
RUN chmod +x /usr/local/bin/gh

# Install mcp-codex Rust binary
COPY --from=mcp-codex-builder /build/tools/mcp/mcp_codex/target/release/mcp-codex /usr/local/bin/mcp-codex
RUN chmod +x /usr/local/bin/mcp-codex

# Install Codex CLI globally (pinned version for reproducibility)
RUN npm install -g @openai/codex@0.79.0

# Create non-root user with consistent UID
RUN useradd -m -u 1000 user && \
    mkdir -p /home/user/.codex \
             /home/user/.config \
             /home/user/.cache \
             /home/user/.local/share \
             /home/user/.local/bin && \
    chown -R user:user /home/user

# Set working directory
WORKDIR /workspace

# Security: gh-validator is installed at /usr/local/bin/gh and shadows /usr/bin/gh
# All gh commands pass through the validator which provides:
# - Secret masking (prevents accidental credential exposure)
# - Unicode emoji blocking (prevents display corruption)
# - Formatting enforcement (requires --body-file for reaction images)
# - URL validation with SSRF protection
# The real gh binary remains at /usr/bin/gh and is found automatically by the validator.

# Copy entrypoint script
COPY docker/scripts/codex-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create runtime directories
RUN mkdir -p /tmp/codex-runtime && \
    chown -R user:user /tmp/codex-runtime /workspace

# Set environment variables
ENV NODE_ENV=production \
    HOME=/home/user \
    PATH="/home/user/.local/bin:${PATH}"

# Switch to non-root user
USER user

# Use entrypoint script to handle mode logic
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Default command (can be overridden)
CMD []
