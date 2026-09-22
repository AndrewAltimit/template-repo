# Multi-stage Rust build for mcp-agentcore-memory
#
# Build context: repository root (see docker-compose.yml service
# `mcp-agentcore-memory`).
#
# The embedding model (all-MiniLM-L6-v2, ~90 MB) is downloaded at build time
# and baked into the image, so containers started with `--rm` (as .mcp.json
# does) never need network access to Hugging Face at runtime.

# Stage 1: Build the Rust binary
# Use bookworm-based rust image to match runtime glibc version
FROM rust:1.93-slim-bookworm AS builder

# pkg-config/libssl-dev: reqwest native-tls; g++: libstdc++ for ONNX Runtime;
# ca-certificates: model and ONNX Runtime downloads during the build
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    g++ \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy MCP core framework first (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy agentcore-memory server
COPY tools/mcp/mcp_agentcore_memory /build/tools/mcp/mcp_agentcore_memory

# Build the binary
WORKDIR /build/tools/mcp/mcp_agentcore_memory
RUN cargo build --release

# Pre-download the embedding model into a fixed location
RUN MEMORY_MODEL_CACHE_DIR=/opt/mcp-agentcore-memory/models \
    ./target/release/mcp-agentcore-memory --prefetch-model

# Stage 2: Runtime image
FROM debian:bookworm-slim

# curl: health check; libssl3/ca-certificates: TLS to ChromaDB (https URLs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Create app user with configurable UID/GID
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} mcp || true && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} mcp || true

# Create directories
RUN mkdir -p /app && \
    chown -R mcp:mcp /app

WORKDIR /app

# Copy the binary and the pre-downloaded model (world-readable, so any
# `user:` override in docker-compose can load it)
COPY --from=builder /build/tools/mcp/mcp_agentcore_memory/target/release/mcp-agentcore-memory /usr/local/bin/
COPY --from=builder /opt/mcp-agentcore-memory/models /opt/mcp-agentcore-memory/models
RUN chmod +x /usr/local/bin/mcp-agentcore-memory && \
    chmod -R a+rX /opt/mcp-agentcore-memory

# Environment variables (all overridable; see the crate README)
ENV RUST_LOG=info
ENV CHROMADB_HOST=chromadb
ENV CHROMADB_PORT=8000
ENV MEMORY_MODEL_CACHE_DIR=/opt/mcp-agentcore-memory/models

# Switch to non-root user
USER mcp

# Expose port for HTTP mode
EXPOSE 8023

# Health check (only works when running in standalone mode, not stdio)
# When using docker-compose with --mode standalone, this health check is active
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8023/health || exit 1

# Default command - run in STDIO mode for Claude Code integration
# Note: Health check will fail in stdio mode (expected behavior)
CMD ["mcp-agentcore-memory", "--mode", "stdio"]
