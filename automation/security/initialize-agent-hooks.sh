#!/bin/bash
# Initialize security hooks for AI agents
# This shared script is sourced by all agent run scripts to ensure
# consistent security hook setup across Claude Code, Gemini CLI, OpenCode, Crush, etc.
#
# Usage: source this file from your agent's run script after setting REPO_ROOT
#
# Prerequisites: REPO_ROOT must be set to the repository root directory

# Check that REPO_ROOT is set
if [ -z "$REPO_ROOT" ]; then
    echo "❌ ERROR: REPO_ROOT not set. Please set it before sourcing initialize-agent-hooks.sh"
    # Use return if sourced, exit if executed directly
    # shellcheck disable=SC2317
    return 1 2>/dev/null || exit 1
fi

# Define paths
HOOKS_SCRIPT="$REPO_ROOT/automation/security/setup-agent-hooks.sh"
AGENT_BASHRC="$REPO_ROOT/automation/security/agent-bashrc"

# Set up security hooks for GitHub operations
# This ensures reaction image URLs are validated and secrets are masked
if [ -f "$HOOKS_SCRIPT" ]; then
    echo "🔐 Loading security hooks..."
    # shellcheck source=/dev/null
    source "$HOOKS_SCRIPT"
    echo "✅ Security hooks activated (GitHub comment validation enabled)"

    # Set BASH_ENV so all bash invocations by the agent load the hooks
    # This is crucial for non-interactive shells spawned by AI agents
    if [ -f "$AGENT_BASHRC" ]; then
        export BASH_ENV="$AGENT_BASHRC"
        echo "📌 Hooks will persist in agent's bash commands (via BASH_ENV)"
    else
        echo "⚠️  Agent bashrc not found at $AGENT_BASHRC"
        echo "   Hooks may not persist in subshells"
    fi
else
    echo "⚠️  Security hooks not found at $HOOKS_SCRIPT"
    echo "   GitHub comment validation will not be active"
    echo "   Expected location: $HOOKS_SCRIPT"
fi

# Export AGENT_HOOKS_DIR for child processes (redundant but ensures consistency)
export AGENT_HOOKS_DIR="$REPO_ROOT/automation/security"
