#!/bin/bash
# Script to run the PR review monitor agent inside a container
set -e

echo "[INFO] Starting PR review monitor agent..."
echo "[INFO] Environment variables:"
echo "  GITHUB_REPOSITORY: $GITHUB_REPOSITORY"
echo "  ENABLE_AI_AGENTS: $ENABLE_AI_AGENTS"
echo "  PR_MONITOR_VERBOSE: $PR_MONITOR_VERBOSE"
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
git config --global user.name 'AI PR Agent'
git config --global user.email 'ai-agent[bot]@users.noreply.github.com'

# Set up Python path
export PYTHONPATH="/workspace/scripts/agents:$PYTHONPATH"
echo "[INFO] Updated PYTHONPATH: $PYTHONPATH"

# Check if we're in the right directory
if [ ! -f scripts/agents/pr_review_monitor.py ]; then
    echo "[ERROR] pr_review_monitor.py not found! Current directory: $(pwd)"
    echo "[ERROR] Directory contents:"
    ls -la
    exit 1
fi

# Run with explicit PR number if provided
if [ -n "$TARGET_PR_NUMBER" ]; then
    echo "[INFO] Targeting specific PR: $TARGET_PR_NUMBER"
fi

echo "[INFO] Running PR review monitor..."
cd /workspace

# Run the actual Python script
python -u scripts/agents/pr_review_monitor.py
