#!/bin/bash
set -euo pipefail

# Get issue details and create context file for agent
#
# Environment variables:
#   ISSUE_NUMBER: Issue number to query
#   GITHUB_OUTPUT: File to write outputs to

echo "📋 Getting issue details..."

# Get issue body and metadata
ISSUE_DATA=$(gh issue view "${ISSUE_NUMBER}" --json body,title,labels)

ISSUE_BODY=$(echo "${ISSUE_DATA}" | jq -r '.body')
ISSUE_TITLE=$(echo "${ISSUE_DATA}" | jq -r '.title')

echo "Issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}"
echo ""
echo "${ISSUE_BODY}"

# Save to file for agent
{
  echo "# Issue #${ISSUE_NUMBER}: ${ISSUE_TITLE}"
  echo ""
  echo "${ISSUE_BODY}"
  echo ""
  echo "---"
  echo "**Agent Task**: Implement the above feature/fix as described."
  echo "Create a branch, make the changes, and open a PR."
} > /tmp/issue_context.md

echo "context_file=/tmp/issue_context.md" >> "${GITHUB_OUTPUT}"
