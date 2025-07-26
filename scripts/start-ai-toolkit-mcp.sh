#!/bin/bash
# Start AI Toolkit MCP Server on Linux/macOS
# This server acts as a bridge to the remote AI Toolkit at 192.168.0.152:8012

echo -e "\033[32mStarting AI Toolkit MCP Server Bridge...\033[0m"
echo

# Show remote server info
echo -e "\033[36mThis server bridges to remote AI Toolkit at:\033[0m"
echo "  Host: 192.168.0.152"
echo "  Port: 8012"
echo
echo -e "\033[33mMake sure the remote AI Toolkit server is running for full functionality.\033[0m"
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "\033[31mERROR: Python3 not found in PATH\033[0m"
    echo "Please install Python 3.8+ and add it to PATH"
    exit 1
fi

# Check if custom host/port provided via environment
if [ -n "$AI_TOOLKIT_HOST" ]; then
    echo -e "\033[33mUsing custom AI Toolkit host: $AI_TOOLKIT_HOST\033[0m"
fi
if [ -n "$AI_TOOLKIT_PORT" ]; then
    echo -e "\033[33mUsing custom AI Toolkit port: $AI_TOOLKIT_PORT\033[0m"
fi
echo

# Get script directory and change to repository root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.." || exit 1

# Start the server
echo -e "\033[32mStarting bridge server on http://localhost:8012\033[0m"
echo -e "\033[33mPress Ctrl+C to stop the server\033[0m"
echo

python3 -m tools.mcp.ai_toolkit.server --mode http "$@"
