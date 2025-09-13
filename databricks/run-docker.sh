#!/bin/bash
# Helper script to run docker-compose with correct user mapping
# This ensures containers create files with the current user's permissions

set -euo pipefail

# Export current user ID and group ID for docker-compose
USER_ID=$(id -u)
GROUP_ID=$(id -g)
export USER_ID
export GROUP_ID

echo "Running docker-compose with user mapping: $USER_ID:$GROUP_ID"

# Pass all arguments to docker-compose
docker-compose "$@"
