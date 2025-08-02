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

# Source the shared credential setup script
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${script_dir}/setup_agent_credentials.sh"

# Set up credentials
setup_agent_credentials

# Verify Claude CLI can see the credentials
echo "[DEBUG] Testing Claude CLI configuration..."
echo "[DEBUG] HOME=$HOME"
echo "[DEBUG] Checking for Claude config files:"
[ -f $HOME/.claude.json ] && echo "[DEBUG]   - Found $HOME/.claude.json"
[ -f $HOME/.claude/claude.json ] && echo "[DEBUG]   - Found $HOME/.claude/claude.json"
[ -d $HOME/.config/claude ] && echo "[DEBUG]   - Found $HOME/.config/claude directory"

# Claude may also look for config in other locations
echo "[DEBUG] Checking additional Claude config locations:"
[ -f $HOME/.config/claude.json ] && echo "[DEBUG]   - Found $HOME/.config/claude.json"
[ -d $HOME/.claude ] && echo "[DEBUG]   - Found $HOME/.claude directory: $(ls -la $HOME/.claude/)"

# Test if Claude can detect the credentials
echo "[DEBUG] Testing Claude CLI authentication status..."
# Use timeout to prevent hanging if claude tries to prompt
timeout 5 claude --version 2>&1 | head -n 5 || echo "[DEBUG] Claude version check timed out or failed"

# Check if we can get more info about Claude's auth status
echo "[DEBUG] Checking Claude CLI help for auth options..."
claude --help 2>&1 | grep -E "(auth|login|api|key|token)" || true

# Try to see what Claude expects
echo "[DEBUG] Testing if Claude recognizes the config..."
timeout 5 claude --settings $HOME/.claude.json --version 2>&1 || echo "[DEBUG] Settings flag test failed"

# Check for the setup-token command
echo "[DEBUG] Checking for setup-token command..."
claude setup-token --help 2>&1 | head -20 || echo "[DEBUG] No setup-token command found"

# GitHub CLI config is handled by setup_agent_credentials function

# Configure git identity
git config --global user.name 'AI Issue Agent'
git config --global user.email 'ai-agent[bot]@users.noreply.github.com'

# Add repository as safe directory (needed when running as different user in container)
git config --global --add safe.directory /workspace

# Set up Python path
export PYTHONPATH="/workspace:$PYTHONPATH"
echo "[INFO] Updated PYTHONPATH: $PYTHONPATH"

# Check if we're in the right directory
if [ ! -f scripts/agents/issue_monitor_multi_agent.py ]; then
    echo "[ERROR] issue_monitor_multi_agent.py not found! Current directory: $(pwd)"
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

# Run the multi-agent Python script as a module to fix imports
python -u -m scripts.agents.issue_monitor_multi_agent
