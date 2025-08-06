#!/bin/bash
# Run issue monitor with containerized agents (OpenCode, Crush)
# This script is called when containerized agents are requested

set -e

echo "=== Running Issue Monitor with Containerized Agents ==="
echo ""

# Set up environment
export PYTHONPATH="${GITHUB_WORKSPACE:-$(pwd)}"
export PYTHONUNBUFFERED="1"
export RUNNING_IN_CONTAINER="true"

# Check if running in GitHub Actions
if [ -n "$GITHUB_ACTIONS" ]; then
    echo "[INFO] Running in GitHub Actions environment"
    echo "[INFO] Repository: $GITHUB_REPOSITORY"
fi

# Pass through all environment variables needed by the agents
docker-compose --profile agents run --rm \
    -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
    -e GITHUB_REPOSITORY="${GITHUB_REPOSITORY}" \
    -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY}" \
    -e ENABLE_AI_AGENTS="${ENABLE_AI_AGENTS}" \
    -e FORCE_REPROCESS="${FORCE_REPROCESS}" \
    -e RUNNING_IN_CONTAINER="true" \
    openrouter-agents \
    python -m github_ai_agents.cli issue-monitor "$@"
