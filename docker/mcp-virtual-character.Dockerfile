# MCP Virtual Character Server Docker Image (Rust)
#
# IMPORTANT: This container runs the middleware MCP server only.
# VRChat itself must run on a Windows machine with GPU (cannot be containerized).
# This server communicates with VRChat via OSC protocol to a remote Windows host.
#
# Multi-stage build for minimal image size

# Stage 1: Build the Rust binary
FROM rust:1.86-slim AS builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy the mcp-core crate first for caching
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy the virtual character crate
COPY tools/mcp/mcp_virtual_character /build/tools/mcp/mcp_virtual_character

# Build the binary
WORKDIR /build/tools/mcp/mcp_virtual_character
RUN cargo build --release

# Stage 2: Runtime image
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy the binary from the builder
COPY --from=builder /build/tools/mcp/mcp_virtual_character/target/release/mcp-virtual-character /usr/local/bin/

# Create non-root user
RUN useradd -m -u 1000 mcp-user
USER mcp-user

# Environment variables
ENV VIRTUAL_CHARACTER_HOST=127.0.0.1
ENV VIRTUAL_CHARACTER_OSC_IN=9000
ENV VIRTUAL_CHARACTER_OSC_OUT=9001

# Expose the server port (8025 is the default MCP port for virtual character)
EXPOSE 8025

# Health check is defined in docker-compose.yml for consistency

# Run the server in standalone HTTP mode by default
ENTRYPOINT ["mcp-virtual-character"]
CMD ["--mode", "standalone", "--port", "8025"]
