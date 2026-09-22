# Dockerfile for OpenCode MCP Server (Rust)
#
# Multi-stage build:
#   1. Build the `mcp-opencode` Rust binary (talks to OpenRouter over HTTPS;
#      it does not need the opencode CLI at runtime).
#   2. Runtime image. It also ships the upstream `opencode` CLI (sst/opencode)
#      at /usr/local/bin/opencode because the `openrouter-agents` image copies
#      it from here (see openrouter-agents.Dockerfile), so that path must stay
#      stable.

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
COPY tools/mcp/mcp_opencode /build/tools/mcp/mcp_opencode

# Build the binary
WORKDIR /build/tools/mcp/mcp_opencode
RUN cargo build --release

# Stage 2: Runtime image
FROM debian:bookworm-slim

# Pinned OpenCode CLI release (checksums verified below).
ARG OPENCODE_VERSION=1.0.223
ARG OPENCODE_CHECKSUM_AMD64=6c1bf6114a0b08fdb4c15ceef9da4480df0297699e045db7dd9a2950b0b9cc09
ARG OPENCODE_CHECKSUM_ARM64=e6549b392ea52842a995da5eae4d35209df605066613b71e7883457d8ecaee9b

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Install the OpenCode CLI from the pinned GitHub release, verifying its checksum.
RUN set -eu; \
    ARCH="$(dpkg --print-architecture)"; \
    case "$ARCH" in \
        amd64) OC_ARCH="x64"; CHECKSUM="${OPENCODE_CHECKSUM_AMD64}" ;; \
        arm64) OC_ARCH="arm64"; CHECKSUM="${OPENCODE_CHECKSUM_ARM64}" ;; \
        *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/sst/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-${OC_ARCH}.tar.gz" -o /tmp/opencode.tar.gz; \
    echo "${CHECKSUM}  /tmp/opencode.tar.gz" | sha256sum -c -; \
    tar --no-same-owner -xzf /tmp/opencode.tar.gz -C /usr/local/bin/ opencode; \
    chmod 0755 /usr/local/bin/opencode; \
    rm /tmp/opencode.tar.gz

# Build arguments for dynamic user creation
ARG USER_ID=1000
ARG GROUP_ID=1000

# Create a user with proper passwd entry (matching host UID/GID)
# Handle cases where the group/user might already exist
RUN (getent group ${GROUP_ID} || groupadd -g ${GROUP_ID} opencodeuser) && \
    (getent passwd ${USER_ID} || useradd -m -u ${USER_ID} -g ${GROUP_ID} -s /bin/bash opencodeuser)

# Copy the MCP server binary from builder
COPY --from=builder /build/tools/mcp/mcp_opencode/target/release/mcp-opencode /usr/local/bin/mcp-opencode

# Set working directory
WORKDIR /app

# Switch to the created user
USER ${USER_ID}:${GROUP_ID}

# Default command - stdio mode for MCP clients
CMD ["mcp-opencode", "--mode", "stdio"]
