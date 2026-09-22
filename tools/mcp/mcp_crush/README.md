# Crush MCP Server (Rust)

> MCP server that consults the [Crush](https://github.com/charmbracelet/crush)
> CLI (`crush run`) through OpenRouter for quick code generation,
> explanation, and conversion.

## Overview

- Each consultation runs `crush run` once, non-interactively. The prompt is
  sent on **stdin** (no argv length limit, not visible in `ps`).
- Default model `qwen/qwen3.7-max` (matching `.agents.yaml`), pinned by
  generating a crush config and pointing `CRUSH_GLOBAL_CONFIG` at it.
  Override per call with `model`, or set `CRUSH_MODEL=` (empty) to use
  crush's own configuration.
- Four modes: `quick`, `generate`, `explain`, `convert`.
- Runs crush locally or inside a docker compose service; the `mcp-crush`
  image bundles a pinned, checksum-verified crush CLI.
- Crush is agentic (it has file and shell tools). Consultations run in a
  dedicated scratch working directory with their own data directory, and the
  prompt instructs crush to answer in text only.
- Hard timeout that kills the process (and removes the container in docker
  mode); captured output is size-capped; ANSI escapes are stripped.
- The child environment gets `OPENROUTER_API_KEY`, `DO_NOT_TRACK=1` (disables
  crush usage metrics), `NO_COLOR=1`, `TERM=dumb`. `OPENAI_API_KEY`,
  `GEMINI_API_KEY`, and `GOOGLE_API_KEY` are removed so crush cannot route to
  the vendors that are disabled in this repository.
- Consultations do not hold the integration lock while crush runs, so
  status/toggle/clear stay responsive.

## Quick Start

Container-first (recommended; the image contains both `mcp-crush` and `crush`):

```bash
docker compose build mcp-crush
docker compose --profile services run --rm -T mcp-crush mcp-crush --mode stdio
```

Local build (requires `crush` on PATH, or docker for the fallback):

```bash
cd tools/mcp/mcp_crush
cargo build --release
export OPENROUTER_API_KEY=sk-or-...
./target/release/mcp-crush --mode stdio
./target/release/mcp-crush --mode standalone --port 8015
```

## Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `consult_crush` | Ask crush | `query` (required), `context`, `mode`, `model`, `force`, `comparison_mode` |
| `crush_status` | Status, statistics, and effective configuration incl. resolved execution mode (no secrets) | none |
| `clear_crush_history` | Clear conversation history | none |
| `toggle_crush_auto_consult` | Set or flip the auto-consult flag | `enable` (optional bool) |

### `consult_crush` parameters

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `query` | string | required | The task, question, or code. Must not be blank. |
| `context` | string | `""` | Meaning depends on `mode` (see below). |
| `mode` | string | `quick` | One of `quick`, `generate`, `explain`, `convert`. Unknown modes are rejected. |
| `model` | string | `CRUSH_MODEL` | OpenRouter model id, e.g. `anthropic/claude-sonnet-4.6`. |
| `force` | bool | `false` | Consult even if `CRUSH_ENABLED=false`. |
| `comparison_mode` | bool | `true` | Accepted for backward compatibility; has no effect. |

### Modes

| Mode | `query` | `context` |
|------|---------|-----------|
| `quick` | Task or question; answer is concise (default) | Optional reference material |
| `generate` | Requirements; complete implementation requested | Optional reference material |
| `explain` | Code to explain | Optional focus, e.g. `"error handling"` |
| `convert` | Code to convert | **Required** target language, e.g. `"Rust"` |

### Response shape

```json
{
  "status": "success",
  "response": "...",
  "execution_time": 11.8,
  "consultation_id": "9b1e...",
  "mode": "convert",
  "execution": "local",
  "model": "qwen/qwen3.7-max"
}
```

`status` is `success`, `error`, `timeout`, or `disabled`; errors and timeouts
set the MCP `isError` flag. Optional fields: `input_truncated`,
`output_truncated` (stdout exceeded `CRUSH_MAX_OUTPUT`).

### Examples

```bash
curl -s -X POST http://localhost:8015/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "consult_crush", "arguments": {"query": "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)", "mode": "convert", "context": "Rust"}}'

curl -s -X POST http://localhost:8015/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "crush_status", "arguments": {}}'
```

## Execution modes

`CRUSH_EXECUTION` selects how crush runs:

| Value | Behaviour |
|-------|-----------|
| `auto` (default) | `local` if `CRUSH_BINARY` is found on PATH, else `docker` if the docker CLI is found, else an error explaining how to fix it |
| `local` | `crush run [--quiet] --cwd $CRUSH_WORKDIR --data-dir $CRUSH_DATA_DIR`, prompt on stdin |
| `docker` | `docker compose [-f $CRUSH_COMPOSE_FILE] run --rm -T --name mcp-crush-consult-<pid>-<n> $CRUSH_DOCKER_SERVICE sh -c <fixed script>`; the API key is forwarded by name (`-e OPENROUTER_API_KEY`), never on the command line. On timeout the container is removed with `docker rm -f`. |

The `mcp-crush` image sets `CRUSH_EXECUTION=local` and points
`CRUSH_DATA_DIR`/`CRUSH_WORKDIR`/`HOME` at writable directories under
`/var/lib/mcp-crush` (the repository is mounted read-only at `/app`).

## Configuration

Booleans accept `true/false/1/0/yes/no/on/off`. Invalid or out-of-range values
fall back to (or are clamped toward) the default with a warning on stderr.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | none | Required. Passed to crush via env only; never logged or returned. |
| `CRUSH_MODEL` | `qwen/qwen3.7-max` | Model pinned via generated crush config; set to empty to use crush's own config |
| `CRUSH_ENABLED` | `true` | When `false`, consultations return `disabled` unless `force=true` |
| `CRUSH_AUTO_CONSULT` | `true` | Advisory flag reported to clients; the server never consults on its own |
| `CRUSH_TIMEOUT` | `300` | Hard deadline in seconds per consultation (1-3600) |
| `CRUSH_MAX_PROMPT` | `32000` | Max characters of query + context; query has priority |
| `CRUSH_MAX_OUTPUT` | `1048576` | Max captured stdout bytes |
| `CRUSH_QUIET_MODE` | `true` | Pass `--quiet` (hide spinner) |
| `CRUSH_EXECUTION` | `auto` | `auto`, `local`, or `docker` |
| `CRUSH_BINARY` | `crush` | Executable name or path |
| `CRUSH_DATA_DIR` | `<tmp>/mcp-crush/data` | Crush data dir (sessions DB, logs, generated config) |
| `CRUSH_WORKDIR` | `<tmp>/mcp-crush/workspace` | Working directory for crush. Point it at a repository only if you want crush to read (and potentially modify) it. |
| `CRUSH_DOCKER_SERVICE` | `mcp-crush` | Compose service for docker mode |
| `CRUSH_COMPOSE_FILE` | none | Compose file for docker mode (default: compose's own lookup from the server's cwd) |
| `CRUSH_INCLUDE_HISTORY` | `true` | Prepend the last 3 exchanges to the prompt |
| `CRUSH_MAX_HISTORY` | `5` | Retained history entries (0 disables) |
| `CRUSH_LOG_CONSULTATIONS` | `true` | Log one line (id, status, time) per consultation; prompts are never logged |

A `.env` file in the working directory is loaded if present.

### CLI arguments (from `mcp-core`)

```
--mode <MODE>         standalone | stdio | server | client   [default: standalone]
--port <PORT>         HTTP port (ignored in stdio mode)      [default: 8000]
--backend-url <URL>   Backend URL (client mode)
--log-level <LEVEL>   Log level                              [default: info]
```

`docker-compose.yml` runs the service on port 8015.

## MCP client configuration

```json
{
  "mcpServers": {
    "crush": {
      "command": "docker",
      "args": ["compose", "-f", "./docker-compose.yml", "--profile", "services",
               "run", "--rm", "-T", "mcp-crush", "mcp-crush", "--mode", "stdio"]
    }
  }
}
```

## Development

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test            # offline: subprocesses are replaced by a fake runner
cargo build --release
```

| File | Purpose |
|------|---------|
| `src/main.rs` | CLI entry point |
| `src/server.rs` | Tool assembly |
| `src/crush.rs` | Prompt building, local/docker invocation, output handling |
| `src/runner.rs` | Subprocess boundary: stdin piping, capped capture, timeout + kill, PATH lookup |
| `src/config.rs` | Environment configuration (redacted `Debug`) |
| `src/consult.rs` | Generic consult/status tools and state (identical copy in `mcp_opencode`) |
| `src/util.rs` | UTF-8-safe truncation, secret redaction, env parsing (identical copy in `mcp_opencode`) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `OPENROUTER_API_KEY is not configured` | Export the key for the server process |
| `crush CLI 'crush' was not found on PATH and docker is not available` | Install crush, set `CRUSH_BINARY`, or use the `mcp-crush` image |
| `Could not find the crush executable` | `CRUSH_EXECUTION=local` but the binary is missing |
| `Crush failed (exit 1): ... unauthorized` | Invalid OpenRouter key |
| `status: timeout` | Raise `CRUSH_TIMEOUT`; crush may be doing agentic work, so keep queries focused |
| `Cannot create directory ...` | Make `CRUSH_DATA_DIR` / `CRUSH_WORKDIR` writable |

## Limitations

- Every consultation starts a fresh crush session; continuity comes only from
  the short history preamble (in-memory, process-wide, lost on restart).
- Crush may still attempt tool use despite the text-only instruction; the
  scratch working directory (and the read-only `/app` mount in the image)
  limits the blast radius. Do not point `CRUSH_WORKDIR` at a checkout you
  care about unless you accept that risk.
- Model pinning relies on crush's `CRUSH_GLOBAL_CONFIG` override; when a
  model is pinned, crush's user-level global config is not read.
- `comparison_mode` is accepted but ignored. No streaming.
