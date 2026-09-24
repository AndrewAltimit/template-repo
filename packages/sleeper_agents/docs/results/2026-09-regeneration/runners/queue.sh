#!/usr/bin/env bash
# Job queue used for the 2026-09 regeneration (Windows host, Git Bash, Docker Desktop + WSL2).
#
# Usage: queue.sh <job-list-file> <log-dir>
# Each non-empty, non-comment line of the job list is:
#   <output-json-relative-to-results-dir> <runner.py> <runner args...>
# A job is skipped when its output JSON already exists, so the queue can be restarted.
# Jobs run one at a time, each in a fresh GPU container (one model in GPU memory at a time).
set -u

JOBS="$1"
LOGDIR="$2"
WT="$(cd "$(dirname "$0")/../../../../../.." && pwd)"   # worktree root
RESULTS_REL="packages/sleeper_agents/docs/results/2026-09-regeneration"
IMAGE="${IMAGE:-sleeper-eval-gpu:regen}"
GIT_COMMIT="$(git -C "$WT" rev-parse HEAD)"
if git -C "$WT" diff --quiet HEAD -- packages/sleeper_agents/src packages/sleeper_agents/scripts packages/sleeper_agents/examples; then
  GIT_DIRTY=false
else
  GIT_DIRTY=true
fi
mkdir -p "$LOGDIR"

while read -r out runner args; do
  [[ -z "${out:-}" || "$out" == \#* ]] && continue
  if [[ -f "$WT/$RESULTS_REL/$out" ]]; then
    echo "[queue] skip (exists): $out"
    continue
  fi
  name="$(basename "$out" .json)"
  echo "[queue] $(date -u +%FT%TZ) start $out"
  start=$(date +%s)
  # shellcheck disable=SC2086
  MSYS_NO_PATHCONV=1 docker run --rm --gpus all \
    -e HF_HOME=/models -e HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}" -e PYTHONUNBUFFERED=1 \
    -e GIT_COMMIT="$GIT_COMMIT" -e GIT_DIRTY="$GIT_DIRTY" -e CONTAINER_IMAGE="$IMAGE" \
    -v template-repo_sleeper-models-cache:/models -v sleeper-regen-work:/work \
    -v "$(cygpath -w "$WT"):/app" -w /app/packages/sleeper_agents "$IMAGE" \
    python "docs/results/2026-09-regeneration/runners/$runner" $args \
      --out "/app/$RESULTS_REL/$out" $( [[ "$runner" == run_train_probes.py ]] && echo "--work-dir /work/$name" ) \
    > "$LOGDIR/$name.log" 2>&1
  rc=$?
  echo "[queue] $(date -u +%FT%TZ) done $out rc=$rc wall=$(( $(date +%s) - start ))s"
done < "$JOBS"
echo "[queue] all done"
