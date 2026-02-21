# Automation

Infrastructure scripts for CI/CD, agent management, security hardening, and service orchestration. All Python and Rust operations follow the container-first philosophy -- everything runs in Docker unless there is a documented exception (e.g., Claude CLI requires host-level authentication).

Most shell scripts in this directory are thin wrappers that delegate to the `automation-cli` Rust binary. Build it once and use it everywhere:

```bash
cargo build --release -p automation-cli
```

## Directory Overview

| Directory | Purpose |
|-----------|---------|
| `ci-cd/` | CI/CD pipeline scripts and agent decision framework |
| `hooks/` | Git hook helpers (pre-commit formatting) |
| `monitoring/` | Issue monitor launchers for GitHub agent workflows |
| `review/` | PR review setup (Gemini CLI authentication) |
| `scripts/` | Service management wrappers (start, wait, remote) |
| `setup/` | One-time host and runner provisioning |
| `testing/` | MCP server integration tests and video editor test suite |
| `analysis/` | Gaea2 project analysis and schema generation |
| `corporate-proxy/` | Translation proxies for corporate AI services |
| `launchers/` | Cross-platform service launcher scripts |

## ci-cd/

Pipeline scripts invoked by GitHub Actions workflows and local development.

| Script | Description |
|--------|-------------|
| `run-ci.sh` | Thin wrapper -- delegates to `automation-cli ci run <stage>` |
| `run-lint-stage.sh` | Thin wrapper -- delegates to `automation-cli lint` |
| `build-docker-images.sh` | Build all Docker images in dependency order |
| `build-latex-doc.sh` | Compile LaTeX documents via containerized TeXLive |
| `agent-failure-handler.sh` | Handle agent review failures (`automation-cli review failure`) |
| `agent-review-response.sh` | Process agent review responses (`automation-cli review respond`) |
| `test-auto-review.sh` | Local test harness for auto-review functionality |
| `install-actionlint.sh` | Install actionlint for GitHub Actions workflow validation |
| `cleanup-workspace.sh` | Emergency cleanup of Python cache files with permission issues |
| `cleanup-outputs.sh` | Docker-based cleanup of output directories |
| `fix-outputs-permissions.sh` | Fix permission issues on outputs directory |
| `AGENT_DECISION_RUBRIC.md` | Decision framework for automated review responses |

Common CI commands:

```bash
automation-cli ci run full           # All Python checks
automation-cli ci run format         # Check formatting
automation-cli ci run lint-full      # Full linting (ruff + ty)
automation-cli ci run rust-full      # All Rust checks
automation-cli ci run econ-full      # Economic agents (fmt + clippy + test)
automation-cli ci list               # Show all available stages
```

## hooks/

Git hook helpers installed via `automation/setup/git/`.

| Script | Description |
|--------|-------------|
| `fmt-mcp-servers.sh` | Pre-commit hook that runs `cargo fmt` on all standalone MCP servers (skips `mcp_core_rust`, `mcp_bioforge`, `mcp_code_quality`) |

## monitoring/

Launchers for the GitHub issue monitor agent system. The actual monitor binary lives at `tools/rust/github-agents-cli/`.

| Script | Description |
|--------|-------------|
| `issues/run-issue-monitor-hybrid.sh` | Hybrid mode -- Claude and Gemini on host, OpenCode and Crush in Docker |
| `issues/run-containerized-issue-monitor.sh` | Fully containerized mode via `docker compose --profile agents` |

## review/

PR review automation setup.

| Script | Description |
|--------|-------------|
| `setup-gemini-cli.sh` | Set up Gemini CLI for PR reviews with OAuth, API key, or Docker Compose authentication |

## scripts/

Service management wrappers that delegate to `automation-cli`.

| Script | Description |
|--------|-------------|
| `start-ai-services.sh` | Start AI services (`automation-cli service start`) |
| `remote-ai-services.sh` | Manage remote AI services (`automation-cli service`) |
| `wait-for-it.sh` | Wait for service readiness (`automation-cli wait`) |

## setup/

One-time provisioning scripts organized by concern.

| Subdirectory | Contents |
|-------------|----------|
| `agents/` | `setup-host-for-agents.sh` -- prepare host for AI agent execution (Node.js, CLIs, credentials) |
| `docker/` | `init-output-dirs.sh` -- pre-create output directories with correct ownership; `set-docker-user.sh` -- configure Docker user mapping |
| `git/` | `setup-pre-commit.sh` -- deprecated, points to `automation-cli`; `hooks/pre-push` -- pre-push hook with PR monitoring reminders |
| `runner/` | GitHub Actions self-hosted runner setup: `setup-runner.sh` (simple), `setup-runner-full.sh` (complete with Docker and MCP), `fix-runner-permissions.sh`, `setup-github-actions-permissions.sh` |
| `security/` | Wrapper guard hardening: `setup-wrapper-guard.sh`, `verify-wrapper-guard.sh`, `uninstall-wrapper-guard.sh` -- setgid chain for git-guard and gh-validator |

## testing/

Integration tests for MCP servers and the video editor.

| File | Description |
|------|-------------|
| `test_all_servers.py` | Smoke test all MCP servers (STDIO and HTTP) |
| `test_mcp_servers_tools.py` | Tool-level integration tests for MCP servers |
| `video_editor/` | Video editor test suite: creation, validation, and example scripts (has its own README) |

## analysis/

Gaea2 terrain engine analysis utilities.

| File | Description |
|------|-------------|
| `analyze_gaea_projects.py` | Analyze real Gaea2 projects to learn patterns and best practices |
| `generate_gaea2_schema.py` | Generate deterministic validation schema from documentation and project analysis |

## corporate-proxy/

Translation proxies that let AI development tools (OpenCode, Crush, Gemini CLI) work with corporate AI services behind firewalls. Supports mock mode for development and corporate mode for production. Each tool has its own subdirectory with Dockerfiles, configs, and build/run scripts.

See [`corporate-proxy/README.md`](corporate-proxy/README.md) for full documentation.

## launchers/

Cross-platform launcher scripts for remote services (AI Toolkit, ComfyUI, Gaea2 MCP). Organized by platform with `unix/` and `windows/` subdirectories.

See [`launchers/README.md`](launchers/README.md) for full documentation.

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) -- CI/CD command reference and project conventions
- [docs/infrastructure/containerization.md](../docs/infrastructure/containerization.md) -- Container-first philosophy
- [docs/infrastructure/self-hosted-runner.md](../docs/infrastructure/self-hosted-runner.md) -- Runner setup guide
- [docs/infrastructure/wrapper-guard.md](../docs/infrastructure/wrapper-guard.md) -- CLI binary hardening
- [docs/developer/claude-code-hooks.md](../docs/developer/claude-code-hooks.md) -- Hook system documentation
- [docs/agents/README.md](../docs/agents/README.md) -- Agent system overview
