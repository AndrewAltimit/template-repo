# Full AI Toolkit with Web UI and MCP Server
FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    wget \
    ffmpeg \
    libsm6 \
    libxext6 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Clone AI Toolkit
RUN git clone https://github.com/ostris/ai-toolkit.git /ai-toolkit

# Install AI Toolkit Python dependencies
WORKDIR /ai-toolkit
RUN pip3 install --no-cache-dir -r requirements.txt

# Build and install the Node.js UI
WORKDIR /ai-toolkit/ui
RUN npm install && npm run build

# Install additional dependencies for MCP server
RUN pip3 install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    httpx \
    pydantic \
    aiofiles \
    psutil \
    mcp

# Copy entire tools directory to maintain proper Python module structure
COPY tools /workspace/tools

# Create directories
RUN mkdir -p /ai-toolkit/datasets \
    /ai-toolkit/outputs \
    /ai-toolkit/configs \
    /workspace/logs

# Environment variables
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
ENV PYTHONUNBUFFERED=1
ENV AI_TOOLKIT_PATH=/ai-toolkit
ENV NODE_ENV=production

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Start AI Toolkit web UI in background\n\
echo "Starting AI Toolkit Web UI on port 3000..."\n\
cd /ai-toolkit/ui\n\
npm start &\n\
AI_TOOLKIT_PID=$!\n\
\n\
# Give the web UI time to start\n\
sleep 10\n\
\n\
# Start MCP server\n\
echo "Starting AI Toolkit MCP Server on port 8190..."\n\
cd /workspace\n\
python3 -m tools.mcp.ai_toolkit.server --mode http --host 0.0.0.0 --port 8190 &\n\
MCP_PID=$!\n\
\n\
# Keep container running and handle shutdown\n\
trap "kill $AI_TOOLKIT_PID $MCP_PID; exit" SIGTERM SIGINT\n\
\n\
echo "AI Toolkit Web UI: http://0.0.0.0:3000"\n\
echo "AI Toolkit MCP Server: http://0.0.0.0:8190"\n\
\n\
# Wait for processes\n\
wait $AI_TOOLKIT_PID $MCP_PID\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

# Expose ports (3000 for Node.js UI, 8190 for MCP)
EXPOSE 3000 8190

# Health check for web UI
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:3000/ || exit 1

# Run entrypoint
CMD ["/entrypoint.sh"]
