# Dockerfile for Crush MCP Server (Rust)
#
# Multi-stage build:
#   1. Build the `mcp-crush` Rust binary.
#   2. Runtime image containing BOTH `mcp-crush` and the upstream `crush` CLI
#      (charmbracelet/crush). The MCP server shells out to `crush run`, so the
#      CLI must be present in this image. The `openrouter-agents` image also
#      copies /usr/local/bin/crush from here (see openrouter-agents.Dockerfile),
#      so the CLI path must stay stable.

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

# Pinned Crush CLI release (checksums verified below).
ARG CRUSH_VERSION=0.30.0
ARG CRUSH_CHECKSUM_AMD64=8497f7ed533e93ec27d478afeca33e1157faafb83c37ea2d5dbdaa2dee9abd1d
ARG CRUSH_CHECKSUM_ARM64=810673903482180dc37e04254c61edf770383c0d927de10783fd42fed6e2e770

# Install runtime dependencies (git is used by crush for repo awareness)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Install the Crush CLI from the pinned GitHub release, verifying its checksum.
RUN set -eu; \
    ARCH="$(dpkg --print-architecture)"; \
    case "$ARCH" in \
        amd64) CRUSH_ARCH="x86_64"; CHECKSUM="${CRUSH_CHECKSUM_AMD64}" ;; \
        arm64) CRUSH_ARCH="arm64"; CHECKSUM="${CRUSH_CHECKSUM_ARM64}" ;; \
        *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/charmbracelet/crush/releases/download/v${CRUSH_VERSION}/crush_${CRUSH_VERSION}_Linux_${CRUSH_ARCH}.tar.gz" -o /tmp/crush.tar.gz; \
    echo "${CHECKSUM}  /tmp/crush.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/crush.tar.gz -C /tmp; \
    install -m 0755 "/tmp/crush_${CRUSH_VERSION}_Linux_${CRUSH_ARCH}/crush" /usr/local/bin/crush; \
    rm -rf /tmp/crush.tar.gz "/tmp/crush_${CRUSH_VERSION}_Linux_${CRUSH_ARCH}"; \
    crush --version

# Build arguments for dynamic user creation
ARG USER_ID=1000
ARG GROUP_ID=1000

# Create a user with proper passwd entry (matching host UID/GID)
# Handle cases where the group/user might already exist
RUN (getent group ${GROUP_ID} || groupadd -g ${GROUP_ID} crushuser) && \
    (getent passwd ${USER_ID} || useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash crushuser)

# Writable state for the crush CLI. The repository is usually mounted
# read-only at /app, so crush's data directory and HOME must live elsewhere.
RUN mkdir -p /var/lib/mcp-crush/home /var/lib/mcp-crush/data /var/lib/mcp-crush/workspace && \
    chown -R ${USER_ID}:${GROUP_ID} /var/lib/mcp-crush

ENV HOME=/var/lib/mcp-crush/home \
    CRUSH_DATA_DIR=/var/lib/mcp-crush/data \
    CRUSH_WORKDIR=/var/lib/mcp-crush/workspace \
    CRUSH_EXECUTION=local

# Copy the MCP server binary from builder
COPY --from=builder /build/tools/mcp/mcp_crush/target/release/mcp-crush /usr/local/bin/mcp-crush

# Set working directory
WORKDIR /app

# Switch to the created user
USER ${USER_ID}:${GROUP_ID}

# Default command - stdio mode for MCP clients
CMD ["mcp-crush", "--mode", "stdio"]
