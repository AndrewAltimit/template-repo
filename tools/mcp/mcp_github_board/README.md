# GitHub Board MCP Server (Rust)

> MCP server for GitHub Projects v2 board operations: ready-work queue, work
> claims, status, dependencies, approvals and stale-claim cleanup for
> multi-agent coordination.

The server is a thin, validated MCP front end for the
[`board-manager`](../../rust/board-manager/README.md) CLI, which performs all
GitHub API calls. Every tool call becomes one
`board-manager --format json <subcommand> ...` process with a timeout.

```
MCP client --(stdio / HTTP)--> mcp-github-board --(argv, JSON stdout)--> board-manager --> GitHub GraphQL/REST
```

## Quick Start

```bash
# Build both binaries (container-first: see "Building" below)
cd tools/rust/board-manager && cargo build --release && ./install.sh   # -> ~/.local/bin
cd ../../mcp/mcp_github_board && cargo build --release

# STDIO mode (Claude Code / .mcp.json)
./target/release/mcp-github-board --mode stdio

# HTTP mode (default port 8022)
./target/release/mcp-github-board --mode standalone
curl http://localhost:8022/health
curl http://localhost:8022/mcp/tools
curl -X POST http://localhost:8022/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "query_ready_work", "arguments": {"agent_name": "claude", "limit": 5}}'
```

### Prerequisites

- `board-manager` binary (see [Discovery](#board-manager-discovery)).
- A GitHub token in `GITHUB_PROJECTS_TOKEN` (preferred; classic PAT with
  `project` and `repo` scopes), `GITHUB_TOKEN` or `GH_TOKEN`. Every board tool
  needs it, including `list_agents` and `get_board_config`.
- A board config: `ai-agents-board.yml` in the working directory or a parent
  (the repo root has one), `BOARD_CONFIG_PATH`, `--board-config`, or the
  `BOARD_PROJECT_NUMBER` / `BOARD_REPOSITORY` / `BOARD_OWNER` env vars.
  See the [board-manager configuration](../../rust/board-manager/README.md#configuration).
- For approvals and claim verification, `.agents.yaml` (searched upwards from
  the working directory).

## Tools

All issue numbers accept an integer or a string such as `"42"` / `"#42"`.
Enum values (status, reason, priority, type, size) are case- and
separator-insensitive (`in_progress` == `In Progress`).

| Tool | Mutates | Parameters (required in bold) | board-manager command |
|------|---------|-------------------------------|------------------------|
| `query_ready_work` | no | `agent_name`, `limit` (1-100, default 10), `approved_only` (default false), `include_labels`, `exclude_labels` | `ready` |
| `claim_work` | yes | **`issue_number`**, **`agent_name`**, **`session_id`** | `claim` |
| `renew_claim` | yes | **`issue_number`**, **`agent_name`**, **`session_id`** | `renew` |
| `release_work` | yes | **`issue_number`**, **`agent_name`**, `reason` (`completed` default, `pr_created`, `blocked`, `abandoned`, `error`) | `release` |
| `update_status` | yes | **`issue_number`**, **`status`** (`Todo`, `In Progress`, `Blocked`, `Done`, `Abandoned`) | `status` |
| `add_blocker` | yes | **`issue_number`** (blocked), **`blocker_number`** | `block` |
| `remove_blocker` | yes | **`issue_number`**, **`blocker_number`** | `unblock` |
| `mark_discovered_from` | yes | **`issue_number`** (child), **`parent_number`** | `discover-from` |
| `get_issue_details` | no | **`issue_number`** | `info` |
| `get_dependency_graph` | no | **`issue_number`** | `deps` |
| `list_agents` | no | - | `agents` |
| `get_board_config` | no | - | `config` |
| `add_to_board` | yes | **`issue_number`**, `status` (default `Todo`), `priority`, `type`, `size`, `agent_name` | `add-to-board` |
| `check_approval` | no | **`issue_number`**, `agent_name` | `check-approval` |
| `find_approved_issues` | no | `agent_name` (default `claude`), `unverified` (default false) | `find-approved` |
| `release_stale_claims` | yes | `agent_name`, `threshold_hours`, `reset_status` (default `Todo`), `dry_run` (**default true**) | `janitor` |
| `board_status` | no | - | local only (`--version` probe) |

Notes:

- `include_labels` / `exclude_labels` take an array of label names or a
  comma-separated string. Label filtering is case-insensitive.
- `release_work` reasons: `completed` and `pr_created` keep the status,
  `blocked` sets `Blocked`, `abandoned` / `error` set `Abandoned`.
- `add_to_board` without `agent_name` assigns `Claude Code` (board-manager
  default). If the issue is already on the board nothing changes and
  `already_on_board: true` is returned.
- `release_stale_claims` only reports unless `dry_run: false` is passed.
- `board_status` never calls GitHub; it reports the server version, read-only
  mode, registered tools, the resolved board-manager path/version (or why it
  is unusable), the timeout, and which token variables are set (names only).

### Response format

Success:

```json
{ "success": true, "result": <board-manager JSON output> }
```

Failure (MCP `isError: true`):

```json
{ "success": false, "error": "human readable reason", "error_kind": "board_manager_error" }
```

`error_kind` is one of `board_manager_not_found`, `spawn_failed`, `timeout`,
`board_manager_error` (the CLI reported an error, e.g. authentication, issue
not found) or `invalid_output`.

These outcomes are also reported as tool errors (`isError: true`,
`success: false`), with the board-manager JSON under `result`:

- `claim_work` when the issue is already claimed or the claim lost a race
  (`result.claimed_by`, `result.claimed_session`);
- `renew_claim` when the agent does not hold the active claim;
- `get_issue_details` / `get_dependency_graph` when the issue is not on the
  board.

Invalid arguments (missing required fields, wrong types, issue number 0,
unknown status, an issue blocking itself, ...) are rejected with a JSON-RPC
`Invalid params` error before any process is started.

### Examples

```json
{"tool": "claim_work", "arguments": {"issue_number": 42, "agent_name": "claude", "session_id": "run-8841"}}
{"tool": "update_status", "arguments": {"issue_number": 42, "status": "in_progress"}}
{"tool": "release_work", "arguments": {"issue_number": 42, "agent_name": "claude", "reason": "pr_created"}}
{"tool": "query_ready_work", "arguments": {"agent_name": "claude", "approved_only": true, "exclude_labels": ["wontfix"]}}
{"tool": "release_stale_claims", "arguments": {"agent_name": "claude", "threshold_hours": 12}}
```

A typical agent loop: `query_ready_work` -> `claim_work` -> (work, calling
`renew_claim` for long tasks, `mark_discovered_from` / `add_blocker` for new
findings) -> `release_work` with `pr_created` or `completed`. See
[`docs/agents/board-workflow.md`](../../../docs/agents/board-workflow.md).

## Configuration

### CLI flags and environment

| Flag | Env | Default | Meaning |
|------|-----|---------|---------|
| `--mode` | - | `standalone` | `standalone` (HTTP MCP), `stdio`, `server` (REST only), `client` (proxy) |
| `--port` | - | `8022` | HTTP port (ignored in stdio mode) |
| `--log-level` | `RUST_LOG` overrides | `info` | Logs always go to stderr |
| `--board-manager PATH` | `BOARD_MANAGER_PATH` | auto-discovery | Use this binary; discovery is disabled |
| `--board-config PATH` | - | board-manager lookup | Passed to every call as `--config` (file must exist) |
| `--timeout-secs N` | `GITHUB_BOARD_TIMEOUT_SECS` | `300` | Per-call timeout (1-3600); the child is killed on expiry |
| `--read-only` | `GITHUB_BOARD_READ_ONLY` | off | Register only non-mutating tools (see table) |

The default timeout is generous because board-manager waits out GitHub rate
limits for up to 5 minutes.

Variables read by board-manager (inherited by the child process):
`GITHUB_PROJECTS_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_GRAPHQL_URL`,
`GITHUB_API_URL`, `BOARD_MANAGER_HTTP_TIMEOUT_SECS`, `BOARD_CONFIG_PATH`,
`BOARD_PROJECT_NUMBER`, `BOARD_OWNER`, `BOARD_REPOSITORY`, `GITHUB_REPOSITORY`.
Note that `GITHUB_PROJECT_NUMBER` is **not** read by anything; use the config
file or `BOARD_PROJECT_NUMBER`.

### board-manager discovery

Without `--board-manager`, the first tool call (or `board_status`) searches,
in order, and verifies the binary with `--version` (10s timeout):

1. `PATH`
2. the directory containing `mcp-github-board`
3. `~/.local/bin`, `~/.cargo/bin`
4. `/usr/local/bin` (Unix)
5. `./tools/rust/board-manager/target/release` (working directory = repo root)

The result is cached; a failed search is not, so installing the binary later
works without a restart. If a cached binary disappears, it is rediscovered on
the next call. The error message lists every location searched.

### MCP configuration

This repository runs the server in Docker (see `.mcp.json`):

```json
"github-board": {
  "command": "docker",
  "args": ["compose", "-f", "./docker-compose.yml", "--profile", "services",
           "run", "--rm", "-T", "mcp-github-board", "mcp-github-board", "--mode", "stdio"],
  "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}", "GITHUB_REPOSITORY": "${GITHUB_REPOSITORY}" }
}
```

The image (`docker/mcp-github-board.Dockerfile`) contains both binaries; the
repository is mounted read-only at `/app` (the working directory), so
`ai-agents-board.yml` and `.agents.yaml` are found automatically.

Native alternative:

```json
"github-board": { "command": "mcp-github-board", "args": ["--mode", "stdio"] }
```

## Security

- Tool arguments are deserialized into typed structs; nothing is passed
  through a shell. String values are always passed as `--flag=value`, so a
  value beginning with `-` cannot be interpreted as another flag. Agent
  names (<= 64 chars), session ids (<= 128), and labels (<= 100, <= 50 per
  list) are trimmed and must not contain control characters.
- The child process gets `stdin` = `/dev/null`, so it can never consume the
  MCP stdio channel.
- `--read-only` removes every tool that writes to GitHub.
- `board_status` reports which token variables are set, never their values.
- Claim, approval and trust checks are enforced by board-manager
  (`.agents.yaml` allow lists); this server does not bypass them.

## Building and testing

```bash
# Container-first
docker compose build mcp-github-board

# Or natively, from tools/mcp/mcp_github_board
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
cargo build --release
```

Tests run offline: argument validation and argv construction for every tool
(`specs.rs`, `args.rs`), response shaping and error mapping through a mock
runner (`server.rs`), stderr/stdout interpretation and discovery ordering
(`runner.rs`), CLI flags (`main.rs`). On Unix, `runner.rs` additionally runs a
fake `board-manager` shell script to exercise real process spawning, error
propagation and timeout killing.

## Project structure

```
src/
  main.rs     CLI flags, server wiring
  server.rs   Tool implementations (spec-driven BoardTool, board_status), response shaping
  specs.rs    Tool table: schemas, typed args -> board-manager argv
  args.rs     Typed argument parsing and validation (issue numbers, enums, labels, names)
  runner.rs   board-manager discovery, process execution with timeout, output parsing
docs/README.md  Usage guide and troubleshooting
```

## Limitations

- One process per tool call; each call re-resolves the project and field
  metadata (one GraphQL query) inside board-manager.
- board-manager's human/`--format human` output and its local commands
  (`bucket-comments`, `trust-level`, `assess-fix`) are not exposed.
- A timed-out mutation may still have been applied on GitHub (for example a
  claim comment posted before the process was killed); re-check with
  `get_issue_details` before retrying.
