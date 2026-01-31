# Dockerfile for GitHub Board MCP Server (Rust)
# Multi-stage build for smaller final image
#
# This server requires the board-manager CLI tool to be available,
# so we build both binaries in this image.

# Stage 1: Build the Rust binaries
FROM rust:1.93-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy MCP core library (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy board-manager (required CLI tool)
COPY tools/rust/board-manager /build/tools/rust/board-manager

# Copy MCP GitHub Board server
COPY tools/mcp/mcp_github_board /build/tools/mcp/mcp_github_board

# Build board-manager first
WORKDIR /build/tools/rust/board-manager
RUN cargo build --release

# Build mcp-github-board
WORKDIR /build/tools/mcp/mcp_github_board
RUN cargo build --release

# Stage 2: Runtime image
# Use trixie-slim to match glibc version from rust:1.93-slim builder
FROM debian:trixie-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3t64 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build arguments for dynamic user creation
ARG USER_ID=1000
ARG GROUP_ID=1000

# Create a user with proper passwd entry (matching host UID/GID)
RUN (getent group ${GROUP_ID} || groupadd -g ${GROUP_ID} boarduser) && \
    (getent passwd ${USER_ID} || useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash boarduser)

# Copy the binaries from builder
COPY --from=builder /build/tools/rust/board-manager/target/release/board-manager /usr/local/bin/board-manager
COPY --from=builder /build/tools/mcp/mcp_github_board/target/release/mcp-github-board /usr/local/bin/mcp-github-board

# Set working directory
WORKDIR /app

# Switch to the created user
USER boarduser

# Default command - stdio mode for MCP clients
CMD ["mcp-github-board", "--mode", "stdio"]
