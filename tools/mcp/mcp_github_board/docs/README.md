# GitHub Board MCP Server: Usage Guide

This guide covers how agents should use the board tools and how to
troubleshoot the server. The full tool, parameter and flag reference is in
the crate [README](../README.md).

## Installation

### Docker (used by this repository)

```bash
docker compose --profile services build mcp-github-board
docker compose --profile services up -d mcp-github-board      # HTTP on :8022
docker compose --profile services run --rm -T mcp-github-board \
  mcp-github-board --mode stdio                                # STDIO
```

The image contains both `mcp-github-board` and `board-manager`. The repository
is mounted read-only at `/app`, which is the working directory, so
`ai-agents-board.yml` and `.agents.yaml` are picked up automatically.

### Pre-built binary

Releases publish `mcp-github-board-linux-x64`:

```bash
curl -L https://github.com/AndrewAltimit/template-repo/releases/latest/download/mcp-github-board-linux-x64 -o mcp-github-board
chmod +x mcp-github-board
```

`board-manager` must be installed separately (see
[board-manager](../../../rust/board-manager/README.md)).

### From source

```bash
cd tools/rust/board-manager && cargo build --release && ./install.sh
cd ../../mcp/mcp_github_board && cargo build --release
```

## Agent workflow

1. **Find work**: `query_ready_work` with your `agent_name`. Add
   `approved_only: true` when you may only work on issues an admin approved
   with `[Approved][Agent]`.
2. **Claim**: `claim_work` with a `session_id` you keep for the whole task.
   If the result is an error with `claimed_by`, someone else holds the issue:
   pick another one. Do not retry the same issue in a loop.
3. **Mark progress**: `claim_work` already sets `In Progress`. Use
   `update_status` for other transitions.
4. **Long tasks**: call `renew_claim` with the same `agent_name` and
   `session_id` well before the board's claim timeout (24h by default; see
   `get_board_config`). A renewal error means your claim is gone; claim again
   before continuing.
5. **Record findings**: file new issues, then `add_to_board`,
   `mark_discovered_from` (child -> parent) and `add_blocker` where needed.
   Use `get_dependency_graph` to see why an issue is not ready.
6. **Finish**: `release_work` with `pr_created` (PR opened, status unchanged),
   `completed`, `blocked` (sets Blocked), or `abandoned` / `error` (sets
   Abandoned).

Maintenance: `release_stale_claims` (dry run by default) lists claims with no
activity past the threshold; run it with `dry_run: false` to release them and
reset the status.

For read-only agents or dashboards start the server with `--read-only`
(or `GITHUB_BOARD_READ_ONLY=true`); only the query tools are registered.

## Error handling

- JSON-RPC `Invalid params` (-32602): the arguments were rejected locally
  (missing field, wrong type, issue number 0, unknown status, an issue
  blocking itself). Nothing was sent to GitHub.
- Tool result with `isError: true`: the body is
  `{"success": false, "error": "...", "error_kind": "..."}`. The `error` text is
  board-manager's own `Error:` line when it failed.

## Troubleshooting

Run `board_status` first. It does not call GitHub and reports whether
board-manager was found, its version, the timeout, and which token variables
are set.

| Symptom | Cause / fix |
|---------|-------------|
| `error_kind: board_manager_not_found` | Build and install board-manager, put it on PATH, or pass `--board-manager` / `BOARD_MANAGER_PATH`. The message lists every path searched. |
| `Authentication failed: GitHub token required` | Set `GITHUB_PROJECTS_TOKEN` (preferred) or `GITHUB_TOKEN` / `GH_TOKEN`. In Docker, make sure the variable is passed through by `docker-compose.yml` / `.mcp.json`. |
| `Configuration error: ...` | No board config found. Run from the repo root (where `ai-agents-board.yml` lives), pass `--board-config`, or set `BOARD_CONFIG_PATH`. |
| `Issue #N is not on the project board` | Add it with `add_to_board`. |
| `error_kind: timeout` | GitHub rate limiting or network trouble. Raise `--timeout-secs`. A timed-out write may still have been applied; check with `get_issue_details` before retrying. |
| `Field '...' not found on project` | The board is missing a field named in `fields.*` of `ai-agents-board.yml`. |

Enable debug logs with `--log-level debug` (or `RUST_LOG=debug`); every
board-manager invocation is logged to stderr.

## Related documentation

- [Crate README (reference)](../README.md)
- [board-manager CLI](../../../rust/board-manager/README.md)
- [Board workflow](../../../../docs/agents/board-workflow.md)
- [MCP Core Rust](../../mcp_core_rust/README.md)
