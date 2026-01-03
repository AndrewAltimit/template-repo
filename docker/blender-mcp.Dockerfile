# Blender MCP Server Dockerfile with GPU support
FROM nvidia/cuda:12.1.1-base-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV BLENDER_VERSION=4.5.1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
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
RUN wget -q https://download.blender.org/release/Blender4.5/blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && tar -xf blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && mv blender-${BLENDER_VERSION}-linux-x64 /opt/blender \
    && rm blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && ln -s /opt/blender/blender /usr/local/bin/blender

# Create app directory
WORKDIR /app

# Upgrade pip first for proper pyproject.toml support
RUN pip3 install --upgrade pip setuptools wheel

# Copy requirements first for better caching
COPY tools/mcp/mcp_blender/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy MCP packages
COPY tools/mcp/mcp_core /app/tools/mcp/mcp_core
COPY tools/mcp/mcp_blender /app/tools/mcp/mcp_blender

# Install MCP packages (use -v for verbose output)
RUN pip install --no-cache-dir -v /app/tools/mcp/mcp_core && \
    pip install --no-cache-dir -v /app/tools/mcp/mcp_blender

# Set Python path for module discovery
ENV PYTHONPATH=/app

# Create non-root user, directories, and set permissions in one layer
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} blender && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} blender && \
    mkdir -p /app/projects /app/assets /app/outputs /app/temp /app/templates && \
    chown -R blender:blender /app && \
    chmod -R 755 /app

# Switch to non-root user
USER blender

# Expose port
EXPOSE 8017

# Run the server
CMD ["python3", "-m", "mcp_blender.server"]
