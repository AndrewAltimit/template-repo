#!/bin/bash
set -e

# Check if --http flag is provided for HTTP mode
if [[ "$1" == "--http" ]]; then
    # Use environment variable for port with default
    GEMINI_PORT=${GEMINI_MCP_PORT:-8006}

    # Start Gemini MCP server in HTTP mode (for testing)
    echo "Starting Gemini MCP server in HTTP mode on port $GEMINI_PORT..."
    echo "WARNING: HTTP mode is for testing only. Use stdio mode for production."
    nohup python3 -m tools.mcp.gemini.server --mode http --port $GEMINI_PORT > /tmp/gemini-mcp.log 2>&1 &
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
else
    # stdio mode (recommended)
    echo "Gemini MCP Server (stdio mode)"
    echo "==============================="
    echo ""
    echo "The stdio server needs to be connected to an MCP client."
    echo ""
    echo "Option 1: Direct execution (for testing)"
    echo "  python3 -m tools.mcp.gemini.server --project-root ."
    echo ""
    echo "Option 2: Configure with an MCP client (recommended)"
    echo ""
    echo "For Claude Desktop, add to config:"
    echo "  ~/.config/Claude/claude_desktop_config.json (Linux)"
    echo "  ~/Library/Application Support/Claude/claude_desktop_config.json (macOS)"
    echo ""
    echo '  {
    "mcpServers": {
      "gemini": {
        "command": "python3",
        "args": ["-m", "tools.mcp.gemini.server"],
        "env": {
          "GEMINI_API_KEY": "your-key-here"
        }
      }
    }
  }'
    echo ""
    echo "For VS Code MCP extension:"
    echo "  Add similar configuration to your VS Code settings"
    echo ""
    echo "For custom MCP client integration:"
    echo "  Use the MCP SDK to connect to the stdio server"
    echo ""
    echo "To test with HTTP mode instead (not recommended for production):"
    echo "  $0 --http"
fi
