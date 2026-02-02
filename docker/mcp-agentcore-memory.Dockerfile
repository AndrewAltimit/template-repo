# Multi-stage Rust build for mcp-agentcore-memory
# Stage 1: Build the Rust binary
FROM rust:1.93 AS builder

WORKDIR /build

# Copy MCP core framework first (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy agentcore-memory server
COPY tools/mcp/mcp_agentcore_memory /build/tools/mcp/mcp_agentcore_memory

# Build the binary
WORKDIR /build/tools/mcp/mcp_agentcore_memory
RUN cargo build --release

# Stage 2: Runtime image
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
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

# Copy the binary from builder
COPY --from=builder /build/tools/mcp/mcp_agentcore_memory/target/release/mcp-agentcore-memory /usr/local/bin/

# Set permissions
RUN chmod +x /usr/local/bin/mcp-agentcore-memory

# Environment variables
ENV RUST_LOG=info
ENV CHROMADB_URL=http://chromadb:8000

# Switch to non-root user
USER mcp

# Expose port for HTTP mode
EXPOSE 8023

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8023/health || exit 1

# Default command - run in STDIO mode for Claude Code integration
CMD ["mcp-agentcore-memory", "--mode", "stdio"]
