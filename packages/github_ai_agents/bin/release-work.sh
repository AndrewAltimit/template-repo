#!/bin/bash
set -euo pipefail

# Release claim on an issue
#
# Environment variables:
#   ISSUE_NUMBER: Issue number to release
#   AGENT_NAME: Agent releasing the claim
#   WORK_COMPLETED: Whether work was completed (true/false)

echo "🔓 Releasing claim on issue #${ISSUE_NUMBER}..."

# Determine reason based on work completion
if [ "${WORK_COMPLETED:-false}" == "true" ]; then
  REASON="completed"
else
  REASON="error"
fi

board-cli release "${ISSUE_NUMBER}" \
  --agent "${AGENT_NAME}" \
  --reason "${REASON}"

echo "✅ Released claim (reason: ${REASON})"
