# Dockerfile for Crush MCP Server (Rust)
# Multi-stage build for smaller final image

# Stage 1: Build the Rust binary
# Use bookworm-based rust image to match runtime glibc version
FROM rust:1.93-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy workspace files
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust
COPY tools/mcp/mcp_crush /build/tools/mcp/mcp_crush

# Build the binary
WORKDIR /build/tools/mcp/mcp_crush
RUN cargo build --release

# Stage 2: Runtime image
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Build arguments for dynamic user creation
ARG USER_ID=1000
ARG GROUP_ID=1000

# Create a user with proper passwd entry (matching host UID/GID)
# Handle cases where the group/user might already exist
RUN (getent group ${GROUP_ID} || groupadd -g ${GROUP_ID} crushuser) && \
    (getent passwd ${USER_ID} || useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash crushuser)

# Copy the binary from builder
COPY --from=builder /build/tools/mcp/mcp_crush/target/release/mcp-crush /usr/local/bin/mcp-crush

# Set working directory
WORKDIR /app

# Switch to the created user
USER crushuser

# Default command - stdio mode for MCP clients
CMD ["mcp-crush", "--mode", "stdio"]
