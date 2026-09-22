# Code Quality MCP Server (Rust)

> MCP server that runs code quality tools -- formatters, linters, pytest, the
> ty type checker, bandit, pip-audit, and a markdown link checker -- on paths
> inside a configured allowlist, and returns structured JSON results.

Every tool call runs an external program as a bounded subprocess:

- **No shell.** Program and arguments are passed as separate argv entries.
- **Path allowlist.** Every path is canonicalized (resolving `..` and symlinks)
  and must exist inside an allowed root. The canonical absolute path is what the
  tool receives, so a user string can never be read as a command-line option.
- **Hard timeout.** On timeout the tool is killed (on Linux, its whole process
  group, so pytest/cargo children die too).
- **Bounded output.** stdout/stderr are streamed into a capped buffer that keeps
  the head and tail; `truncated: true` marks anything cut. Issue/finding lists
  are capped at 500 entries (the `*_count` fields keep the full count).
- **Concurrency limit** on simultaneous tool processes, **per-tool rate
  limits**, and a JSON-lines **audit log** with size-based rotation.

## Quick Start

```bash
# Docker (how .mcp.json launches it: STDIO through docker compose)
docker compose --profile services run --rm -T mcp-code-quality mcp-code-quality --mode stdio

# HTTP mode
docker compose --profile services up -d mcp-code-quality     # listens on 8010
curl http://localhost:8010/health
curl -X POST http://localhost:8010/mcp/execute -H 'Content-Type: application/json' \
  -d '{"tool": "lint", "arguments": {"path": "/app/tools/cli", "linter": "ruff"}}'

# From source (the external tools must be on PATH)
cargo build --release
./target/release/mcp-code-quality --mode stdio --allowed-paths "$PWD"
```

## Tools

All tools return a JSON object. `success` means *the tool ran and produced a
usable result*; whether the code passed is reported separately in `passed`
(or `formatted`). On failure `success` is `false` with `error` and
`error_type` (see [Errors](#errors)). Result objects also carry `command`
(for display only), `returncode`, `duration_ms`, and, when relevant,
`truncated` and `notes` (caveats such as an ignored option).

Invalid arguments -- a missing required parameter, a wrong type, or an unknown
enum value such as `linter: "pylint"` -- are rejected with an MCP
`InvalidParameters` error rather than silently replaced by a default. `null`
values count as "not provided".

| Tool | Required | Optional (default) |
|------|----------|--------------------|
| `format_check` | `path` | `language` (`python`), `formatter` (`ruff`), `diff` (`false`) |
| `autoformat` | `path` | `language` (`python`), `formatter` (`ruff`) |
| `lint` | `path` | `linter` (`ruff`), `config` |
| `type_check` | `path` | `strict` (`false`), `config` |
| `run_tests` | -- | `path` (`tests/`), `working_dir`, `pattern`, `markers`, `verbose`, `coverage`, `fail_fast` (all `false`) |
| `security_scan` | `path` | `severity` (`low`), `confidence` (`low`) |
| `audit_dependencies` | -- | `requirements_file` (`requirements.txt`) |
| `check_markdown_links` | `path` | `check_external` (`true`), `timeout` (10, 1-120), `concurrent` (10, 1-64), `ignore_patterns` (`[]`), `exclude` (`[]`), `skip_anchors` (`false`) |
| `get_status` | -- | -- |
| `get_audit_log` | -- | `limit` (100, clamped to 1-1000), `operation` |

Relative paths resolve against the server's working directory (`/app` in the
container), except for `run_tests`, where they resolve against `working_dir`
when it is given.

### `format_check` / `autoformat`

| `language` | Command |
|------------|---------|
| `python` | `ruff format [--check] [--diff]` (default), or `black` with `formatter: "black"` |
| `javascript`, `typescript` | `prettier --check` / `prettier --write` |
| `go` | `gofmt -l` (check), `gofmt -d` (check + diff), `gofmt -w` (write) |
| `rust` | crate directory with `Cargo.toml`: `cargo fmt [--check]`; single `.rs` file: `rustfmt [--check] --edition <from nearest Cargo.toml, else 2021>` |

`format_check` returns `formatted` and `unformatted_files`; `diff: true` puts a
diff in `output` (not supported by prettier -- a note says so). A formatter that
fails for another reason (syntax error, bad config) is reported as
`tool_error`, not as "unformatted". `autoformat` modifies files in place, which
fails on the default read-only `/app` mount.

> The default Python formatter changed from `black` to `ruff format` to match
> this repository's CI. Pass `formatter: "black"` for the old behaviour.

### `lint`

| `linter` | Command | `config` |
|----------|---------|----------|
| `ruff` | `ruff check --no-cache --output-format concise` | `--config <file>` |
| `flake8` | `flake8` | `--config <file>` |
| `eslint` | `eslint --format json` (parsed) | `--config <file>` |
| `golint` | `golint` | not supported (a note is returned) |
| `clippy` | `cargo clippy --quiet --message-format=short` in the crate directory | its directory is used as `CLIPPY_CONF_DIR` |

Returns `passed`, `issues` (`file:line:col: message` strings) and
`issue_count`. `passed` requires both exit code 0 and no issues, so clippy
warnings count. A non-zero exit with no parseable issues (bad config, compile
error) is a `tool_error` with the raw `output`. Clippy builds into a shared
scratch target directory under the system temp dir, so it works on a read-only
mount.

### `type_check`

Runs `ty check --output-format concise`. `strict: true` adds
`--error-on-warning`. `config` may be a `pyproject.toml` (its directory is
passed as `--project`) or a `ty.toml` (`--config-file`).

### `run_tests`

Runs `pytest <path> -p no:cacheprovider` (no cache writes, so a read-only
workspace works).

- `pattern`: a file glob such as `test_*.py` sets `python_files`; anything
  else (e.g. `login and not slow`) is passed to `-k`.
- `markers`: passed to `-m`.
- `coverage`: `--cov=<working_dir or .> --cov-report=term-missing` (needs
  pytest-cov); the coverage data file goes to the temp dir.
- `working_dir`: pytest's working directory (must be inside the allowlist).

Returns `passed`, `returncode`, `summary` (parsed from the final line, e.g.
`{"passed": 3, "failed": 1, "skipped": 2}`), and the capped `output`. Exit
code 5 ("no tests collected") gives `passed: false` plus a note. Running tests
executes the project's code; the allowlist restricts what is targeted, not
what that code can do.

### `security_scan`

Runs `bandit -r <path> --severity-level=.. --confidence-level=.. -f json -q`.
Returns `passed` (no findings), `findings` (bandit result objects),
`finding_count`, and `summary` (`high`/`medium`/`low`/`errors` counts). Files
bandit could not parse are listed in `notes`.

### `audit_dependencies`

Runs `pip-audit -r <file> --format json`. Returns `passed`, and
`vulnerabilities` as one entry per vulnerability:
`{package, version, id, fix_versions, aliases, description}`. Needs network
access to PyPI/OSV.

### `check_markdown_links`

Runs the repository's `md-link-checker` (`tools/rust/markdown-link-checker`,
built into the container image). `ignore_patterns` are regexes matched against
links; `exclude` are gitignore-style globs of files to skip. Returns `passed`,
`files_checked`, `total_links`, `broken_links`, and `broken`: one
`{file, url, lines, error}` entry per broken link (plus `{file, error}` for
unreadable files).

### `get_status`

Server version, timeout, output/concurrency limits, configured and effective
(canonical, existing) allowed paths, rate limits, audit log path, and, for
every external tool, `{available, version | reason}`. Probes run concurrently
with a 10s timeout each.

### `get_audit_log`

The most recent entries (oldest first), optionally filtered by `operation`.
Reads across one rotation (`audit.log.1`) when needed.

### Errors

| `error_type` | Meaning |
|--------------|---------|
| `path_validation` | Path missing, of the wrong kind (file vs directory), malformed, or outside the allowlist. `allowed_paths` is included. |
| `invalid_input` | Argument out of range, containing control characters, or unsupported (e.g. clippy on a directory without `Cargo.toml`). |
| `rate_limit` | Per-tool limit exceeded; the message says when to retry. |
| `tool_not_found` | The external program is not installed. |
| `timeout` | The tool exceeded `--timeout` and was killed. |
| `tool_error` | The tool ran but failed without a usable result; raw `output` is included. |
| `exception` | Unexpected I/O failure. |

### Example

```json
{"tool": "lint", "arguments": {"path": "/app/tools/cli", "linter": "ruff"}}
```

```json
{
  "success": true,
  "passed": false,
  "command": "ruff check --no-cache --output-format concise /app/tools/cli",
  "issues": ["tools/cli/x.py:1:8: F401 [*] `os` imported but unused"],
  "issue_count": 1,
  "returncode": 1,
  "duration_ms": 22
}
```

## Configuration

| Flag | Env var | Default | Notes |
|------|---------|---------|-------|
| `--mode` | -- | `standalone` | `standalone` (HTTP), `stdio`, `server`, `client` |
| `--port` | -- | `8000` | The container passes `--port 8010` |
| `--log-level` | -- | `info` | Logs go to stderr |
| `--timeout` | `MCP_CODE_QUALITY_TIMEOUT` | `600` | Seconds per tool run (1-86400) |
| `--allowed-paths` | `MCP_CODE_QUALITY_ALLOWED_PATHS` | `/workspace,/app,/home` | Comma-separated; roots that do not exist are ignored with a warning |
| `--audit-log` | `MCP_CODE_QUALITY_AUDIT_LOG` | `/var/log/mcp-code-quality/audit.log` | JSON lines |
| `--audit-log-max-bytes` | `MCP_CODE_QUALITY_AUDIT_LOG_MAX_BYTES` | `10485760` | Rotate to `<file>.1` beyond this (min 4096) |
| `--rate-limit` | `MCP_CODE_QUALITY_RATE_LIMIT` | `true` | `--rate-limit false` disables |
| `--max-output-bytes` | `MCP_CODE_QUALITY_MAX_OUTPUT_BYTES` | `100000` | Per stream (1 KiB - 64 MiB) |
| `--max-concurrent` | `MCP_CODE_QUALITY_MAX_CONCURRENT` | `4` | Simultaneous tool processes (1-64) |

Rate limits (calls per minute): `format_check` 100, `lint` 50, `autoformat`
50, `type_check` 30, `check_markdown_links` 30, `run_tests` 20,
`security_scan` 20, `audit_dependencies` 10.

## External tools

The container image (`docker/mcp-code-quality.Dockerfile`) installs ruff,
black, flake8, ty, pytest, pytest-cov, bandit, pip-audit, prettier, eslint,
and md-link-checker. It does **not** include Go (`gofmt`, `golint`) or a Rust
toolchain (`cargo`, `rustfmt`, `clippy`); those tools report `tool_not_found`
there. `golint` is deprecated upstream. Use `get_status` to see what is
available.

## Limitations

- The compose service mounts the repository read-only at `/app`, so
  `autoformat` cannot write there.
- `run_tests` executes project code; `audit_dependencies` and
  `check_markdown_links` (with `check_external`) need network access.
- `unformatted_files` is parsed from formatter output and is best effort.
- Rust files in a workspace that inherits `edition.workspace = true` fall back
  to the first literal `edition` found in an ancestor `Cargo.toml`, else 2021.

## Development

```bash
cd tools/mcp/mcp_code_quality
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test            # offline; the real-tool test only needs rustfmt
cargo build --release
```

Source layout:

```
src/
  main.rs       CLI flags -> EngineConfig, server startup
  server.rs     MCP tool definitions: JSON schemas + typed argument structs
  engine.rs     per-tool pipeline: rate limit, validate, run, parse, audit
  commands.rs   pure argv builders for every external tool
  parsers.rs    pure parsers for tool output (ruff, eslint, bandit, pip-audit, pytest, ...)
  process.rs    bounded subprocess runner (timeout + kill, capped output, ANSI stripping)
  paths.rs      path allowlist enforcement
  ratelimit.rs  sliding-window rate limiter
  audit.rs      JSON-lines audit log with rotation
  types.rs      argument enums and the result type
```
