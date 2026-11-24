#!/usr/bin/env bash
# Launch and manage measurement nodes. Nothing here runs unless asked, and
# launching against real AWS is a dry run unless --yes is given.
#
#   scripts/node.sh bundle    --run-id ID --manifest FILE [--requirements FILE] [--include PATH]...
#                             build the toolkit wheel and upload a run bundle to s3://BUCKET/bundles/ID/
#   scripts/node.sh launch    --run-id ID --tier TIER --max-hours H [--az ZONE] [--yes]
#                             start one node from the tier's launch template; it runs the bundle,
#                             checkpoints to s3://BUCKET/runs/ID/ and terminates itself
#   scripts/node.sh status    [--run-id ID]      nodes and the run's heartbeat
#   scripts/node.sh terminate --run-id ID | --all [--yes]
#   scripts/node.sh fetch     --run-id ID --dest DIR
#
# Add --emulator to any command to run it against the local AWS Emulator.
# BUCKET comes from RDS_BUCKET or the results-store unit's output.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

usage() { sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2; }

cmd="${1:-}"; shift || true
target=aws; yes=false; run_id=""; tier=""; max_hours=""; az=""; manifest=""; requirements=""; dest=""; all=false
includes=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --emulator) target=emulator ;;
    --yes) yes=true ;;
    --all) all=true ;;
    --run-id) run_id="$2"; shift ;;
    --tier) tier="$2"; shift ;;
    --max-hours) max_hours="$2"; shift ;;
    --az) az="$2"; shift ;;
    --manifest) manifest="$2"; shift ;;
    --requirements) requirements="$2"; shift ;;
    --include) includes+=("$2"); shift ;;
    --dest) dest="$2"; shift ;;
    -h|--help) usage ;;
    *) die "unknown argument $1" ;;
  esac
  shift
done

check_run_id() {
  [[ "$run_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$ ]] || die "--run-id must be [A-Za-z0-9._-], at most 100 characters"
}

bucket() {
  if [[ -n "${RDS_BUCKET:-}" ]]; then echo "$RDS_BUCKET"; return; fi
  local name
  name="$(tf_run "$target" 'cd live/results-store && terragrunt output -raw bucket_name' 2>/dev/null | tr -d '
' | tail -1)"
  [[ "$name" =~ ^[a-z0-9.-]{3,63}$ ]] || die "could not read the bucket name; set RDS_BUCKET or apply the results-store unit"
  echo "$name"
}

# A staging directory inside the repo (gitignored) so containers can see it.
stage_dir() { echo "$RDS_DIR/.cache/bundles/$run_id"; }

aws_in() { tf_run "$target" "set -euo pipefail; $*"; }

case "$cmd" in
  bundle)
    check_run_id
    [[ -f "$manifest" ]] || die "--manifest must name an existing file"
    b="$(bucket)"
    dir="$(stage_dir)"
    rm -rf -- "${dir:?}"
    mkdir -p "$dir"
    cp "$manifest" "$dir/manifest.json"
    [[ -z "$requirements" ]] || cp "$requirements" "$dir/requirements.txt"
    for p in "${includes[@]}"; do cp -r "$p" "$dir/"; done
    log "validating the manifest and building the toolkit wheel"
    rel="infra/aws/recurrent-depth/.cache/bundles/$run_id"
    py_run -- "set -euo pipefail
      python -m recurrent_depth campaign run $rel/manifest.json --dry-run --run-id $(shell_quote "$run_id") >/dev/null
      pip wheel --quiet --no-deps --wheel-dir $rel packages/recurrent_depth"
    log "uploading bundle to s3://$b/bundles/$run_id/"
    aws_in "aws s3 cp $(shell_quote ".cache/bundles/$run_id/") $(shell_quote "s3://$b/bundles/$run_id/") --recursive --only-show-errors
      aws s3 ls $(shell_quote "s3://$b/bundles/$run_id/")"
    ;;

  launch)
    check_run_id
    [[ -n "$tier" ]] || die "--tier is required (single-gpu, single-gpu-large, frontier)"
    [[ "$max_hours" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "--max-hours must be a positive number"
    if [[ "$target" == emulator ]]; then yes=true; fi # nothing real to pay for
    b="$(bucket)"
    env_name="${RDS_ENVIRONMENT:-dev}"
    template="recurrent-depth-$env_name-$tier"
    az_filter=""
    [[ -z "$az" ]] || az_filter="Name=availability-zone,Values=$(shell_quote "$az")"
    script="
      t=$(shell_quote "$template"); rid=$(shell_quote "$run_id"); hours=$(shell_quote "$max_hours"); b=$(shell_quote "$b")
      aws s3api head-object --bucket \"\$b\" --key \"bundles/\$rid/manifest.json\" >/dev/null \
        || { echo 'no bundle for this run id; run node.sh bundle first' >&2; exit 1; }
      if aws s3api head-object --bucket \"\$b\" --key \"runs/\$rid/_CAMPAIGN.json\" >/dev/null 2>&1; then
        echo 'note: this run id already finished once; the node will only rerun stages without a checkpoint' >&2
      fi
      q='LaunchTemplateVersions[0].LaunchTemplateData'
      itype=\$(aws ec2 describe-launch-template-versions --launch-template-name \"\$t\" --versions '\$Default'         --query \"\$q.InstanceType\" --output text 2>/dev/null || true)
      [[ -n \"\$itype\" && \"\$itype\" != None ]] || { echo \"launch template \$t not found\" >&2; exit 1; }
      cap=\$(aws ec2 describe-launch-template-versions --launch-template-name \"\$t\" --versions '\$Default'         --query \"\$q.TagSpecifications[?ResourceType=='instance'].Tags[] | [?Key=='HardCapHours'].Value | [0]\" --output text)
      [[ \"\$cap\" != None ]] || cap=''
      if [[ -n \"\$cap\" ]] && awk -v h=\"\$hours\" -v c=\"\$cap\" 'BEGIN{exit !(h>c)}'; then
        echo \"--max-hours \$hours exceeds the \$t cap of \$cap hours\" >&2; exit 1
      fi
      subnet=\$(aws ec2 describe-subnets --filters Name=tag:Project,Values=recurrent-depth $az_filter \
        --query 'Subnets[0].SubnetId' --output text)
      [[ \"\$subnet\" != None && -n \"\$subnet\" ]] || { echo 'no recurrent-depth subnet found' >&2; exit 1; }
      tags=\"ResourceType=instance,Tags=[{Key=Project,Value=recurrent-depth},{Key=RunId,Value=\$rid},{Key=MaxHours,Value=\$hours},{Key=Tier,Value=$(shell_quote "$tier")},{Key=HardCapHours,Value=\${cap:-\$hours}},{Key=Name,Value=rds-\$rid}]\"
      echo \"template \$t (\$itype), subnet \$subnet, run \$rid, at most \$hours h (cap \${cap:-unknown} h)\" >&2
      if [[ $(shell_quote "$yes") != true ]]; then
        echo 'dry run: nothing launched. Check the instance type price for the hours above, then rerun with --yes.' >&2
        exit 0
      fi
      aws ec2 run-instances --launch-template LaunchTemplateName=\"\$t\" --subnet-id \"\$subnet\" \
        --count 1 --tag-specifications \"\$tags\" --query 'Instances[0].InstanceId' --output text"
    aws_in "$script"
    ;;

  status)
    filter="Name=tag:Project,Values=recurrent-depth"
    [[ -z "$run_id" ]] || { check_run_id; filter="$filter Name=tag:RunId,Values=$run_id"; }
    aws_in "aws ec2 describe-instances --filters $filter \
      Name=instance-state-name,Values=pending,running,stopping,shutting-down \
      --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,LaunchTime,Tags[?Key==\`RunId\`]|[0].Value]' \
      --output table"
    if [[ -n "$run_id" ]]; then
      b="$(bucket)"
      aws_in "aws s3 cp $(shell_quote "s3://$b/runs/$run_id/_HEARTBEAT.json") - 2>/dev/null || echo 'no heartbeat yet'"
    fi
    ;;

  terminate)
    if [[ "$all" == true ]]; then
      filter="Name=tag:Project,Values=recurrent-depth"
    else
      check_run_id
      filter="Name=tag:Project,Values=recurrent-depth Name=tag:RunId,Values=$run_id"
    fi
    [[ "$target" == emulator || "$yes" == true ]] || die "terminate needs --yes"
    aws_in "ids=\$(aws ec2 describe-instances --filters $filter Name=instance-state-name,Values=pending,running,stopping \
        --query 'Reservations[].Instances[].InstanceId' --output text)
      if [[ -z \"\$ids\" ]]; then echo 'no matching instances'; exit 0; fi
      aws ec2 terminate-instances --instance-ids \$ids --query 'TerminatingInstances[].[InstanceId,CurrentState.Name]' --output text"
    ;;

  fetch)
    check_run_id
    [[ -n "$dest" ]] || die "--dest is required"
    b="$(bucket)"
    mkdir -p "$RDS_DIR/.cache/fetch/$run_id"
    aws_in "aws s3 sync $(shell_quote "s3://$b/runs/$run_id/") $(shell_quote ".cache/fetch/$run_id/") --only-show-errors"
    mkdir -p "$dest"
    cp -r "$RDS_DIR/.cache/fetch/$run_id/." "$dest/"
    log "fetched s3://$b/runs/$run_id/ into $dest"
    ;;

  *)
    usage
    ;;
esac
