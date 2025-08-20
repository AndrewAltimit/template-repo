# Docker image for Video Editor MCP Server
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # FFmpeg for audio/video processing
    ffmpeg \
    # Build tools for Python packages
    gcc \
    g++ \
    # Git for installing packages from GitHub
    git \
    # Curl for health checks
    curl \
    # Audio libraries
    libsndfile1 \
    # gosu for proper user switching
    gosu \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create output and cache directories
RUN mkdir -p /output /cache /tmp/video_editor

# Copy requirements first for better caching
COPY tools/mcp/video_editor/requirements.txt /tmp/video_editor_requirements.txt
COPY config/python/requirements.txt /tmp/base_requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir \
    # Install from the video editor requirements file
    -r /tmp/video_editor_requirements.txt \
    # Also install base requirements
    -r /tmp/base_requirements.txt

# Copy the application code
COPY tools/mcp/core /app/tools/mcp/core
COPY tools/mcp/video_editor /app/tools/mcp/video_editor

# Create non-root user (but don't switch yet)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /output /cache /tmp/video_editor

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:$PYTHONPATH
ENV MCP_VIDEO_OUTPUT_DIR=/output
ENV MCP_VIDEO_CACHE_DIR=/cache
ENV MCP_VIDEO_TEMP_DIR=/tmp/video_editor

# Expose the port
EXPOSE 8019

# Copy entrypoint script
COPY docker/entrypoints/video-editor-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/video-editor-entrypoint.sh

# Entrypoint for permission handling
ENTRYPOINT ["/usr/local/bin/video-editor-entrypoint.sh"]

# Default command
CMD ["python", "-m", "tools.mcp.video_editor.server", "--mode", "http"]
