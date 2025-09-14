#!/bin/bash
# Auto-detect and run the appropriate compose command with user permissions

set -euo pipefail

# Export current user ID and group ID for docker-compose
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

# If building, source versions from config/versions.json
if [[ "$*" == *"build"* ]]; then
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    if [ -f "$SCRIPT_DIR/scripts/export-versions.sh" ]; then
        echo "Loading versions from config/versions.json..."
        # shellcheck source=/dev/null
        source "$SCRIPT_DIR/scripts/export-versions.sh"
    fi
fi

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

echo "Using: $COMPOSE_CMD with user mapping: $USER_ID:$GROUP_ID"

# Pass all arguments to the compose command
exec $COMPOSE_CMD "$@"
