#!/usr/bin/env bash
# End-to-end test of the whole stack against the local AWS Emulator. Free and
# offline apart from image and provider downloads; nothing touches real AWS.
#
#   1. start the emulator
#   2. apply every Terragrunt unit to it
#   3. run tests/test_emulator_e2e.py: checkpoints through boto3, a node
#      launched from a template, the reaper terminating it
#   4. upload a bundle and launch a node with scripts/node.sh
#   5. destroy every unit and stop the emulator (also on failure, unless --keep)

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

keep=false
[[ "${1:-}" == "--keep" ]] && keep=true

cleanup() {
  local code=$?
  if [[ "$keep" == true ]]; then
    log "--keep: leaving the emulator and its resources in place"
    exit $code
  fi
  log "destroying emulated resources"
  "$RDS_DIR/scripts/infra.sh" destroy --emulator >/dev/null 2>&1 || log "destroy reported errors (emulator state is discarded anyway)"
  "$RDS_DIR/scripts/emulator.sh" stop
  exit $code
}
trap cleanup EXIT

"$RDS_DIR/scripts/emulator.sh" start

log "applying all units to the emulator"
"$RDS_DIR/scripts/infra.sh" apply --emulator

bucket="$(tf_run emulator 'cd live/results-store && terragrunt output -raw bucket_name' | tr -d '\r' | tail -1)"
[[ -n "$bucket" ]] || die "no bucket output"
log "results bucket: $bucket"

log "python end-to-end tests (boto3 against the emulator)"
mapfile -t emu < <(emulator_docker_args)
# python-ci has no boto3; install it into a throwaway directory for this run only.
py_run "${emu[@]}" -e "RDS_E2E_BUCKET=$bucket" -e AWS_CA_BUNDLE=/app/infra/aws/recurrent-depth/.emulator/ca.pem -- "
  set -euo pipefail
  pip install --quiet --target /tmp/e2e-deps 'boto3>=1.40'
  PYTHONPATH=/tmp/e2e-deps:\$PYTHONPATH python -m pytest -q -rs -p no:cacheprovider -m emulator \
    infra/aws/recurrent-depth/tests/test_emulator_e2e.py"

log "node.sh: bundle and launch against the emulator"
manifest="$RDS_DIR/tests/fixtures/e2e-manifest.json"
RDS_BUCKET="$bucket" "$RDS_DIR/scripts/node.sh" bundle --emulator --run-id e2e-node --manifest "$manifest"
RDS_BUCKET="$bucket" "$RDS_DIR/scripts/node.sh" launch --emulator --run-id e2e-node --tier single-gpu --max-hours 1
RDS_BUCKET="$bucket" "$RDS_DIR/scripts/node.sh" status --emulator --run-id e2e-node
RDS_BUCKET="$bucket" "$RDS_DIR/scripts/node.sh" terminate --emulator --run-id e2e-node

log "end-to-end test passed"
