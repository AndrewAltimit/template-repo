#!/bin/bash
# Shared credential setup for AI agent scripts
# This script sets up Claude and GitHub credentials in the container environment

# Function to set up credentials
setup_agent_credentials() {
    # Copy Claude credentials if they exist
    if [ -d /host-claude ]; then
        echo "[INFO] Copying Claude credentials directory..."
        cp -r /host-claude "$HOME/.claude"
        # Also check for claude.json file in the mounted directory
        if [ -f /host-claude/claude.json ]; then
            echo "[INFO] Found claude.json in mounted directory"
        fi
    elif [ -f /host-claude ]; then
        # Handle case where .claude is a file (like .claude.json)
        echo "[INFO] Copying Claude credentials file..."
        mkdir -p "$HOME/.claude"
        cp /host-claude "$HOME/.claude/claude.json"
    fi

    # Check if credentials were copied successfully
    if [ -f "$HOME/.claude/claude.json" ]; then
        echo "[INFO] Claude credentials found at $HOME/.claude/claude.json"
        # Claude Code might also look for .claude.json in HOME
        cp "$HOME/.claude/claude.json" "$HOME/.claude.json"
        echo "[INFO] Also copied to $HOME/.claude.json for compatibility"
        # Debug: check file contents (without exposing sensitive data)
        echo "[DEBUG] Credential file size: $(stat -c%s "$HOME/.claude.json") bytes"
        echo "[DEBUG] Credential file permissions: $(stat -c%a "$HOME/.claude.json")"
    elif [ -f "$HOME/.claude.json" ]; then
        echo "[INFO] Claude credentials found at $HOME/.claude.json"
        # Also create .claude directory structure
        mkdir -p "$HOME/.claude"
        cp "$HOME/.claude.json" "$HOME/.claude/claude.json"
        echo "[INFO] Also copied to $HOME/.claude/claude.json for compatibility"
        # Debug: check file contents (without exposing sensitive data)
        echo "[DEBUG] Credential file size: $(stat -c%s "$HOME/.claude.json") bytes"
        echo "[DEBUG] Credential file permissions: $(stat -c%a "$HOME/.claude.json")"
    else
        echo "[WARNING] No Claude credentials found after copy"
        echo "[DEBUG] HOME directory contents:"
        ls -la "$HOME/"
        echo "[DEBUG] Looking for Claude config in standard locations..."
        [ -f ~/.claude.json ] && echo "[DEBUG] Found ~/.claude.json in original home"
        [ -d ~/.claude ] && echo "[DEBUG] Found ~/.claude directory in original home"
    fi

    # Copy GitHub CLI config if available
    if [ -d /host-gh ]; then
        echo "[INFO] Copying GitHub CLI config..."
        cp -r /host-gh "$HOME/.config/gh"
    fi
}

# Make the function available to other scripts
export -f setup_agent_credentials
