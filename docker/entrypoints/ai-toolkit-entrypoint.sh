#!/bin/bash
set -e

# Start AI Toolkit web UI in background
echo "Starting AI Toolkit Web UI on port 8675..."
cd /ai-toolkit/ui
npm start &
AI_TOOLKIT_PID=$!

# Give the web UI time to start
sleep 10

# Start MCP server
echo "Starting AI Toolkit MCP Server on port 8012..."
cd /workspace
python3 -m tools.mcp.ai_toolkit.server --mode http --host 0.0.0.0 --port 8012 &
MCP_PID=$!

# Keep container running and handle shutdown
trap 'kill $AI_TOOLKIT_PID $MCP_PID; exit' SIGTERM SIGINT

echo "AI Toolkit Web UI: http://0.0.0.0:8675"
echo "AI Toolkit MCP Server: http://0.0.0.0:8012"

# Wait for processes
wait $AI_TOOLKIT_PID $MCP_PID
