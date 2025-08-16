#!/bin/bash

# PR Monitor - Detects comments after a specific commit or monitors for new ones
# Usage: ./monitor.sh PR_NUMBER [SINCE_COMMIT]
# Returns: JSON with comment data when admin/Gemini comment detected
# SINCE_COMMIT: Optional commit SHA to get all comments after this commit

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
echo "Will exit and return data when admin/Gemini comment detected" >&2
echo "================================" >&2

# Function to check if a comment is relevant (from admin or github-actions)
is_relevant_comment() {
    local author="$1"
    if [[ "$author" == "AndrewAltimit" ]] || [[ "$author" == *"github-actions"* ]]; then
        return 0
    fi
    return 1
}

# If SINCE_COMMIT is provided, first check ALL existing comments after that commit
if [ -n "$SINCE_COMMIT" ]; then
    echo "Looking for comments after commit: $SINCE_COMMIT" >&2

    # Get commit timestamp
    COMMIT_TIME=$(gh api repos/:owner/:repo/commits/"$SINCE_COMMIT" --jq '.commit.committer.date' 2>/dev/null)
    if [ -z "$COMMIT_TIME" ]; then
        echo "Warning: Could not get timestamp for commit $SINCE_COMMIT" >&2
        echo "Will monitor for new comments instead" >&2
        SINCE_COMMIT=""
    else
        echo "Commit timestamp: $COMMIT_TIME" >&2

        # Get ALL comments and check if any came after the commit
        echo "Checking existing comments..." >&2

        # Get all comments as an array
        COMMENT_COUNT=$(gh pr view "$PR_NUMBER" --json comments --jq '.comments | length')

        # Check each comment
        for ((i=0; i<COMMENT_COUNT; i++)); do
            COMMENT_JSON=$(gh pr view "$PR_NUMBER" --json comments --jq ".comments[$i]")
            COMMENT_TIME=$(echo "$COMMENT_JSON" | jq -r '.createdAt')
            AUTHOR=$(echo "$COMMENT_JSON" | jq -r '.author.login')

            # Check if comment is after the commit
            if [[ "$COMMENT_TIME" > "$COMMIT_TIME" ]]; then
                echo "  Found comment from $AUTHOR at $COMMENT_TIME (after commit)" >&2

                if is_relevant_comment "$AUTHOR"; then
                    echo "  ✓ Relevant comment from $AUTHOR - returning immediately" >&2
                    echo "$COMMENT_JSON"
                    exit 0
                fi
            fi
        done

        echo "No relevant comments found after commit $SINCE_COMMIT yet" >&2
        echo "Now monitoring for new comments..." >&2

        # Store the commit time for filtering new comments
        FILTER_TIME=$COMMIT_TIME
    fi
fi

# Get initial count for monitoring new comments
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

        # Get the new comment(s) - there might be multiple
        NEW_COMMENTS=$((CURRENT_COUNT - LAST_COUNT))
        for ((i = NEW_COMMENTS; i > 0; i--)); do
            # Get comment at position (total - i + 1)
            COMMENT_INDEX=$((CURRENT_COUNT - i))
            COMMENT_JSON=$(gh pr view "$PR_NUMBER" --json comments --jq ".comments[$COMMENT_INDEX]")
            AUTHOR=$(echo "$COMMENT_JSON" | jq -r '.author.login')
            COMMENT_TIME=$(echo "$COMMENT_JSON" | jq -r '.createdAt')

            echo "  Comment from $AUTHOR at $COMMENT_TIME" >&2

            # Skip if comment is before the specified commit (when using FILTER_TIME)
            if [ -n "${FILTER_TIME:-}" ]; then
                if [[ "$COMMENT_TIME" < "$FILTER_TIME" ]]; then
                    echo "    ℹ Comment is before commit $SINCE_COMMIT, ignoring..." >&2
                    continue
                fi
            fi

            # Check if it's from admin or Gemini/GitHub Actions
            if is_relevant_comment "$AUTHOR"; then
                echo "  ✓ Relevant comment from $AUTHOR - returning to parent" >&2
                echo "$COMMENT_JSON"
                exit 0
            else
                echo "    ℹ Comment from $AUTHOR - not relevant, continuing..." >&2
            fi
        done

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
