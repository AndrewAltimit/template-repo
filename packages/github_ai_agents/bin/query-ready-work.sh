#!/bin/bash
set -euo pipefail

# Query ready work from board and output results
#
# Dependencies:
#   - board-cli (from github_ai_agents package)
#   - jq (JSON processor)
#
# Environment variables:
#   AGENT_NAME: Agent to query for
#   MAX_ISSUES: Maximum number of issues to return
#   GITHUB_OUTPUT: File to write outputs to

echo "🔍 Querying board for ready work..."
echo "Agent: ${AGENT_NAME}"
echo "Max issues: ${MAX_ISSUES}"

# Query ready work using board CLI
READY_WORK=$(board-cli ready \
  --agent "${AGENT_NAME}" \
  --limit "${MAX_ISSUES}" \
  --json)

echo "Board response:"
echo "${READY_WORK}" | jq '.'

# Check if we have work
ISSUE_COUNT=$(echo "${READY_WORK}" | jq 'length')

if [ "${ISSUE_COUNT}" -gt 0 ]; then
  echo "has_work=true" >> "${GITHUB_OUTPUT}"

  # Get first issue details
  ISSUE_NUM=$(echo "${READY_WORK}" | jq -r '.[0].number')
  ISSUE_TITLE=$(echo "${READY_WORK}" | jq -r '.[0].title')

  echo "issue_number=${ISSUE_NUM}" >> "${GITHUB_OUTPUT}"
  echo "issue_title=${ISSUE_TITLE}" >> "${GITHUB_OUTPUT}"

  echo "✅ Found work: Issue #${ISSUE_NUM} - ${ISSUE_TITLE}"
else
  echo "has_work=false" >> "${GITHUB_OUTPUT}"
  echo "ℹ️ No ready work found for agent ${AGENT_NAME}"
fi
