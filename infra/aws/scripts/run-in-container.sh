#!/usr/bin/env bash
#
# Run Terraform/Terragrunt Commands in Container
#
# Usage:
#   ./run-in-container.sh terragrunt plan
#   ./run-in-container.sh terragrunt apply
#   ./run-in-container.sh terraform version
#   ./run-in-container.sh aws sts get-caller-identity
#   ./run-in-container.sh bash  # Interactive shell
#
# AWS credentials are automatically exported from the host's AWS CLI
# configuration (supports SSO, profiles, etc.)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/../../.."

cd "${REPO_ROOT}"

# Build the container if it doesn't exist
if ! docker images | grep -q "template-repo.terraform-ci"; then
    echo "Building terraform-ci container..."
    docker compose --profile ci build terraform-ci
fi

# Export AWS credentials if not already set
# This converts SSO/profile credentials to env vars that Go SDK understands
if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
    echo "Exporting AWS credentials from host configuration..."
    eval "$(aws configure export-credentials --format env 2>/dev/null)" || {
        echo "Warning: Could not export AWS credentials. Run 'aws sso login' if using SSO."
    }
fi

# Build environment variable arguments for docker-compose
AWS_ENV_ARGS=()
if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
    AWS_ENV_ARGS+=(-e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY)
    # When using explicit credentials, unset AWS_PROFILE to avoid conflicts
    # (docker compose may pick up AWS_PROFILE from .env file)
    AWS_ENV_ARGS+=(-e AWS_PROFILE=)
    if [[ -n "${AWS_SESSION_TOKEN:-}" ]]; then
        AWS_ENV_ARGS+=(-e AWS_SESSION_TOKEN)
    fi
fi
if [[ -n "${AWS_REGION:-}" ]]; then
    AWS_ENV_ARGS+=(-e AWS_REGION)
fi

exec docker compose --profile ci run --rm \
    "${AWS_ENV_ARGS[@]}" \
    terraform-ci \
    "$@"
