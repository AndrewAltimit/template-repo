# Dockerfile for Meme Generator MCP Server (Rust)
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
COPY tools/mcp/mcp_meme_generator /build/tools/mcp/mcp_meme_generator

# Build the binary
WORKDIR /build/tools/mcp/mcp_meme_generator
RUN cargo build --release

# Stage 2: Runtime image
FROM debian:bookworm-slim

# Install runtime dependencies including fonts for meme text
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libssl3 \
    # Fonts for meme text rendering
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Build arguments for dynamic user creation
ARG USER_ID=1000
ARG GROUP_ID=1000

# Create a user with proper passwd entry (matching host UID/GID)
# Handle cases where the group/user might already exist
RUN (getent group ${GROUP_ID} || groupadd -g ${GROUP_ID} memeuser) && \
    (getent passwd ${USER_ID} || useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash memeuser)

# Create output directory with proper permissions
RUN mkdir -p /output && chown -R ${USER_ID}:${GROUP_ID} /output

# Copy the binary from builder
COPY --from=builder /build/tools/mcp/mcp_meme_generator/target/release/mcp-meme-generator /usr/local/bin/mcp-meme-generator

# Copy templates directory
COPY --chown=${USER_ID}:${GROUP_ID} tools/mcp/mcp_meme_generator/templates /app/templates

# Set working directory
WORKDIR /app

# Switch to the created user
USER memeuser

# Expose port
EXPOSE 8016

# Default command - standalone mode with templates
CMD ["mcp-meme-generator", "--mode", "standalone", "--port", "8016", "--templates", "/app/templates", "--output", "/output"]
