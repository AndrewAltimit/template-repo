#!/usr/bin/env bash
# Shared helpers for the recurrent-depth infrastructure scripts.
# Everything runs in containers: terraform-ci (Terraform, Terragrunt, AWS CLI),
# python-ci (tests, wheel builds) and the local AWS Emulator.

set -euo pipefail
export MSYS_NO_PATHCONV=1 # Git Bash on Windows: do not rewrite container paths

RDS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$RDS_DIR/../../.." && pwd)"
TF_IMAGE="${RDS_TF_IMAGE:-template-repo-terraform-ci}"
PY_IMAGE="${RDS_PY_IMAGE:-template-repo-python-ci:latest}"
EMU_IMAGE="${RDS_EMU_IMAGE:-template-repo-aws-emulator:local}"
EMU_NAME="${RDS_EMU_NAME:-rds-aws-emulator}"
EMU_PORT="${RDS_EMU_PORT:-9297}"
EMU_DIR="$RDS_DIR/.emulator"          # gitignored: CA certificate and local state
CONTAINER_RDS=/workspace/infra/aws/recurrent-depth

log() { printf '[rds] %s\n' "$*" >&2; }
die() { printf '[rds] error: %s\n' "$*" >&2; exit 1; }

# Docker on Windows wants a Windows-style host path for bind mounts.
host_path() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }

ensure_image() {
  local image="$1" service="$2" profile="$3"
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    log "building $service image"
    (cd "$REPO_ROOT" && docker compose --profile "$profile" build "$service")
  fi
}

emulator_running() {
  [[ "$(docker inspect -f '{{.State.Running}}' "$EMU_NAME" 2>/dev/null || true)" == "true" ]]
}

# Arguments that point a container at the emulator: share its network namespace
# so https://127.0.0.1:9297 matches the emulator's certificate.
emulator_docker_args() {
  emulator_running || die "the emulator is not running; start it with scripts/emulator.sh start"
  printf '%s\n' \
    --network "container:$EMU_NAME" \
    -e RDS_TARGET=emulator \
    -e "RDS_EMULATOR_ENDPOINT=https://127.0.0.1:$EMU_PORT" \
    -e "AWS_ENDPOINT_URL=https://127.0.0.1:$EMU_PORT" \
    -e "AWS_CA_BUNDLE=$CONTAINER_RDS/.emulator/ca.pem" \
    -e AWS_ACCESS_KEY_ID=emulator \
    -e AWS_SECRET_ACCESS_KEY=emulator \
    -e AWS_REGION=us-east-1 \
    -e AWS_DEFAULT_REGION=us-east-1 \
    -e AWS_EC2_METADATA_DISABLED=true \
    -e AWS_DISABLE_HOST_PREFIX_INJECTION=true
}

# Arguments for real AWS: export the host's credentials (SSO, profiles) as env vars.
aws_docker_args() {
  if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]] && command -v aws >/dev/null 2>&1; then
    eval "$(aws configure export-credentials --format env 2>/dev/null)" || true
  fi
  [[ -n "${AWS_ACCESS_KEY_ID:-}" ]] || die "no AWS credentials; run 'aws sso login' or export AWS_ACCESS_KEY_ID"
  printf '%s\n' -e RDS_TARGET=aws -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
    -e "AWS_REGION=${AWS_REGION:-us-east-1}" -e "AWS_DEFAULT_REGION=${AWS_REGION:-us-east-1}" \
    -e RDS_STATE_BUCKET -e RDS_BUCKET_SUFFIX -e RDS_ENVIRONMENT -e RDS_ALERT_EMAILS -e RDS_MONTHLY_BUDGET_USD \
    -e RDS_ENABLE_SSM
}

# tf_run <emulator|aws> <command...>: run a shell command in terraform-ci, cwd = this stack.
tf_run() {
  local target="$1"; shift
  ensure_image "$TF_IMAGE" terraform-ci ci
  local -a extra
  if [[ "$target" == "emulator" ]]; then
    mapfile -t extra < <(emulator_docker_args)
  else
    mapfile -t extra < <(aws_docker_args)
  fi
  mkdir -p "$RDS_DIR/.cache/terraform-plugins"
  docker run --rm -i \
    -v "$(host_path "$REPO_ROOT"):/workspace" \
    -e TF_PLUGIN_CACHE_DIR="$CONTAINER_RDS/.cache/terraform-plugins" \
    -e TF_IN_AUTOMATION=1 -e TG_NON_INTERACTIVE=true -e "RDS_ENVIRONMENT=${RDS_ENVIRONMENT:-dev}" \
    "${extra[@]}" \
    -w "$CONTAINER_RDS" --entrypoint bash "$TF_IMAGE" -c "$*"
}

# py_run [docker args...] -- <command>: run a shell command in python-ci from the repo root.
py_run() {
  local -a extra=()
  while [[ $# -gt 0 && "$1" != "--" ]]; do extra+=("$1"); shift; done
  shift || true
  docker run --rm -i -v "$(host_path "$REPO_ROOT"):/app" -w /app \
    -e PYTHONPATH=/app/packages/recurrent_depth/src -e PYTHONDONTWRITEBYTECODE=1 \
    "${extra[@]}" --entrypoint bash "$PY_IMAGE" -c "$*"
}

# shell_quote <args...>: quote arguments for embedding in a bash -c string.
shell_quote() { printf '%q ' "$@"; }
