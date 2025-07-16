#!/bin/bash
set -e
# Test that Gemini MCP server exits when run in a container

echo "Testing Gemini MCP server container detection..."

# Try to run in container - should exit with code 1
echo "Attempting to run Gemini MCP server in container..."
# Temporarily allow failure for this test
set +e
docker-compose run --rm gemini-mcp-server
EXIT_CODE=$?
set -e
if [ $EXIT_CODE -eq 1 ]; then
    echo "✅ SUCCESS: Gemini MCP server correctly exited with code 1 when run in container"
else
    echo "❌ FAILED: Expected exit code 1, got $EXIT_CODE"
    exit 1
fi

echo ""
echo "To run the Gemini MCP server properly, use:"
echo "  python tools/mcp/gemini_mcp_server.py"
