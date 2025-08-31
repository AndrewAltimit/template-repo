#!/bin/bash
# run_claude.sh - Start Claude Code with Node.js 22.16.0

set -e

echo "🚀 Starting Claude Code with Node.js 22.16.0"

# Load NVM if it exists
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    echo "📦 Loading NVM..."
    # shellcheck source=/dev/null
    source "$HOME/.nvm/nvm.sh"
elif [ -s "/usr/local/share/nvm/nvm.sh" ]; then
    echo "📦 Loading NVM (system-wide)..."
    # shellcheck source=/dev/null
    source "/usr/local/share/nvm/nvm.sh"
else
    echo "❌ NVM not found. Please install NVM first."
    echo "Visit: https://github.com/nvm-sh/nvm#installation-and-update"
    exit 1
fi

# Use Node.js 22.16.0
echo "🔧 Switching to Node.js 22.16.0..."
nvm use 22.16.0

# Verify Node version
NODE_VERSION=$(node --version)
echo "✅ Using Node.js: $NODE_VERSION"

# Set up security hooks for GitHub operations
# This ensures reaction image URLs are validated and secrets are masked
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
HOOKS_SCRIPT="$REPO_ROOT/automation/security/setup-agent-hooks.sh"

if [ -f "$HOOKS_SCRIPT" ]; then
    echo "🔐 Loading security hooks..."
    # shellcheck source=/dev/null
    source "$HOOKS_SCRIPT"
    echo "✅ Security hooks activated (GitHub comment validation enabled)"

    # Set BASH_ENV so all bash invocations by Claude load the hooks
    AGENT_BASHRC="$REPO_ROOT/automation/security/agent-bashrc"
    if [ -f "$AGENT_BASHRC" ]; then
        export BASH_ENV="$AGENT_BASHRC"
        echo "📌 Hooks will persist in Claude's bash commands (via BASH_ENV)"
    fi
else
    echo "⚠️  Security hooks not found at $HOOKS_SCRIPT"
    echo "   GitHub comment validation will not be active"
fi

# Ask about unattended mode
echo "🤖 Claude Code Configuration"
echo ""
echo "Would you like to run Claude Code in unattended mode?"
echo "This will allow Claude to execute commands without asking for approval."
echo ""
read -p "Use unattended mode? (y/N): " -n 1 -r
echo ""

# Start Claude Code with appropriate flags
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "⚡ Starting Claude Code in UNATTENDED mode (--dangerously-skip-permissions)..."
    echo "⚠️  Claude will execute commands without asking for approval!"
    echo ""
    claude --dangerously-skip-permissions
else
    echo "🔒 Starting Claude Code in NORMAL mode (with approval prompts)..."
    echo ""
    claude
fi
