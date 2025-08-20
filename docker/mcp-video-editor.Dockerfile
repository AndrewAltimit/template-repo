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
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create output and cache directories
RUN mkdir -p /output /cache /tmp/video_editor

# Copy requirements first for better caching
COPY config/python/requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir \
    # MCP and async
    mcp \
    asyncio \
    aiohttp \
    # Video processing
    moviepy \
    opencv-python-headless \
    # Audio processing
    openai-whisper \
    pyannote.audio \
    librosa \
    # ML dependencies
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 \
    transformers \
    # Image processing
    Pillow \
    # Utilities
    numpy \
    scipy \
    # Install base requirements
    -r /tmp/requirements.txt

# Copy the application code
COPY tools/mcp/core /app/tools/mcp/core
COPY tools/mcp/video_editor /app/tools/mcp/video_editor

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /output /cache /tmp/video_editor

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:$PYTHONPATH
ENV MCP_VIDEO_OUTPUT_DIR=/output
ENV MCP_VIDEO_CACHE_DIR=/cache
ENV MCP_VIDEO_TEMP_DIR=/tmp/video_editor

# Expose the port
EXPOSE 8019

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8019/health || exit 1

# Default command
CMD ["python", "-m", "tools.mcp.video_editor.server", "--mode", "http"]
