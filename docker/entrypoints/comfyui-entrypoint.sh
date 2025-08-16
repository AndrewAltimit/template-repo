#!/bin/bash
set -e

# Start ComfyUI web UI in background
echo "Starting ComfyUI Web UI on port 8188..."
cd /comfyui
python3 main.py --listen 0.0.0.0 --port 8188 --highvram &
COMFYUI_PID=$!

# Wait for the web UI to be ready (with timeout)
echo "Waiting for ComfyUI UI to be available on port 8188..."
MAX_ATTEMPTS=30  # 30 attempts * 2 seconds = 60 seconds max wait
ATTEMPT=0
while ! curl -s http://localhost:8188/system_stats > /dev/null 2>&1; do
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
        echo "ERROR: ComfyUI UI failed to start after 60 seconds"
        kill $COMFYUI_PID 2>/dev/null
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo " ComfyUI UI is ready!"

# Start MCP server
echo "Starting ComfyUI MCP Server on port 8013..."
cd /workspace
python3 -m tools.mcp.comfyui.server --mode http --host 0.0.0.0 --port 8013 &
MCP_PID=$!

# Keep container running and handle shutdown
trap 'kill $COMFYUI_PID $MCP_PID; exit' SIGTERM SIGINT

echo "ComfyUI Web UI: http://0.0.0.0:8188"
echo "ComfyUI MCP Server: http://0.0.0.0:8013"

# Wait for processes
wait $COMFYUI_PID $MCP_PID
