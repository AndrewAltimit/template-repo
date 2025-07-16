#!/bin/bash
set -e

# Use environment variable for port with default
GEMINI_PORT=${GEMINI_MCP_PORT:-8006}

# Start Gemini MCP server in background
echo "Starting Gemini MCP server on port $GEMINI_PORT..."
nohup python3 tools/mcp/gemini_mcp_server.py > /tmp/gemini-mcp.log 2>&1 &
PID=$!
echo $PID > /tmp/gemini-mcp.pid
echo "Server started with PID $PID"
echo "Logs: /tmp/gemini-mcp.log"

echo "Waiting for server to become healthy..."
for i in {1..10}; do
    if curl -s http://localhost:$GEMINI_PORT/health | grep -q "healthy"; then
        echo "✅ Server is healthy."
        HEALTH_JSON=$(curl -s http://localhost:$GEMINI_PORT/health)
        if command -v jq &> /dev/null; then
            echo "$HEALTH_JSON" | jq
        else
            echo "$HEALTH_JSON"
        fi
        exit 0
    fi
    sleep 1
done

echo "❌ Server did not become healthy after 10 seconds."
exit 1
