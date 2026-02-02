# Multi-stage Rust build for mcp-blender with GPU support
# Stage 1: Build the Rust binary
# Use bookworm-based rust image to match runtime glibc version
FROM rust:1.93-slim-bookworm AS builder

# Install build dependencies for OpenSSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy MCP core framework first (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy blender server
COPY tools/mcp/mcp_blender /build/tools/mcp/mcp_blender

# Build the binary
WORKDIR /build/tools/mcp/mcp_blender
RUN cargo build --release

# Stage 2: Runtime image with Blender and CUDA
FROM nvidia/cuda:12.1.1-base-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV BLENDER_VERSION=4.5.1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    xz-utils \
    libxxf86vm1 \
    libgl1-mesa-glx \
    libxi6 \
    libxrender1 \
    libxkbcommon-x11-0 \
    libsm6 \
    libglib2.0-0 \
    libgomp1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download and install Blender
RUN wget -q https://download.blender.org/release/Blender4.5/blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && tar -xf blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && mv blender-${BLENDER_VERSION}-linux-x64 /opt/blender \
    && rm blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && ln -s /opt/blender/blender /usr/local/bin/blender

# Create app user with configurable UID/GID
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} blender || true && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} blender || true

# Create directories
RUN mkdir -p /app /app/projects /app/assets /app/outputs /app/temp /app/templates /app/blender/scripts && \
    chown -R blender:blender /app

WORKDIR /app

# Copy the binary from builder
COPY --from=builder /build/tools/mcp/mcp_blender/target/release/mcp-blender /usr/local/bin/

# Copy Blender scripts
COPY tools/mcp/mcp_blender/scripts /app/blender/scripts

# Set permissions
RUN chmod +x /usr/local/bin/mcp-blender && \
    chown -R blender:blender /app

# Environment variables
ENV RUST_LOG=info
ENV MCP_BLENDER_PROJECT_DIR=/app/projects
ENV MCP_BLENDER_ASSETS_DIR=/app/assets
ENV MCP_BLENDER_OUTPUT_DIR=/app/outputs
ENV MCP_BLENDER_TEMP_DIR=/app/temp
ENV MCP_BLENDER_TEMPLATES_DIR=/app/templates
ENV MCP_BLENDER_SCRIPTS_DIR=/app/blender/scripts

# Switch to non-root user
USER blender

# Expose port
EXPOSE 8017

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8017/health || exit 1

# Default command
CMD ["mcp-blender", "--mode", "standalone", "--port", "8017"]
