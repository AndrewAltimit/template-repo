# Multi-stage Rust build for mcp-video-editor
# Stage 1: Build the Rust binary
# Use bookworm-based rust image to match runtime glibc version
FROM rust:1.93-slim-bookworm AS builder

WORKDIR /build

# Copy MCP core framework first (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy video editor server
COPY tools/mcp/mcp_video_editor /build/tools/mcp/mcp_video_editor

# Build the binary
WORKDIR /build/tools/mcp/mcp_video_editor
RUN cargo build --release

# Stage 2: Runtime image with FFmpeg and audio processing
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # FFmpeg for audio/video processing
    ffmpeg \
    # Audio libraries
    libsndfile1 \
    # Networking
    curl \
    ca-certificates \
    # gosu for proper user switching
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create app user with configurable UID/GID
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} mcp || true && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} mcp || true

# Create directories
RUN mkdir -p /app /output /cache /tmp/video_editor && \
    chown -R mcp:mcp /app /output /cache /tmp/video_editor

WORKDIR /app

# Copy the binary from builder
COPY --from=builder /build/tools/mcp/mcp_video_editor/target/release/mcp-video-editor /usr/local/bin/

# Set permissions
RUN chmod +x /usr/local/bin/mcp-video-editor

# Copy entrypoint script
COPY docker/entrypoints/video-editor-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/video-editor-entrypoint.sh

# Environment variables
ENV RUST_LOG=info
ENV MCP_VIDEO_OUTPUT_DIR=/output
ENV MCP_VIDEO_CACHE_DIR=/cache
ENV MCP_VIDEO_TEMP_DIR=/tmp/video_editor

# Expose port
EXPOSE 8019

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8019/health || exit 1

# Entrypoint for permission handling
ENTRYPOINT ["/usr/local/bin/video-editor-entrypoint.sh"]

# Default command
CMD ["mcp-video-editor", "--mode", "standalone", "--port", "8019"]
