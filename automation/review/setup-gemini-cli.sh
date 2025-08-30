#!/bin/bash
# setup-gemini-cli.sh - Setup Gemini CLI for PR reviews in GitHub Actions
# This script ensures Gemini CLI is available for automated PR reviews

set -e

echo "🔧 Setting up Gemini CLI for PR review..."

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
    echo "❌ NVM not found. Cannot set up Gemini CLI."
    exit 1
fi

# Use Node.js 22.16.0
echo "🔧 Switching to Node.js 22.16.0..."
if ! nvm use 22.16.0; then
    echo "❌ Node.js 22.16.0 not found. Please install it with: nvm install 22.16.0"
    exit 1
fi

# Verify Node version
NODE_VERSION=$(node --version)
echo "✅ Using Node.js: $NODE_VERSION"

# Check if Gemini CLI is installed
if ! command -v gemini &> /dev/null; then
    echo "❌ Gemini CLI not found."
    echo "Please install it with: npm install -g @google/gemini-cli"
    exit 1
fi

# Get Gemini CLI version
GEMINI_VERSION=$(gemini --version 2>/dev/null || echo "unknown")
echo "✅ Gemini CLI version: $GEMINI_VERSION"

# Verify Gemini API key is available
if [ -z "${GEMINI_API_KEY}" ]; then
    echo "⚠️ GEMINI_API_KEY not set. Gemini CLI may not work properly."
    # Don't exit with error here since the workflow has continue-on-error
    exit 0
fi

echo "✅ Gemini CLI setup complete"
exit 0
