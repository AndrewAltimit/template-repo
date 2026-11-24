#!/usr/bin/env bash
# Infrastructure as code for the recurrent-depth stack.
#
#   scripts/infra.sh test                          offline: fmt, validate, terraform test, Python tests
#   scripts/infra.sh plan     [--emulator] [unit]  plan all units (or one)
#   scripts/infra.sh apply    [--emulator] [unit]  apply; real AWS also needs --yes
#   scripts/infra.sh destroy  [--emulator] [unit]  destroy; real AWS also needs --yes
#   scripts/infra.sh output   [--emulator] unit    print a unit's outputs as JSON
#   scripts/infra.sh bootstrap-state --yes         create the S3 state bucket (real AWS, once)
#
# Units, in dependency order: results-store, network, node-iam, gpu-node, guardrails.
# None of them starts an instance. scripts/node.sh launches nodes from the templates.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

usage() { sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2; }

cmd="${1:-}"; shift || true
target=aws; yes=false; unit=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --emulator) target=emulator ;;
    --yes) yes=true ;;
    -h|--help) usage ;;
    -*) die "unknown option $1" ;;
    *) unit="$1" ;;
  esac
  shift
done
if [[ -n "$unit" && ! -d "$RDS_DIR/live/$unit" ]]; then die "no unit named $unit under live/"; fi

# Real AWS: derive the account-scoped state bucket and the results bucket suffix.
prepare_aws() {
  local account
  account="$(tf_run aws 'aws sts get-caller-identity --query Account --output text' | tr -d '\r')"
  [[ "$account" =~ ^[0-9]{12}$ ]] || die "could not read the AWS account id"
  export RDS_STATE_BUCKET="rds-tfstate-$account-${AWS_REGION:-us-east-1}"
  export RDS_BUCKET_SUFFIX="$account"
  log "account $account, region ${AWS_REGION:-us-east-1}, state bucket $RDS_STATE_BUCKET"
}

terragrunt_cmd() {
  local action="$1"
  if [[ -n "$unit" ]]; then
    echo "cd live/$unit && terragrunt $action"
  else
    echo "cd live && terragrunt run --all $action"
  fi
}

case "$cmd" in
  test)
    log "terraform fmt, validate and unit tests (mocked provider, offline)"
    ensure_image "$TF_IMAGE" terraform-ci ci
    docker run --rm -v "$(host_path "$REPO_ROOT"):/workspace" -w "$CONTAINER_RDS" \
      -e TF_PLUGIN_CACHE_DIR="$CONTAINER_RDS/.cache/terraform-plugins" -e TF_IN_AUTOMATION=1 \
      --entrypoint bash "$TF_IMAGE" -c '
        set -euo pipefail
        mkdir -p .cache/terraform-plugins
        terraform fmt -check -recursive .
        terragrunt hcl fmt --check --working-dir . >/dev/null
        for m in modules/*/; do
          echo "== $m"
          (cd "$m" && terraform init -backend=false -input=false >/dev/null \
            && terraform validate -no-color && terraform test -no-color \
            ; rc=$?; rm -rf .terraform .terraform.lock.hcl .build; exit $rc)
        done'
    log "python tests for the reaper and the node bootstrap"
    py_run -- 'python -m pytest -q -p no:cacheprovider infra/aws/recurrent-depth/tests -m "not emulator"'
    ;;
  plan|apply|destroy|output)
    if [[ "$target" == "aws" ]]; then
      if [[ "$cmd" != "plan" && "$cmd" != "output" && "$yes" != true ]]; then
        die "$cmd against real AWS needs --yes (run plan first and read it)"
      fi
      prepare_aws
    fi
    case "$cmd" in
      plan) tg="$(terragrunt_cmd plan)" ;;
      apply) tg="$(terragrunt_cmd apply)"; [[ -n "$unit" ]] && tg="$tg -auto-approve" ;;
      destroy) tg="$(terragrunt_cmd destroy)"; [[ -n "$unit" ]] && tg="$tg -auto-approve" ;;
      output)
        [[ -n "$unit" ]] || die "output needs a unit name"
        tg="cd live/$unit && terragrunt output -json"
        ;;
    esac
    tf_run "$target" "set -euo pipefail; mkdir -p .cache/terraform-plugins; $tg"
    ;;
  bootstrap-state)
    [[ "$yes" == true ]] || die "bootstrap-state creates a real S3 bucket; rerun with --yes"
    prepare_aws
    region="${AWS_REGION:-us-east-1}"
    tf_run aws "
      set -euo pipefail
      b=$(shell_quote "$RDS_STATE_BUCKET")
      if aws s3api head-bucket --bucket \"\$b\" 2>/dev/null; then echo \"state bucket \$b exists\"; exit 0; fi
      if [[ $(shell_quote "$region") == us-east-1 ]]; then aws s3api create-bucket --bucket \"\$b\";
      else aws s3api create-bucket --bucket \"\$b\" --create-bucket-configuration LocationConstraint=$(shell_quote "$region"); fi
      aws s3api put-bucket-versioning --bucket \"\$b\" --versioning-configuration Status=Enabled
      aws s3api put-public-access-block --bucket \"\$b\" --public-access-block-configuration \
        BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
      aws s3api put-bucket-encryption --bucket \"\$b\" --server-side-encryption-configuration \
        '{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}'
      echo \"created state bucket \$b\""
    ;;
  *)
    usage
    ;;
esac
