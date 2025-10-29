#!/bin/bash
set -euo pipefail

# Claim work on an issue
#
# Dependencies:
#   - board-cli (from github_ai_agents package)
#
# Environment variables:
#   ISSUE_NUMBER: Issue number to claim
#   AGENT_NAME: Agent claiming the issue
#   GITHUB_OUTPUT: File to write outputs to

echo "🔒 Claiming issue #${ISSUE_NUMBER} for agent ${AGENT_NAME}..."

# Generate unique session ID
SESSION_ID="gh-actions-$(date +%s)-${RANDOM}"
echo "session_id=${SESSION_ID}" >> "${GITHUB_OUTPUT}"

# Claim the issue
if board-cli claim "${ISSUE_NUMBER}" \
  --agent "${AGENT_NAME}" \
  --session "${SESSION_ID}"; then
  echo "✅ Successfully claimed issue #${ISSUE_NUMBER}"
  echo "claimed=true" >> "${GITHUB_OUTPUT}"
else
  echo "❌ Failed to claim issue #${ISSUE_NUMBER} (may be already claimed)"
  echo "claimed=false" >> "${GITHUB_OUTPUT}"
  exit 1
fi
