# automation-cli

Unified Rust CLI for CI/CD orchestration, PR review agents, service launching, and runner setup. CI stages run inside the `python-ci` / `rust-ci` Docker Compose services (container-first); the binary itself only needs Docker on the host.

## Build

```bash
# Container-first (output lands in tools/rust/automation-cli/target/release/)
docker compose --profile ci run --rm -w /app/tools/rust/automation-cli rust-ci cargo build --release

# Or with a host toolchain (Rust 1.91+)
cargo build --release --manifest-path tools/rust/automation-cli/Cargo.toml
```

The shell wrappers below expect the binary at `tools/rust/automation-cli/target/release/automation-cli`; CI workflows download a prebuilt binary to that path.

## Shell Wrappers

The scripts in `automation/` are thin wrappers that `exec` this binary, so existing workflow and documentation references keep working:

| Shell Wrapper | CLI Equivalent |
|--------------|----------------|
| `automation/ci-cd/run-ci.sh <stage> [args]` | `automation-cli ci run <stage> [args]` |
| `automation/ci-cd/run-lint-stage.sh <mode>` | `automation-cli lint <mode>` |
| `automation/ci-cd/agent-review-response.sh ...` | `automation-cli review respond ...` |
| `automation/ci-cd/agent-failure-handler.sh ...` | `automation-cli review failure ...` |
| `automation/scripts/wait-for-it.sh ...` | `automation-cli wait ...` |
| `automation/launchers/unix/start-ai-toolkit.sh` | `automation-cli launch ai-toolkit` |
| `automation/launchers/unix/start-comfyui.sh` | `automation-cli launch comfyui` |
| `automation/launchers/unix/start-gemini-mcp.sh` | `automation-cli launch gemini-mcp` |
| `automation/scripts/start-ai-services.sh` | `automation-cli service start` |
| `automation/scripts/remote-ai-services.sh <action>` | `automation-cli service <action>` |

All commands locate the project root by walking up from the current directory to the first directory containing both `docker-compose.yml` and `CLAUDE.md`, and run from there.

## `ci` -- CI Stages

```bash
automation-cli ci run <stage> [extra-args...]   # Run a CI stage
automation-cli ci list [--names]                # List stages (--names: one per line)
automation-cli ci doctor                        # Validate stage references and layout
```

`extra-args` are forwarded to pytest (`test`, `test-all`, `test-corporate-proxy`) or `cargo test` (including `test-gaea2`) / `cargo llvm-cov` (Rust test and coverage stages), e.g. `ci run test -- --timeout=300`. Unknown stage names fail immediately with a "did you mean" hint.

### Python stages (`python-ci` container)

| Stage | What it runs |
|-------|--------------|
| `format` | `ruff format --check --diff`, import order (`ruff --select=I`) |
| `lint-basic` | format + import checks, critical errors (`E9,F63,F7,F82`), style (`E,W,C90`) |
| `lint-full` | format + import checks, full `ruff check`, `ty check` (informational) |
| `lint-shell` | `shellcheck -S warning` on every `*.sh` |
| `ruff` / `ruff-fix` | `ruff check` (GitHub annotations) / `ruff check --fix` |
| `bandit` | Bandit security scan |
| `security` | Bandit (medium+ severity fails) + dependency audit (Safety if `SAFETY_API_KEY` is set, else pip-audit; advisory) |
| `test` | pytest `tests/` + `automation/corporate-proxy/tests/` with coverage, plus proxy component scripts |
| `test-all` | pytest `tests/` with coverage |
| `test-gaea2` | `cargo test` for `tools/mcp/mcp_gaea2` (rust-ci), then a live `/health` check of `$GAEA2_MCP_URL` (default `http://192.168.0.152:8007`; unreachable = warning) |
| `test-corporate-proxy` | pytest `automation/corporate-proxy/tests/` only |
| `yaml-lint` | `yamllint` + strict `yaml.safe_load_all` over every YAML file |
| `json-lint` | strict JSON parse of every `*.json` |
| `autoformat` | `ruff format`, `ruff --select=I --fix`, and `cargo fmt --all` for every crate in `tools/rust/*`, `tools/mcp/*` and the `packages/` workspaces (one container run) |
| `full` | `format`, `lint-basic`, `lint-full`, `lint-shell`, `security`, `yaml-lint`, `json-lint`, `test` |

File discovery for `yaml-lint`, `json-lint` and `lint-shell` skips `.git`, `target`, `node_modules`, virtualenvs, caches and `outputs`.

### Rust stages (`rust-ci` container)

| Prefix | Directory | Stages |
|--------|-----------|--------|
| `econ-` | `packages/economic_agents` | `fmt clippy test build deny doc coverage full` |
| `mcp-` | `tools/mcp/mcp_core_rust` | `fmt clippy test build deny doc full` |
| `bio-` | `packages/bioforge` (+ `tools/mcp/mcp_bioforge` for fmt/clippy/build) | `fmt clippy test build deny full` |
| `sleeper-` | `packages/sleeper_agents` | `fmt clippy test build deny full` |
| `tamper-` | `packages/tamper_briefcase` (host crates only; aarch64 crates skipped) | `fmt clippy test build deny full` |
| `sprite-` | `tools/mcp/mcp_sprite_sheet` | `fmt clippy test build full` |
| `wrapper-` | `tools/rust/{wrapper-common,git-guard,gh-validator}` | `fmt clippy test full` |
| `mcp-servers-` | every `tools/mcp/*` crate except `mcp_core_rust`, `mcp_bioforge` | `fmt clippy test full` |
| `tools-` | every other `tools/rust/*` crate (including this one) | `fmt clippy test full` |

`fmt` = `cargo fmt --all -- --check`; `clippy` = `--all-targets -- -D warnings`; `*-full` = fmt + clippy + test. The `wrapper-`, `mcp-servers-` and `tools-` groups discover crates automatically (any directory with a `Cargo.toml`), keep going past failures, and list every failing crate at the end.

`rust-all` (alias `rust-full`) runs `econ-full`, `mcp-full`, `bio-full`, `tamper-full`, `sleeper-full`, `wrapper-full`, `mcp-servers-full`, `tools-full`.

### `ci doctor`

Checks, without running anything in Docker:

- `python-ci` and `rust-ci` exist in `docker-compose.yml`
- every workspace directory, the tamper host crates, and `tools/mcp/mcp_bioforge` exist; crate groups are non-empty
- paths used by the test stages exist (Python test dirs, `tools/mcp/mcp_gaea2`)
- every `run-ci.sh <stage>`, `automation-cli ci run <stage>`, `run-lint-stage.sh <mode>` and `automation-cli lint <mode>` reference in `*.md`, `*.yml`, `*.yaml` and `*.sh` files resolves (lines starting with `#` are ignored)

Exits 1 if any check fails; missing optional files (e.g. `deny.toml`) are warnings.

## `lint` -- Counted Lint Stages

```bash
automation-cli lint <format|ruff|basic|full|links>
```

Used by `.github/workflows/lint-stages.yml`. Each mode counts failed checks as errors (and dependency-audit findings as warnings), appends `errors=N` / `warnings=N` to `$GITHUB_ENV`, and exits 1 if `errors > 0`.

| Mode | Errors counted |
|------|----------------|
| `format` | `ruff format --check`, import order |
| `ruff` | `ruff check` |
| `basic` | critical errors only (format/style output is informational) |
| `full` | format, full ruff, critical errors, Bandit; `ty` informational; dependency audit = warning |
| `links` | `md-link-checker <root> --internal-only`; writes `link_check_summary.md` for the PR comment step |

`links` uses `tools/rust/markdown-link-checker/target/release/md-link-checker`, then `md-link-checker` on `PATH`, and otherwise builds it in the `rust-ci` container.

## `review` -- PR Agents

```bash
automation-cli review respond <pr> <branch> [iteration=1] [max-iterations=5]
automation-cli review failure <pr> <branch> [iteration=1] [max-iterations=5] [failure-types=format,lint]
automation-cli review precommit [--autoformat] [--lint[=STAGES]] [--test[=STAGES]] [--stage STAGES] [--fail-on-error]
```

- **respond** reads reviewer output files (`CLAUDE_SECURITY_REVIEW_PATH`, `CLAUDE_QUALITY_REVIEW_PATH`, `OPENROUTER_REVIEW_PATH`; defaults `*-review.md` in the repo root) and PR comments bucketed by trust (`security.agent_admins` / `security.trusted_sources` in `.agents.yaml`). It runs Claude (`claude -p --output-format stream-json`), cross-checks claimed fixes against actual `Edit`/`Write` tool calls and `git diff`, retries once with the prior iteration's diff on a mismatch, runs `lint-basic` and feeds failures back, then commits and pushes. Outputs: `made_changes`, `pushed`, `commit_sha`. The masked stream log goes to `$RUNNER_TEMP/review-agent-logs/`; an unpushed commit is saved to `$RUNNER_TEMP/review-agent-patches/` (both require `.secrets.yaml`, fail-closed).
- **failure** reads `FORMAT_CHECK_RESULT`, `BASIC_LINT_RESULT`, `FULL_LINT_RESULT`, `TEST_SUITE_RESULT` (falling back to `failure-types`), autoformats, captures remaining lint/test errors, runs Claude, commits and pushes. Outputs: `exceeded_max` (and exit 1 when `iteration >= max-iterations`), `made_changes`, `pushed`, `commit_sha`.
- **precommit** runs `autoformat` and restages formatter changes, then the requested stages (`--lint` defaults to `lint-basic`, `--test` to `test`; values are comma-separated). Prints a `[PASS]/[FAIL]` summary on stdout. Outputs: `precommit_passed`, `precommit_autoformat_changed`, `precommit_failed_checks`. Exits 0 unless `--fail-on-error`.

Both agents push with `git push --no-verify` and verify the result with `git ls-remote`, rebasing onto the remote on non-fast-forward rejections (up to 5 attempts). In GitHub Actions (`GITHUB_TOKEN` + `GITHUB_REPOSITORY` set) they configure an authenticated `origin` and a bot identity. CI stages are run by re-invoking this binary, so no shell wrapper is required.

## `wait` -- Readiness Check

```bash
automation-cli wait [HOST:PORT] [-H HOST] [-p PORT] [-t TIMEOUT=15] [-e /health] [-q]
automation-cli wait --host localhost --port 8080 --health-endpoint /health --timeout 60
automation-cli wait db:5432
```

TCP connect check by default; `--health-endpoint` switches to HTTP GET (2xx required). Polls every second; exits 1 on timeout (`--timeout 0` checks once).

## `launch` -- Service Launchers

```bash
automation-cli launch <ai-toolkit|comfyui|gemini-mcp> [--mode default|stdio|http] [--port PORT] [--no-browser] [--timeout 60]
```

- `ai-toolkit` / `comfyui`: build and start `mcp-ai-toolkit` / `mcp-comfyui` (profile `ai-services`), wait for the web UI (8675 / 8188), and open a browser unless `--no-browser`. ARM64 hosts use `docker/comfyui-arm64.Dockerfile`.
- `gemini-mcp`: builds `tools/mcp/mcp_gemini` if needed. Default/stdio mode prints usage; `--mode http` starts the server in the background on `--port` (else `$GEMINI_MCP_PORT`, else 8006) with its log and PID in the temp directory, and stops it again if it never becomes healthy. Gemini is disabled by project policy; this is for local testing only.

## `service` -- Remote AI Services

```bash
automation-cli service start [--mode docker|host] [--profile ai-services] [--timeout 60]
automation-cli service <stop|restart|logs|status|build|pull|update>
```

Manages `mcp-ai-toolkit` and `mcp-comfyui` only (other containers are never touched). `start --mode docker` checks for an NVIDIA GPU/runtime, builds, starts, and waits until both containers report `healthy`. `start --mode host` builds and runs the Rust `mcp-ai-toolkit` (port 8020) and `mcp-comfyui` (port 8013) servers directly. `pull` is `git pull --ff-only` on the current branch; `update` = pull + build + `up -d`.

## `setup` -- Environment Setup

```bash
automation-cli setup agents        # Report missing agent prerequisites (git, gh, docker, cargo, ...)
automation-cli setup runner        # automation/setup/runner/setup-runner.sh
automation-cli setup runner-full   # automation/setup/runner/setup-runner-full.sh
automation-cli setup permissions   # Output dirs, Python cache cleanup, USER_ID/GROUP_ID in .env, git safe.directory
automation-cli setup init-dirs     # Create outputs/* and chown them via a busybox container
```

`permissions` updates only the `USER_ID` / `GROUP_ID` lines of `.env` and preserves everything else.

## `proxy` -- Corporate Proxy

```bash
automation-cli proxy build [--arch amd64|arm64]
automation-cli proxy test [quick|crush|opencode|gemini|api|integration|all]
```

`build` builds `crush-proxy`, `opencode-proxy`, `gemini-proxy` (profile `proxy`) with `TARGETARCH`. `test quick`/`api` start `unified_tool_api.py` locally (needs Python with Flask), wait for `/health`, exercise `/tools` and `/execute`, and stop it; the image modes build one container; `integration` starts the crush/opencode proxy containers, checks `/health` on 8051/8052, and stops only those containers. `all` runs every mode and reports one combined summary.

## Development

```bash
MSYS_NO_PATHCONV=1 docker compose --profile ci run --rm -w /app/tools/rust/automation-cli rust-ci \
  bash -c "cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test"
```

The crate is covered by the `tools-*` CI stages and is built as a release binary by `main-ci.yml` and `pr-validation.yml`.
