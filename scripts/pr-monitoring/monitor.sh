#!/bin/bash

# PR Monitor - Detects new comments and returns when relevant ones are found
# Usage: ./monitor.sh PR_NUMBER [SINCE_COMMIT]
# Returns: JSON with comment data when admin/Gemini comment detected
# SINCE_COMMIT: Optional commit SHA to only consider comments after this commit

# Exit on error and fail on pipe errors for robustness
set -e
set -o pipefail

PR_NUMBER=${1:-}
SINCE_COMMIT=${2:-}

if [ -z "$PR_NUMBER" ]; then
    echo "Usage: $0 PR_NUMBER [SINCE_COMMIT]" >&2
    echo "Example: $0 48" >&2
    echo "Example: $0 48 abc1234" >&2
    exit 1
fi

echo "Starting PR #$PR_NUMBER monitor..." >&2
if [ -n "$SINCE_COMMIT" ]; then
    echo "Monitoring for comments after commit: $SINCE_COMMIT" >&2
fi
echo "Will exit and return data when admin/Gemini comment detected" >&2
echo "================================" >&2

# Get initial comments and filter by commit if provided
if [ -n "$SINCE_COMMIT" ]; then
    # Get commit timestamp to filter comments
    COMMIT_TIME=$(gh api repos/:owner/:repo/commits/"$SINCE_COMMIT" --jq '.commit.committer.date' 2>/dev/null)
    if [ -z "$COMMIT_TIME" ]; then
        echo "Warning: Could not get timestamp for commit $SINCE_COMMIT, monitoring all new comments" >&2
        SINCE_COMMIT=""
    else
        echo "Filtering comments after: $COMMIT_TIME" >&2
    fi
fi

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
        COMMENT_TIME=$(echo "$COMMENT_JSON" | jq -r '.createdAt')

        # Skip if comment is before the specified commit
        if [ -n "$SINCE_COMMIT" ] && [ -n "$COMMIT_TIME" ]; then
            if [[ "$COMMENT_TIME" < "$COMMIT_TIME" ]]; then
                echo "  ℹ Comment is before commit $SINCE_COMMIT, ignoring..." >&2
                LAST_COUNT=$CURRENT_COUNT
                continue
            fi
        fi

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
