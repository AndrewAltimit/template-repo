# Dockerfile for Sprite Sheet MCP Server (Rust)
# Multi-stage build for smaller final image

# Stage 1: Build the Rust binary
FROM rust:1.93-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy workspace files
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust
COPY tools/mcp/mcp_sprite_sheet /build/tools/mcp/mcp_sprite_sheet

# Build the binary
WORKDIR /build/tools/mcp/mcp_sprite_sheet
RUN cargo build --release

# Stage 2: Runtime image
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Build arguments for dynamic user creation
ARG USER_ID=1000
ARG GROUP_ID=1000

# Create a user with proper passwd entry (matching host UID/GID)
RUN (getent group ${GROUP_ID} || groupadd -g ${GROUP_ID} spriteuser) && \
    (getent passwd ${USER_ID} || useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash spriteuser)

# Create output directory with proper permissions
RUN mkdir -p /output && chown -R ${USER_ID}:${GROUP_ID} /output

# Copy the binary from builder
COPY --from=builder /build/tools/mcp/mcp_sprite_sheet/target/release/mcp-sprite-sheet /usr/local/bin/mcp-sprite-sheet

WORKDIR /app

USER spriteuser

EXPOSE 8027

CMD ["mcp-sprite-sheet", "--mode", "standalone", "--port", "8027", "--output", "/output"]
