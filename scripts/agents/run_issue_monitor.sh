#!/bin/bash
# Script to run the issue monitor agent inside a container
set -e

echo "[INFO] Starting issue monitor agent..."
echo "[INFO] Environment variables:"
echo "  GITHUB_REPOSITORY: $GITHUB_REPOSITORY"
echo "  ENABLE_AI_AGENTS: $ENABLE_AI_AGENTS"
echo "  FORCE_REPROCESS: ${FORCE_REPROCESS:-false}"
echo "  PYTHONPATH: $PYTHONPATH"
echo "[INFO] Current directory: $(pwd)"

# Set up the home directory for configs
export HOME=/tmp/agent-home
mkdir -p $HOME/.config

# Copy credentials if they exist
if [ -d /host-claude ]; then
    echo "[INFO] Copying Claude credentials..."
    cp -r /host-claude $HOME/.claude
fi

if [ -d /host-gh ]; then
    echo "[INFO] Copying GitHub CLI config..."
    cp -r /host-gh $HOME/.config/gh
fi

# Configure git identity
git config --global user.name 'AI Issue Agent'
git config --global user.email 'ai-agent[bot]@users.noreply.github.com'

# Add repository as safe directory (needed when running as different user in container)
git config --global --add safe.directory /workspace

# Set up Python path
export PYTHONPATH="/workspace:$PYTHONPATH"
echo "[INFO] Updated PYTHONPATH: $PYTHONPATH"

# Check if we're in the right directory
if [ ! -f scripts/agents/issue_monitor.py ]; then
    echo "[ERROR] issue_monitor.py not found! Current directory: $(pwd)"
    echo "[ERROR] Directory contents:"
    ls -la
    exit 1
fi

# Run with explicit issue number if provided
if [ -n "$TARGET_ISSUE_NUMBER" ]; then
    echo "[INFO] Targeting specific issue: $TARGET_ISSUE_NUMBER"
fi

echo "[INFO] Running issue monitor..."
cd /workspace

# Run the actual Python script
python -u scripts/agents/issue_monitor.py
