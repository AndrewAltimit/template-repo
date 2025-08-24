#!/bin/bash
# Start the Virtual Character MCP Server

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR/../../../.."

# Set environment variables
export VIRTUAL_CHARACTER_PORT="${VIRTUAL_CHARACTER_PORT:-8020}"
export VIRTUAL_CHARACTER_HOST="${VIRTUAL_CHARACTER_HOST:-0.0.0.0}"
export DEFAULT_BACKEND="${DEFAULT_BACKEND:-mock}"

# VRChat remote settings (if using)
export VRCHAT_REMOTE_HOST="${VRCHAT_REMOTE_HOST:-192.168.0.150}"
export OBS_PASSWORD="${OBS_PASSWORD:-}"
export STREAM_AUTH_TOKEN="${STREAM_AUTH_TOKEN:-}"

echo "Starting Virtual Character MCP Server..."
echo "Host: $VIRTUAL_CHARACTER_HOST"
echo "Port: $VIRTUAL_CHARACTER_PORT"
echo "Default Backend: $DEFAULT_BACKEND"

# Change to project root
cd "$PROJECT_ROOT" || exit

# Run the server
python -m tools.mcp.virtual_character.server
