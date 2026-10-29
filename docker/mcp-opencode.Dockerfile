# Dockerfile for OpenCode MCP Server (Rust)
#
# Multi-stage build:
#   1. Build the `mcp-opencode` Rust binary (talks to OpenRouter over HTTPS;
#      it does not need the opencode CLI at runtime).
#   2. Runtime image. It also ships the upstream `opencode` CLI
#      (github.com/anomalyco/opencode, formerly sst/opencode) at
#      /usr/local/bin/opencode because the `openrouter-agents` image copies it
#      from here (see openrouter-agents.Dockerfile), so that path must stay
#      stable.

# Stage 1: Build the Rust binary
# Use bookworm-based rust image to match runtime glibc version
FROM rust:1.99-slim-bookworm AS builder

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

# Pinned OpenCode CLI release (checksums verified below). The values come from
# the release's SHA256SUMS asset. 2.x is the current major line; 1.19.x only
# receives maintenance releases. The 2.x CLI is self-contained (models catalog
# and provider runtimes are bundled), and `opencode run` talks to a background
# service it starts on demand unless `--standalone` is given.
ARG OPENCODE_VERSION=2.2.1
ARG OPENCODE_CHECKSUM_AMD64=3179551ddf69877ca24a960b0175e94405cf3f52147f1eec705094374bef49f2
ARG OPENCODE_CHECKSUM_ARM64=c354d8a2dc4152308bf286b5ec7f20b3b3cfc71f9476e64f6aa274142505b2f8

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
    curl -fsSL "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-${OC_ARCH}.tar.gz" -o /tmp/opencode.tar.gz; \
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
