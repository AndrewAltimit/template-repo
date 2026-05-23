#!/usr/bin/env bash
# Self-hosted runner job-started hook.
#
# Runs BEFORE every job on the runner (including before `actions/checkout`).
# Its job is to remove root-owned bind-mount artifacts that a Docker container
# may have left in the workspace (e.g. `outputs/`, `evaluation_results/`), so
# checkout's clean step does not fail with:
#
#     Error: File was unable to be removed
#     Error: EACCES: permission denied, rmdir '.../outputs/blender'
#
# Docker's daemon runs as root, so missing bind-mount source directories it
# auto-creates (and anything a root container writes) are owned by root and the
# unprivileged runner user cannot delete them. This hook uses busybox-as-root
# via Docker to remove them without needing passwordless sudo -- the same
# technique as .github/actions/pre-checkout-cleanup, but applied universally to
# every workflow (and to leftovers from manual `docker compose` runs on the
# host, which no per-workflow step can cover).
#
# ── Activation ────────────────────────────────────────────────────────────
# Install this at a STABLE path OUTSIDE any workspace (the workspace is wiped
# per job), then point the runner at it via its .env and restart the service:
#
#   install -m 0755 automation/setup/runner/job-started-hook.sh \
#       "$HOME/.actions-runner-hooks/job-started.sh"
#   echo 'ACTIONS_RUNNER_HOOK_JOB_STARTED='"$HOME"'/.actions-runner-hooks/job-started.sh' \
#       >> /path/to/actions-runner/.env
#   ( cd /path/to/actions-runner && sudo ./svc.sh stop && sudo ./svc.sh start )
#
# The hook always exits 0: a cleanup failure must never fail the job itself.

set -u

WS="${GITHUB_WORKSPACE:-}"

# GITHUB_WORKSPACE may not be set for some job types; fall back to nothing.
[ -n "$WS" ] || exit 0
[ -d "$WS" ] || exit 0

# Only the regenerable, gitignored artifacts are removed -- never source or
# .git history.
if command -v docker >/dev/null 2>&1; then
    # Remove root-owned targets as root inside a throwaway container.
    timeout 60 docker run --rm -v "$WS:/ws" busybox:1.36.1 \
        sh -c 'rm -rf /ws/outputs /ws/evaluation_results /ws/.git/index.lock 2>/dev/null || true' \
        >/dev/null 2>&1 || true
else
    # No Docker: best-effort as the runner user (handles non-root leftovers).
    rm -rf "${WS:?}/outputs" "${WS:?}/evaluation_results" "${WS:?}/.git/index.lock" 2>/dev/null || true
fi

exit 0
