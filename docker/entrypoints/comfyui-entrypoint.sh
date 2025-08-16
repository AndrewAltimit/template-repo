#!/bin/bash
set -e

# Start ComfyUI web UI in background
echo "Starting ComfyUI Web UI on port 8188..."
cd /comfyui
python3 main.py --listen 0.0.0.0 --port 8188 --highvram &
COMFYUI_PID=$!

# Give the web UI time to start
sleep 10

# Start MCP server
echo "Starting ComfyUI MCP Server on port 8189..."
cd /workspace
python3 -m tools.mcp.comfyui.server --mode http --host 0.0.0.0 --port 8189 &
MCP_PID=$!

# Keep container running and handle shutdown
trap 'kill $COMFYUI_PID $MCP_PID; exit' SIGTERM SIGINT

echo "ComfyUI Web UI: http://0.0.0.0:8188"
echo "ComfyUI MCP Server: http://0.0.0.0:8189"

# Wait for processes
wait $COMFYUI_PID $MCP_PID
