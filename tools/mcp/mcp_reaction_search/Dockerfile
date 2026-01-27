# syntax=docker/dockerfile:1.4
# MCP Reaction Search Server - Rust
#
# Multi-stage build for minimal runtime image
#
# Build (from tools/mcp/ directory):
#   docker build -f mcp_reaction_search/Dockerfile -t mcp-reaction-search .
#
# Run modes:
#   Standalone: docker run -p 8024:8024 mcp-reaction-search
#   Server:     docker run -p 8024:8024 mcp-reaction-search --mode server
#   Client:     docker run -p 8024:8024 mcp-reaction-search --mode client --backend-url http://host:port

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM rust:1.85-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy mcp_core_rust (dependency)
COPY mcp_core_rust/Cargo.toml mcp_core_rust/Cargo.lock ./mcp_core_rust/
COPY mcp_core_rust/crates ./mcp_core_rust/crates

# Copy mcp_reaction_search
COPY mcp_reaction_search/Cargo.toml ./mcp_reaction_search/
COPY mcp_reaction_search/src ./mcp_reaction_search/src

# Build release binary
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cd mcp_reaction_search && \
    cargo build --release \
    && cp /app/target/release/mcp-reaction-search /usr/local/bin/

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM debian:bookworm-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash mcp

# Copy binary from builder
COPY --from=builder /usr/local/bin/mcp-reaction-search /usr/local/bin/

# Create cache directory for fastembed models
RUN mkdir -p /home/mcp/.cache && chown -R mcp:mcp /home/mcp/.cache

# Switch to non-root user
USER mcp
WORKDIR /home/mcp

# Default port
EXPOSE 8024

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8024/health || exit 1

# Default to standalone mode
ENTRYPOINT ["mcp-reaction-search"]
CMD ["--mode", "standalone", "--port", "8024"]
