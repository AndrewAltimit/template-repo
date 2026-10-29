#!/bin/bash
# run_claude.sh - Start Claude Code with Node.js 26.13.0

set -e

echo "🚀 Starting Claude Code with Node.js 26.13.0"

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

# Use Node.js 26.13.0
echo "🔧 Switching to Node.js 26.13.0..."
nvm use 26.13.0

# Verify Node version
NODE_VERSION=$(node --version)
echo "✅ Using Node.js: $NODE_VERSION"

# Note: Security validation is handled by gh-validator binary at ~/.local/bin/gh
# via PATH shadowing. No explicit hook initialization needed.

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
