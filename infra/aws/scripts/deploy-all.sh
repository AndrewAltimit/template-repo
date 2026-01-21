#!/usr/bin/env bash
#
# Deploy All AgentCore Infrastructure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_DIR="${SCRIPT_DIR}/.."

AUTO_APPROVE=""
[[ "${1:-}" == "-y" ]] && AUTO_APPROVE="--terragrunt-non-interactive"

echo "=== Deploying AgentCore Infrastructure ==="
echo ""

# Deploy IAM
echo "=== Step 1/4: IAM Roles ==="
cd "${AWS_DIR}/iam"
terragrunt init
terragrunt apply ${AUTO_APPROVE}

# Deploy ECR
echo "=== Step 2/4: ECR Repository ==="
cd "${AWS_DIR}/ecr"
terragrunt init
terragrunt apply ${AUTO_APPROVE}

# Build and push container
echo "=== Step 3/4: Container Image ==="
"${SCRIPT_DIR}/build-and-push.sh"

# Deploy AgentCore runtime
echo "=== Step 4/4: AgentCore Runtime ==="
cd "${AWS_DIR}/agentcore-runtime"
terragrunt init
terragrunt apply ${AUTO_APPROVE}

echo ""
echo "=== Deployment Complete ==="
terragrunt output
