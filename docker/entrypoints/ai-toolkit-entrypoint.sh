#!/bin/bash
set -e

# Start AI Toolkit web UI in background
echo "Starting AI Toolkit Web UI on port 8675..."
cd /ai-toolkit/ui
npm start &
AI_TOOLKIT_PID=$!

# Wait for the web UI to be ready (with timeout)
echo "Waiting for AI Toolkit UI to be available on port 8675..."
MAX_ATTEMPTS=30  # 30 attempts * 2 seconds = 60 seconds max wait
ATTEMPT=0
while ! curl -s http://localhost:8675/ > /dev/null 2>&1; do
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
        echo "ERROR: AI Toolkit UI failed to start after 60 seconds"
        kill $AI_TOOLKIT_PID 2>/dev/null
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo " AI Toolkit UI is ready!"

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
