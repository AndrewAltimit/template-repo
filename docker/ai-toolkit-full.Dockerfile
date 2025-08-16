# Full AI Toolkit with Web UI and MCP Server
FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    wget \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Clone AI Toolkit
RUN git clone https://github.com/ostris/ai-toolkit.git /ai-toolkit

# Install AI Toolkit dependencies
WORKDIR /ai-toolkit
RUN pip3 install --no-cache-dir -r requirements.txt

# Install additional dependencies for MCP server
RUN pip3 install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    httpx \
    pydantic \
    aiofiles \
    psutil

# Copy MCP server code from our repo
COPY tools/mcp/ai_toolkit /workspace/mcp_server

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

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Start AI Toolkit web UI in background\n\
echo "Starting AI Toolkit Web UI on port 8675..."\n\
cd /ai-toolkit\n\
python3 app.py --host 0.0.0.0 --port 8675 &\n\
AI_TOOLKIT_PID=$!\n\
\n\
# Give the web UI time to start\n\
sleep 5\n\
\n\
# Start MCP server\n\
echo "Starting AI Toolkit MCP Server on port 8190..."\n\
cd /workspace\n\
python3 -m mcp_server.server --mode http --host 0.0.0.0 --port 8190 &\n\
MCP_PID=$!\n\
\n\
# Keep container running and handle shutdown\n\
trap "kill $AI_TOOLKIT_PID $MCP_PID; exit" SIGTERM SIGINT\n\
\n\
echo "AI Toolkit Web UI: http://0.0.0.0:8675"\n\
echo "AI Toolkit MCP Server: http://0.0.0.0:8190"\n\
\n\
# Wait for processes\n\
wait $AI_TOOLKIT_PID $MCP_PID\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

# Expose ports
EXPOSE 8675 8190

# Health check for web UI
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8675/ || exit 1

# Run entrypoint
CMD ["/entrypoint.sh"]
