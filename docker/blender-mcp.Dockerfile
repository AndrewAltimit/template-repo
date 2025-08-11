# Blender MCP Server Dockerfile with GPU support
FROM nvidia/cuda:12.1.1-base-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV BLENDER_VERSION=4.0.2

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    xz-utils \
    python3 \
    python3-pip \
    libxxf86vm1 \
    libgl1-mesa-glx \
    libxi6 \
    libxrender1 \
    libxkbcommon-x11-0 \
    libsm6 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Download and install Blender
RUN wget -q https://download.blender.org/release/Blender4.0/blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && tar -xf blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && mv blender-${BLENDER_VERSION}-linux-x64 /opt/blender \
    && rm blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && ln -s /opt/blender/blender /usr/local/bin/blender

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY tools/mcp/blender/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy MCP core components
COPY tools/mcp/core /app/core

# Copy Blender MCP server
COPY tools/mcp/blender /app/blender

# Create necessary directories
RUN mkdir -p /app/projects /app/assets /app/outputs /app/temp /app/templates

# Create non-root user for security
RUN useradd -m -u 1000 blender && \
    chown -R blender:blender /app

# Switch to non-root user
USER blender

# Expose port
EXPOSE 8017

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8017/health')" || exit 1

# Run the server
CMD ["python3", "-m", "uvicorn", "blender.server:app", "--host", "0.0.0.0", "--port", "8017"]
