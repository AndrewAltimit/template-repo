#!/bin/bash
set -e

# Convenience wrapper for PR monitoring
# Usage: monitor-pr.sh PR_NUMBER [OPTIONS]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if PR number provided
if [ -z "$1" ]; then
    echo "Usage: monitor-pr.sh PR_NUMBER [--timeout SECONDS] [--json] [--since-commit SHA]"
    echo ""
    echo "Examples:"
    echo "  monitor-pr.sh 48                          # Monitor PR #48"
    echo "  monitor-pr.sh 48 --timeout 1800           # Monitor for 30 minutes"
    echo "  monitor-pr.sh 48 --json                   # Output only JSON"
    echo "  monitor-pr.sh 48 --since-commit abc1234   # Monitor comments after commit"
    exit 1
fi

# Run the Python agent
python3 "$SCRIPT_DIR/pr_monitor_agent.py" "$@"
