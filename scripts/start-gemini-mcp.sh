#!/bin/bash
# Start Gemini MCP server in background
echo "Starting Gemini MCP server on port 8006..."
nohup python3 tools/mcp/gemini_mcp_server.py > /tmp/gemini-mcp.log 2>&1 &
echo $! > /tmp/gemini-mcp.pid
echo "Server started with PID $(cat /tmp/gemini-mcp.pid)"
echo "Logs: /tmp/gemini-mcp.log"
sleep 2
curl -s http://localhost:8006/health | jq || echo "Server not ready yet"
