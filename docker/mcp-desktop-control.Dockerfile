# Multi-stage Rust build for mcp-desktop-control
#
# The X11 backend uses the pure-Rust x11rb protocol implementation, so neither
# the build nor the runtime image needs libX11/libxcb or any X11 CLI tools
# (xdotool, wmctrl, scrot, ...). Only OpenSSL is linked (via mcp-core's HTTP
# client).

# Stage 1: Build the Rust binary
# Use bookworm-based rust image to match runtime glibc version
FROM rust:1.93-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy MCP core framework first (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy desktop control server
COPY tools/mcp/mcp_desktop_control /build/tools/mcp/mcp_desktop_control

# Build the binary
WORKDIR /build/tools/mcp/mcp_desktop_control
RUN cargo build --release

# Stage 2: Minimal runtime image
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user with configurable UID/GID
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} mcp || true && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} mcp || true

# Screenshot output directory (bind-mount it to reach files from the host)
RUN mkdir -p /app /output && \
    chown -R ${USER_ID}:${GROUP_ID} /app /output

WORKDIR /app

COPY --from=builder /build/tools/mcp/mcp_desktop_control/target/release/mcp-desktop-control /usr/local/bin/
RUN chmod +x /usr/local/bin/mcp-desktop-control

ENV RUST_LOG=info \
    DESKTOP_CONTROL_OUTPUT_DIR=/output

USER mcp

# Port for HTTP mode (matches docker-compose.yml)
EXPOSE 8026

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8026/health || exit 1

# Default command - run in HTTP mode. Requires DISPLAY and access to the X
# socket (/tmp/.X11-unix) plus Xauthority; see the crate README.
CMD ["mcp-desktop-control", "--mode", "standalone", "--port", "8026"]
