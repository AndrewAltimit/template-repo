# Multi-stage Rust build for mcp-desktop-control
# Stage 1: Build the Rust binary
FROM rust:1.93 AS builder

# Install X11 development libraries for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    libx11-dev \
    libxcb1-dev \
    libxkbcommon-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy MCP core framework first (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy desktop control server
COPY tools/mcp/mcp_desktop_control /build/tools/mcp/mcp_desktop_control

# Build the binary
WORKDIR /build/tools/mcp/mcp_desktop_control
RUN cargo build --release

# Stage 2: Runtime image with X11 tools
FROM debian:bookworm-slim

# Install system dependencies for Linux desktop control
RUN apt-get update && apt-get install -y --no-install-recommends \
    # X11 automation tools
    xdotool \
    wmctrl \
    scrot \
    x11-utils \
    xclip \
    # For xrandr
    x11-xserver-utils \
    # ImageMagick for window screenshots
    imagemagick \
    # X11 runtime libraries
    libx11-6 \
    libxcb1 \
    libxkbcommon0 \
    # General utilities
    curl \
    ca-certificates \
    procps \
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
COPY --from=builder /build/tools/mcp/mcp_desktop_control/target/release/mcp-desktop-control /usr/local/bin/

# Set permissions
RUN chmod +x /usr/local/bin/mcp-desktop-control

# Environment variables
ENV RUST_LOG=info

# Switch to non-root user
USER mcp

# Port for HTTP mode
EXPOSE 8025

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8025/health || exit 1

# Default command - run in HTTP mode
CMD ["mcp-desktop-control", "--mode", "standalone", "--port", "8025"]
