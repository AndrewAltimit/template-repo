# Recurrent-Depth Measurement Stack (AWS)

Terraform and Terragrunt for renting GPU nodes by the hour to run the
`recurrent_depth` toolkit against self-hosted models: first small looped models
(Huginn, Ouro) to calibrate the probes, later frontier-scale ones (GLM-5.x).
The plan and its pre-registered predictions are in
`packages/recurrent_depth/reports/2026-11-looped-calibration/PREDICTIONS.md`.

**Status:** nothing is deployed. Every module is unit-tested offline and the
whole stack is tested end to end against the local AWS Emulator. Nothing has
run against real AWS yet; see [Not yet verified](#not-yet-verified).

## What it creates

| Unit | Resources | Cost while idle |
|---|---|---|
| `results-store` | Private, versioned, encrypted S3 bucket; TLS-only policy; old versions expire after 30 days, the `weights/` mirror after 14 | Storage only (about $0.023 per GB-month) |
| `network` | VPC, a public subnet in each of 3 zones, no inbound rules, free S3 gateway endpoint | None |
| `node-iam` | Instance role: read `bundles/` and `weights/`, write `runs/` and `weights/`, never delete | None |
| `gpu-node` | One launch template per tier. **No instances.** | None |
| `guardrails` | Reaper Lambda every 5 minutes; monthly AWS Budget with email alerts | Effectively none |

Instances exist only between `scripts/node.sh launch` and the node shutting itself down.

## Four limits on spend

A node can only cost money while it runs, so four independent mechanisms stop it:

1. **Campaign deadline.** `recurrent-depth campaign run` will not start a stage past `max_wall_hours` and stops a stage that reaches it, after checkpointing what it wrote.
2. **Node watchdog.** The first thing the bootstrap does, before downloading anything, is `shutdown -h +<MaxHours>`. Every exit path, success or failure, uploads the log and powers off. The launch template makes power-off terminate the instance.
3. **Reaper Lambda.** Every 5 minutes it terminates any `Project=recurrent-depth` instance older than its `MaxHours` tag, capped by the tier's `HardCapHours` and a 12-hour global cap, plus 15 minutes of grace. Its IAM policy can only terminate instances that carry the project tag.
4. **AWS Budget.** Emails at 50%, 80% and 100% of a monthly limit, and at 100% of forecast. It is created only when `RDS_ALERT_EMAILS` is set.

`node.sh launch` refuses a `--max-hours` above the tier cap, and against real AWS it is a dry run unless `--yes` is given.

## Tiers

| Tier | Instance | GPU memory | Hard cap | Used for |
|---|---|---|---|---|
| `single-gpu` | g6.xlarge | 1x L4, 24 GB | 4 h | Huginn-0125, Ouro 1.4B and 2.6B, 1.7B controls (calibration tier 1) |
| `single-gpu-large` | g6e.xlarge | 1x L40S, 48 GB | 4 h | Longer contexts, or two models resident |
| `frontier` | p5en.48xlarge | 8x H200, about 1.1 TB, plus 8 local NVMe drives | 8 h | GLM-5.3 and GLM-5.4 in FP8 |

On-demand prices change and differ by region; check them before launching. As
a rough guide, the single-GPU tiers cost a few dollars an hour and the frontier
tier tens of dollars an hour. New accounts usually have a GPU vCPU quota of 0,
so request a quota increase days ahead. For the frontier tier, EC2 Capacity
Blocks are often the only way to get a node at a known time.

## Checkpoints

Every campaign stage uploads its outputs to `s3://<bucket>/runs/<run_id>/` the
moment it finishes, and partial output every 2 minutes while it runs:

```
runs/<run_id>/manifest.json           the manifest the run uses
runs/<run_id>/_HEARTBEAT.json         current stage, elapsed and remaining time
runs/<run_id>/_CAMPAIGN.json          final status: completed, failed or deadline
runs/<run_id>/stages/<stage>/...      records, logs, _SUCCESS.json with SHA-256 per file
runs/<run_id>/node/bootstrap-*.log    the node's boot log
```

Relaunching with the same run id resumes: finished stages are skipped and their
files restored for later stages; only unfinished stages run again. A resume with
a different manifest is refused.

## Order of operations

All commands run in containers (`terraform-ci`, `python-ci`, the emulator image).
From the repository root:

```bash
S=infra/aws/recurrent-depth/scripts

# 0. Offline checks, free: fmt, validate, terraform test (mocked provider), reaper and bootstrap tests
$S/infra.sh test

# 1. Full rehearsal against the local AWS Emulator, free: apply every unit,
#    checkpoint through boto3, launch a node, reap it, destroy
$S/emulator-e2e.sh

# 2. Real AWS, once per account: the Terraform state bucket
$S/infra.sh bootstrap-state --yes

# 3. Plan, read it, then apply
RDS_ALERT_EMAILS=you@example.com RDS_MONTHLY_BUDGET_USD=300 $S/infra.sh plan
RDS_ALERT_EMAILS=you@example.com RDS_MONTHLY_BUDGET_USD=300 $S/infra.sh apply --yes

# 4. A run: upload the bundle, dry-run the launch, then launch
$S/node.sh bundle --run-id calib-t1-001 \
  --manifest packages/recurrent_depth/campaigns/calibration/tier1-gpu.json \
  --requirements packages/recurrent_depth/campaigns/calibration/requirements-tier1.txt \
  --include packages/recurrent_depth/campaigns/calibration/plans
$S/node.sh launch --run-id calib-t1-001 --tier single-gpu --max-hours 3.5         # dry run
$S/node.sh launch --run-id calib-t1-001 --tier single-gpu --max-hours 3.5 --yes   # starts billing

# 5. Watch, fetch, stop early if needed
$S/node.sh status --run-id calib-t1-001
$S/node.sh fetch --run-id calib-t1-001 --dest outputs/rds/calibration/calib-t1-001
$S/node.sh terminate --run-id calib-t1-001 --yes

# 6. Tear down (the bucket refuses to be destroyed while it holds results)
$S/infra.sh destroy --yes
```

The suggested ladder: tier 0 on a workstation (free), one rehearsal of tier 1 on
`single-gpu` with `max_wall_hours` cut to 0.5 to shake out setup problems, the
full tier 1, then the frontier tier once GLM-5.4's weights are public.

## Layout

```
root.hcl                   provider and backend per target (RDS_TARGET=aws or emulator)
live/<unit>/terragrunt.hcl the five units and their dependencies
modules/<unit>/            Terraform modules, each with tests/*.tftest.hcl
modules/gpu-node/bootstrap.sh.tftpl   the node boot script
modules/guardrails/lambda/reaper.py   the reaper
scripts/infra.sh           test, plan, apply, destroy, output, bootstrap-state
scripts/node.sh            bundle, launch, status, terminate, fetch
scripts/emulator.sh        start, status, stop the AWS Emulator
scripts/emulator-e2e.sh    the end-to-end rehearsal
tests/                     reaper unit tests, sandboxed bootstrap tests, emulator e2e tests
```

## The AWS Emulator

[AWS Emulator](https://github.com/aws/aws-emulator) (CC0-1.0) serves the AWS
APIs locally over HTTPS. AWS publishes no image, so `docker/aws-emulator.Dockerfile`
builds one from the official RPM, following AWS's Docker guide. The scripts run
it on `127.0.0.1:9297` with request authentication off and telemetry off, and
point client containers at it by sharing its network namespace, so the
emulator's certificate for 127.0.0.1 validates. State is in memory and
disappears when it stops.

In emulator mode (`RDS_TARGET=emulator`) the stack differs from real AWS in four
places only: provider endpoints and dummy credentials, local Terraform state in
`.emulator-state/`, a placeholder AMI id (there is no public Deep Learning AMI
parameter), and `force_destroy` on the bucket so teardown works.

Tested against emulator 1.0.588: all five units apply and destroy; boto3
checkpoints, resume and fetch through `S3Store`; `node.sh` bundle, launch,
status and terminate; and the reaper terminating an overdue instance. The
emulator does not boot instances, so the bootstrap script is tested separately
by running it in a sandbox with stubbed `curl`, `aws`, `shutdown` and `python3`
(`tests/test_bootstrap.py`).

## Not yet verified

These need a real account and are the point of the tier 1 rehearsal:

- The Deep Learning AMI SSM parameter path and its root device name (`/dev/sda1`).
- That the AMI ships `python3 -m venv`, `mdadm` and the AWS CLI, which the bootstrap assumes.
- The pinned versions in `requirements-tier1.txt`, and Huginn's modeling code running under transformers 4.54.
- GPU quotas and on-demand capacity for each tier in the chosen region.
- That the toolkit's per-request Huginn settings (`num_steps`, adaptive `criterion`) reach the model as the model card describes; the server is tested only with a scripted backend.
