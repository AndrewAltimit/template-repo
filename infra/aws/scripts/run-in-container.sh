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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/../../.."

cd "${REPO_ROOT}"

# Build the container if it doesn't exist
if ! docker images | grep -q "template-repo.terraform-ci"; then
    echo "Building terraform-ci container..."
    docker-compose --profile ci build terraform-ci
fi

# Run the command in the container
# Pass through AWS credentials via environment variables if set
AWS_ENV_ARGS=()
if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
    AWS_ENV_ARGS+=(-e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY)
    if [[ -n "${AWS_SESSION_TOKEN:-}" ]]; then
        AWS_ENV_ARGS+=(-e AWS_SESSION_TOKEN)
    fi
fi

exec docker-compose --profile ci run --rm \
    "${AWS_ENV_ARGS[@]}" \
    terraform-ci \
    "$@"
