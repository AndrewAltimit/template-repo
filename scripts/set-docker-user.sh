#!/bin/bash
# Script to set USER_ID and GROUP_ID environment variables for docker-compose
# This ensures containers run with the same permissions as the current user

# Export the current user's ID and group ID
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)

echo "🐳 Docker user environment set:"
echo "   USER_ID=$USER_ID"
echo "   GROUP_ID=$GROUP_ID"

# Also add these to GitHub Actions environment if running in CI
if [ -n "$GITHUB_ENV" ]; then
    echo "USER_ID=$USER_ID" >> $GITHUB_ENV
    echo "GROUP_ID=$GROUP_ID" >> $GITHUB_ENV
    echo "✅ Exported to GitHub Actions environment"
fi
