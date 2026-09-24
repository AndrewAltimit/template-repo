#!/usr/bin/env bash
# Job queue for the 2026-09 backdoor experiment (Windows host, Git Bash, Docker Desktop + WSL2).
#
# Usage: queue.sh <job-list-file> <log-dir>
# Each non-empty, non-comment line of the job list is:
#   <output-json-relative-to-results-dir> <runner.py> <runner args...>
# A job is skipped when its output JSON already exists, so the queue can be restarted.
# Jobs run one at a time, each in a fresh GPU container named bdexp-<job>.
#
# Mounts: the worktree at /app (the package source is put first on PYTHONPATH, so the
# code under test is the worktree's, not the copy installed in the image), the
# sleeper-backdoor-work volume at /work (trained models, evaluation databases, scratch;
# also the working directory, so relative log/checkpoint paths land there) and the
# shared HF cache volume at /models.
set -u

JOBS="$1"
LOGDIR="$2"
WT="$(cd "$(dirname "$0")/../../../../../.." && pwd)"   # worktree root
RESULTS_REL="packages/sleeper_agents/docs/results/2026-09-backdoor-experiment"
IMAGE="${IMAGE:-sleeper-eval-gpu:regen-art}"
GIT_COMMIT="$(git -C "$WT" rev-parse HEAD)"
if git -C "$WT" diff --quiet HEAD -- packages/sleeper_agents/src packages/sleeper_agents/scripts; then
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
  MSYS_NO_PATHCONV=1 docker run --rm --gpus all --name "bdexp-$name" \
    -e HF_HOME=/models -e HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}" -e PYTHONUNBUFFERED=1 \
    -e PYTHONPATH=/app/packages/sleeper_agents/src -e EVAL_DB_PATH="/work/db/$name.db" \
    -e GIT_COMMIT="$GIT_COMMIT" -e GIT_DIRTY="$GIT_DIRTY" -e CONTAINER_IMAGE="$IMAGE" \
    -v template-repo_sleeper-models-cache:/models -v sleeper-backdoor-work:/work \
    -v "$(cygpath -w "$WT"):/app" -w /work "$IMAGE" \
    python "/app/$RESULTS_REL/runners/$runner" $args --out "/app/$RESULTS_REL/$out" \
    > "$LOGDIR/$name.log" 2>&1
  rc=$?
  echo "[queue] $(date -u +%FT%TZ) done $out rc=$rc wall=$(( $(date +%s) - start ))s"
done < "$JOBS"
echo "[queue] all done"
