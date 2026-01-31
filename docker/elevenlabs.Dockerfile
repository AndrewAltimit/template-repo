# ElevenLabs Speech MCP Server Container (Rust)
# Multi-stage build for minimal final image

# Stage 1: Build the Rust binary
FROM rust:1.93-slim AS builder

RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy mcp-core dependency first for caching
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy Cargo files for dependency caching
COPY tools/mcp/mcp_elevenlabs_speech/Cargo.toml tools/mcp/mcp_elevenlabs_speech/Cargo.lock* /build/tools/mcp/mcp_elevenlabs_speech/

# Create dummy source file for dependency compilation
WORKDIR /build/tools/mcp/mcp_elevenlabs_speech
RUN mkdir -p src && echo "fn main() {}" > src/main.rs
RUN cargo build --release 2>/dev/null || true

# Copy actual source and rebuild
COPY tools/mcp/mcp_elevenlabs_speech/src ./src
RUN touch src/main.rs && cargo build --release

# Stage 2: Final minimal image
FROM debian:bookworm-slim

# Install runtime dependencies (SSL for HTTPS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 mcp

WORKDIR /app

# Copy the binary from builder
COPY --from=builder /build/tools/mcp/mcp_elevenlabs_speech/target/release/mcp-elevenlabs-speech /usr/local/bin/mcp-elevenlabs-speech
RUN chmod +x /usr/local/bin/mcp-elevenlabs-speech

# Set ownership to non-root user
RUN chown -R mcp:mcp /app

USER mcp

# Expose port for HTTP mode
EXPOSE 8018

# Environment variables
ENV RUST_LOG=info

# Default to HTTP mode for container
CMD ["mcp-elevenlabs-speech", "--mode", "http", "--port", "8018"]
