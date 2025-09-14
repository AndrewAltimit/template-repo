#!/bin/bash
# Auto-detect and run the appropriate compose command

set -euo pipefail

# Detect which compose tool to use
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "Error: No compose command found (docker-compose, docker compose, or podman-compose)"
    exit 1
fi

echo "Using: $COMPOSE_CMD"

# Pass all arguments to the compose command
exec $COMPOSE_CMD "$@"
