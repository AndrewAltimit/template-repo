# syntax=docker/dockerfile:1.4
# MCP Gaea2 Server - Rust
#
# Multi-stage build for minimal runtime image
#
# Build (from repo root directory):
#   docker build -f docker/mcp-gaea2.Dockerfile -t mcp-gaea2 .
#
# Run modes:
#   Standalone: docker run -p 8007:8007 mcp-gaea2
#   Server:     docker run -p 8007:8007 mcp-gaea2 --mode server
#   Client:     docker run -p 8007:8007 mcp-gaea2 --mode client --backend-url http://host:port
#
# Note: CLI automation features require Windows host with Gaea2 installed.
#       Container provides project creation, validation, and template generation.

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM rust:1.93-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy mcp_core_rust (dependency)
COPY tools/mcp/mcp_core_rust/Cargo.toml tools/mcp/mcp_core_rust/Cargo.lock ./tools/mcp/mcp_core_rust/
COPY tools/mcp/mcp_core_rust/crates ./tools/mcp/mcp_core_rust/crates

# Copy mcp_gaea2
COPY tools/mcp/mcp_gaea2/Cargo.toml ./tools/mcp/mcp_gaea2/
COPY tools/mcp/mcp_gaea2/src ./tools/mcp/mcp_gaea2/src

# Build release binary
# Use CARGO_TARGET_DIR to put output in /app/target for caching
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cd tools/mcp/mcp_gaea2 && \
    CARGO_TARGET_DIR=/app/target cargo build --release \
    && cp /app/target/release/mcp-gaea2 /usr/local/bin/

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

# Create output directory for generated projects
RUN mkdir -p /output/gaea2 && chown -R mcp:mcp /output

# Copy binary from builder
COPY --from=builder /usr/local/bin/mcp-gaea2 /usr/local/bin/

# Switch to non-root user
USER mcp
WORKDIR /home/mcp

# Default port (matches existing compose configuration)
EXPOSE 8007

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8007/health || exit 1

# Default to standalone mode
ENTRYPOINT ["mcp-gaea2"]
CMD ["--mode", "standalone", "--port", "8007", "--output-dir", "/output/gaea2"]
