#!/bin/bash
# stop_claude.sh - Stop any running Claude Code processes

set -e

echo "🛑 Stopping Claude Code processes..."
echo ""

# Check if any claude processes are running
CLAUDE_PIDS=$(pgrep -f "claude" | grep -v $$ 2>/dev/null || true)

if [ -z "$CLAUDE_PIDS" ]; then
    echo "✅ No Claude Code processes found running."
    exit 0
fi

# Display found processes
echo "Found Claude Code processes:"
ps -fp $CLAUDE_PIDS
echo ""

# Ask for confirmation
read -p "⚠️  Kill these processes? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Kill the processes
    echo "Terminating Claude Code processes..."
    pkill -f "claude"

    # Wait a moment
    sleep 1

    # Check if any processes remain
    REMAINING=$(pgrep -f "claude" 2>/dev/null || true)
    if [ -z "$REMAINING" ]; then
        echo "✅ All Claude Code processes have been terminated."
    else
        echo "⚠️  Some processes may still be running. Use 'pkill -9 -f claude' to force kill."
    fi
else
    echo "❌ Cancelled. No processes were terminated."
fi
