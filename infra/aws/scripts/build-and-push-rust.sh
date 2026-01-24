#!/usr/bin/env bash
#
# Build and Push Rust AgentCore Runtime Container to ECR

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_DIR="${SCRIPT_DIR}/.."
DOCKERFILE="docker/strands-runtime-rust/Dockerfile"

REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO_NAME="${1:-bedrock-agentcore-strands-runtime-dev}"
TAG="${2:-latest}"

ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"

echo "=== Building Rust AgentCore Runtime Container ==="
echo "Repository: ${REPO_NAME}"
echo "Tag: ${TAG}"
echo "ECR URI: ${ECR_URI}:${TAG}"
echo ""

# Authenticate with ECR
aws ecr get-login-password --region "${REGION}" | \
    docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Check repository exists
if ! aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${REGION}" 2>/dev/null; then
    echo "Repository does not exist. Run: cd ../ecr && terragrunt apply"
    exit 1
fi

# Build and push from the aws directory context
cd "${AWS_DIR}"

if ! docker buildx inspect agentcore-builder 2>/dev/null; then
    docker buildx create --name agentcore-builder --use
fi

# Build for ARM64 (AWS Graviton)
docker buildx build \
    --platform linux/arm64 \
    --file "${DOCKERFILE}" \
    --tag "${ECR_URI}:${TAG}" \
    --tag "${ECR_URI}:rust-$(date +%Y%m%d-%H%M%S)" \
    --push \
    --builder agentcore-builder \
    .

echo ""
echo "=== Build Complete ==="
echo "Image URI: ${ECR_URI}:${TAG}"
