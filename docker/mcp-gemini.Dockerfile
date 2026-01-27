# Dockerfile for Gemini MCP Server (Rust)
# Multi-stage build for smaller final image

# Stage 1: Build the Rust binary
FROM rust:1.93-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy workspace files
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust
COPY tools/mcp/mcp_gemini /build/tools/mcp/mcp_gemini

# Build the binary
WORKDIR /build/tools/mcp/mcp_gemini
RUN cargo build --release

# Stage 2: Runtime image
FROM debian:bookworm-slim

# Install runtime dependencies and Node.js for Gemini CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    libssl3 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @google/gemini-cli@0.22.4 \
    && rm -rf /var/lib/apt/lists/*

# Build arguments for dynamic user creation
ARG USER_ID=1000
ARG GROUP_ID=1000

# Create a user with proper passwd entry (matching host UID/GID)
# Handle cases where the group/user might already exist
RUN (getent group ${GROUP_ID} || groupadd -g ${GROUP_ID} geminiuser) && \
    (getent passwd ${USER_ID} || useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash geminiuser)

# Copy the binary from builder
COPY --from=builder /build/tools/mcp/mcp_gemini/target/release/mcp-gemini /usr/local/bin/mcp-gemini

# Set working directory
WORKDIR /app

# Switch to the created user
USER geminiuser

# Default command - stdio mode for MCP clients
CMD ["mcp-gemini", "--mode", "stdio"]
