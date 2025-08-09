#!/bin/bash

# PR Monitor - Detects new comments and returns when relevant ones are found
# Usage: ./monitor.sh [PR_NUMBER]
# Returns: JSON with comment data when admin/Gemini comment detected

# Exit on error and fail on pipe errors for robustness
set -e
set -o pipefail

PR_NUMBER=${1:-}

if [ -z "$PR_NUMBER" ]; then
    echo "Usage: $0 PR_NUMBER" >&2
    echo "Example: $0 48" >&2
    exit 1
fi

echo "Starting PR #$PR_NUMBER monitor..." >&2
echo "Will exit and return data when admin/Gemini comment detected" >&2
echo "================================" >&2

# Get initial count
LAST_COUNT=$(gh pr view "$PR_NUMBER" --json comments --jq '.comments | length')
echo "Starting with $LAST_COUNT comments" >&2
echo "Checking every 5 seconds..." >&2
echo "" >&2

CHECKS=0
while true; do
    sleep 5
    CHECKS=$((CHECKS + 1))

    # Get current count
    CURRENT_COUNT=$(gh pr view "$PR_NUMBER" --json comments --jq '.comments | length')

    echo -n "[$(date +%H:%M:%S)] Check #$CHECKS: $CURRENT_COUNT comments" >&2

    if [ "$CURRENT_COUNT" -gt "$LAST_COUNT" ]; then
        echo " → NEW COMMENT DETECTED!" >&2

        # Get the new comment details
        COMMENT_JSON=$(gh pr view "$PR_NUMBER" --json comments --jq '.comments[-1]')
        AUTHOR=$(echo "$COMMENT_JSON" | jq -r '.author.login')

        echo "  Author: $AUTHOR" >&2

        # Check if it's from admin or Gemini/GitHub Actions
        if [[ "$AUTHOR" == "AndrewAltimit" ]] || [[ "$AUTHOR" == *"github-actions"* ]]; then
            echo "  ✓ Relevant comment from $AUTHOR - returning to parent" >&2

            # Return the comment JSON to stdout and exit
            echo "$COMMENT_JSON"
            exit 0
        else
            echo "  ℹ Comment from $AUTHOR - not relevant, continuing..." >&2
        fi

        LAST_COUNT=$CURRENT_COUNT
    else
        echo " (no change)" >&2
    fi

    # Timeout after 10 minutes
    if [ $CHECKS -gt 120 ]; then
        echo "" >&2
        echo "Monitor timeout after 10 minutes" >&2
        exit 1
    fi
done
