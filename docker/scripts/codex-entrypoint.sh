#!/bin/bash
# Entrypoint script for Codex Docker container
# Handles both agent and MCP server modes

set -e

# Fix for HOME directory mismatch - ensure .codex is accessible from $HOME
# This works regardless of what username docker-compose sets HOME to
if [ "$MODE" = "agent" ] && [ -d "/home/user/.codex" ]; then
    # Create parent directories if needed
    mkdir -p "$HOME" 2>/dev/null || true

    # If .codex doesn't exist at $HOME, create a symlink
    if [ ! -e "$HOME/.codex" ]; then
        ln -sf /home/user/.codex "$HOME/.codex" 2>/dev/null || true
    fi
fi

# Determine execution mode based on MODE environment variable
if [ "$MODE" = "mcp" ]; then
    # MCP mode - if arguments are provided, use them; otherwise use default HTTP mode
    if [ $# -eq 0 ]; then
        echo "Starting Codex MCP server in HTTP mode on port 8021..."
        exec python -m tools.mcp.codex.server --mode http --host 0.0.0.0 --port 8021
    else
        # Arguments provided (e.g., for stdio mode from .mcp.json)
        exec "$@"
    fi
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
