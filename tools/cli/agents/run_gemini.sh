#!/bin/bash
# run_gemini.sh - Start Gemini CLI with Node.js 22.16.0

set -e

echo "🚀 Starting Gemini CLI with Node.js 22.16.0"

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

# Check if Gemini CLI is installed
if ! command -v gemini &> /dev/null; then
    echo "❌ Gemini CLI not found. Please install it first."
    echo "Run: npm install -g @google/gemini-cli@0.21.2"
    exit 1
fi

GEMINI_VERSION=$(gemini --version 2>/dev/null || echo "unknown")
echo "✅ Gemini CLI version: $GEMINI_VERSION"

# Note: Security validation is handled by gh-validator binary at ~/.local/bin/gh
# via PATH shadowing. No explicit hook initialization needed.

# Ask about approval mode
echo ""
echo "🤖 Gemini CLI Configuration"
echo ""
echo "Select approval mode for Gemini CLI:"
echo "1) Normal mode - prompts for tool approval (recommended)"
echo "2) Auto-edit mode - auto-approves edit tools only"
echo "3) YOLO mode - auto-approves ALL tools (use with caution!)"
echo ""
read -p "Select mode (1/2/3) [default: 1]: " -r MODE_CHOICE
echo ""

# Additional flags for Gemini CLI
GEMINI_FLAGS=""

# Parse approval mode choice
case "$MODE_CHOICE" in
    2)
        echo "✏️  Starting Gemini CLI in AUTO-EDIT mode..."
        echo "📝 Edit tools will be auto-approved, other tools will prompt."
        GEMINI_FLAGS="--approval-mode auto_edit"
        ;;
    3)
        echo "⚡ Starting Gemini CLI in YOLO mode..."
        echo "⚠️  ALL tools will be auto-approved without prompting!"
        echo "🚨 Use with extreme caution - Gemini will execute all commands automatically!"
        GEMINI_FLAGS="--yolo"
        ;;
    *)
        echo "🔒 Starting Gemini CLI in NORMAL mode..."
        echo "📋 You will be prompted to approve each tool use."
        GEMINI_FLAGS=""
        ;;
esac

# Optional: Ask about additional features
echo ""
read -p "Enable checkpointing for file edits? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "💾 Checkpointing enabled - you can restore file states with /restore"
    GEMINI_FLAGS="$GEMINI_FLAGS --checkpointing"
fi

# Start Gemini CLI with appropriate flags
echo ""
echo "🎯 Starting Gemini CLI..."
echo "💡 Tip: Use /help to see all available commands"
echo ""

# Execute Gemini CLI with the selected flags
# shellcheck disable=SC2086
exec gemini $GEMINI_FLAGS
