#!/bin/bash
# Entrypoint script for Codex Docker container
# Handles both agent and MCP server modes

set -e

# Determine execution mode based on MODE environment variable
if [ "$MODE" = "mcp" ]; then
    echo "Starting Codex MCP server on port 8021..."
    exec python -m tools.mcp.codex.server --mode http --host 0.0.0.0 --port 8021
else
    # Agent mode - start interactive bash or execute provided command
    if [ $# -eq 0 ]; then
        # No arguments, start interactive bash
        exec bash
    else
        # Arguments provided, execute them
        exec "$@"
    fi
fi
