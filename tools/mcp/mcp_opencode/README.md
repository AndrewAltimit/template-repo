# OpenCode MCP Server (Rust)

> MCP server that consults an OpenRouter-hosted model for code generation,
> refactoring, review, and explanation.

## Overview

- One OpenRouter chat-completion request per consultation (default model
  `qwen/qwen3.7-max`, matching `.agents.yaml`). Despite the name, this server
  does **not** run the `opencode` CLI; the Docker image ships that CLI only so
  the `openrouter-agents` image can copy it.
- Five modes with task-specific system prompts: `quick`, `generate`,
  `refactor`, `review`, `explain`.
- Per-call overrides for `model`, `temperature`, and `max_tokens`.
- Bounded conversation history replayed as real chat turns.
- Retries with backoff on 408/429/5xx and connection errors (honours
  `Retry-After`), all inside one overall deadline.
- Responses include the serving model, `finish_reason`, and token `usage`.
- Consultations do not hold the integration lock during the HTTP call, so
  status/toggle/clear stay responsive and HTTP-mode requests run concurrently.

## Quick Start

```bash
cd tools/mcp/mcp_opencode
cargo build --release

export OPENROUTER_API_KEY=sk-or-...

# STDIO mode (Claude Code and other MCP clients)
./target/release/mcp-opencode --mode stdio

# Standalone HTTP mode
./target/release/mcp-opencode --mode standalone --port 8014
curl http://localhost:8014/health
```

Container-first (as configured in `.mcp.json`):

```bash
docker compose --profile services run --rm -T mcp-opencode mcp-opencode --mode stdio
```

## Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `consult_opencode` | Ask the model | `query` (required), `context`, `mode`, `model`, `temperature`, `max_tokens`, `force`, `comparison_mode` |
| `opencode_status` | Status, statistics, and effective configuration (no secrets) | none |
| `clear_opencode_history` | Clear conversation history | none |
| `toggle_opencode_auto_consult` | Set or flip the auto-consult flag | `enable` (optional bool) |

### `consult_opencode` parameters

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `query` | string | required | The question, task, or code. Must not be blank. |
| `context` | string | `""` | Reference material. Sent first inside `<context>` tags; the model is told to treat it as data, not instructions. |
| `mode` | string | `quick` | One of `quick`, `generate`, `refactor`, `review`, `explain`. Unknown modes are rejected. |
| `model` | string | `OPENCODE_MODEL` | Any OpenRouter model id, e.g. `anthropic/claude-sonnet-4.6`. |
| `temperature` | number | `OPENCODE_TEMPERATURE` | 0 to 2. |
| `max_tokens` | integer | `OPENCODE_MAX_TOKENS` | Completion limit. |
| `force` | bool | `false` | Consult even if `OPENCODE_ENABLED=false`. |
| `comparison_mode` | bool | `true` | Accepted for backward compatibility; has no effect. |

### Modes

| Mode | Behaviour |
|------|-----------|
| `quick` | Concise answer, minimal example when useful (default) |
| `generate` | Complete, working code from requirements; no placeholders |
| `refactor` | Behaviour-preserving refactor plus a list of changes |
| `review` | Issues ordered by severity with location and concrete fix |
| `explain` | Structured explanation of purpose, flow, and pitfalls |

### Response shape

```json
{
  "status": "success",
  "response": "...",
  "execution_time": 2.41,
  "consultation_id": "5f0c...",
  "mode": "review",
  "model": "qwen/qwen3.7-max",
  "finish_reason": "stop",
  "usage": {"prompt_tokens": 812, "completion_tokens": 403, "total_tokens": 1215}
}
```

`status` is `success`, `error`, `timeout`, or `disabled`. Errors and timeouts
also set the MCP `isError` flag. Optional fields: `input_truncated` (query or
context exceeded `OPENCODE_MAX_PROMPT`), `warning` (response hit `max_tokens`).

### Examples

```bash
curl -s -X POST http://localhost:8014/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "consult_opencode", "arguments": {"query": "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)", "mode": "review"}}'

curl -s -X POST http://localhost:8014/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "consult_opencode", "arguments": {"query": "Write a thread-safe LRU cache", "context": "Rust 2024, no external crates", "mode": "generate", "max_tokens": 8000}}'

curl -s -X POST http://localhost:8014/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "opencode_status", "arguments": {}}'
```

## Configuration

Booleans accept `true/false/1/0/yes/no/on/off`. Invalid or out-of-range values
fall back to (or are clamped toward) the default with a warning on stderr.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | none | Required. Never logged or returned by tools. |
| `OPENCODE_MODEL` | `qwen/qwen3.7-max` | Default model id |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible base URL (proxy, gateway, local mock) |
| `OPENCODE_ENABLED` | `true` | When `false`, consultations return `disabled` unless `force=true` |
| `OPENCODE_AUTO_CONSULT` | `true` | Advisory flag reported to clients; the server never consults on its own |
| `OPENCODE_TIMEOUT` | `300` | Overall deadline in seconds per consultation, including retries (1-3600) |
| `OPENCODE_MAX_PROMPT` | `32000` | Max characters of query + context; query has priority |
| `OPENCODE_MAX_TOKENS` | `4096` | Default completion token limit |
| `OPENCODE_TEMPERATURE` | `0.3` | Default sampling temperature (0-2) |
| `OPENCODE_MAX_RETRIES` | `2` | Retries for 408/429/5xx/connection errors (0-10) |
| `OPENCODE_INCLUDE_HISTORY` | `true` | Replay the last 3 exchanges as chat turns |
| `OPENCODE_MAX_HISTORY` | `5` | Retained history entries (0 disables) |
| `OPENCODE_LOG_CONSULTATIONS` | `true` | Log one line (id, status, time) per consultation; prompts are never logged |

A `.env` file in the working directory is loaded if present.

### CLI arguments (from `mcp-core`)

```
--mode <MODE>         standalone | stdio | server | client   [default: standalone]
--port <PORT>         HTTP port (ignored in stdio mode)      [default: 8000]
--backend-url <URL>   Backend URL (client mode)
--log-level <LEVEL>   Log level                              [default: info]
```

`docker-compose.yml` runs the service on port 8014.

## MCP client configuration

```json
{
  "mcpServers": {
    "opencode": {
      "command": "docker",
      "args": ["compose", "-f", "./docker-compose.yml", "--profile", "services",
               "run", "--rm", "-T", "mcp-opencode", "mcp-opencode", "--mode", "stdio"]
    }
  }
}
```

Or with a locally built binary: `"command": "mcp-opencode", "args": ["--mode", "stdio"]`
and `OPENROUTER_API_KEY` in `env`.

## Development

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test            # offline: uses an in-process mock HTTP server, no API key needed
cargo build --release
```

Layout:

| File | Purpose |
|------|---------|
| `src/main.rs` | CLI entry point |
| `src/server.rs` | Tool assembly |
| `src/opencode.rs` | OpenRouter client, prompts, response parsing, retries |
| `src/config.rs` | Environment configuration (redacted `Debug`) |
| `src/consult.rs` | Generic consult/status tools and state (identical copy in `mcp_crush`) |
| `src/util.rs` | UTF-8-safe truncation, secret redaction, env parsing (identical copy in `mcp_crush`) |
| `src/test_support.rs` | Mock HTTP server for tests |

`consult.rs` and `util.rs` are deliberately byte-identical to the copies in
`tools/mcp/mcp_crush/src/`; change both together.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `OPENROUTER_API_KEY is not configured` | Export the key (or add it to `.env`) for the server process |
| `OpenRouter API error (401 ...) (check OPENROUTER_API_KEY)` | Invalid or revoked key |
| `OpenRouter API error (402 ...)` | Out of OpenRouter credits |
| `OpenRouter API error (404 ...) (check the model id)` | Unknown `model` / `OPENCODE_MODEL` |
| `status: timeout` | Raise `OPENCODE_TIMEOUT` or lower `max_tokens` |
| `warning: Response was cut off at max_tokens` | Pass a larger `max_tokens` |
| `Model returned an empty response` | Some reasoning models spend the budget on hidden reasoning; raise `max_tokens` or switch models |

## Limitations

- Single-shot request/response; no streaming and no tool use.
- History is in-memory, process-wide (shared by all clients of one server), and lost on restart.
- `comparison_mode` is accepted but ignored.
- Codex and Gemini are disabled repository-wide; do not point this server at them.
