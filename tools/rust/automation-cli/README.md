# automation-cli

Unified Rust CLI for CI/CD orchestration, service launching, and automation. Replaces the bulk of the shell scripts in `automation/` with a single, type-safe binary.

## Build

```bash
cargo build --release --manifest-path tools/rust/automation-cli/Cargo.toml
```

The binary is produced at `tools/rust/automation-cli/target/release/automation-cli`.

## Shell Wrappers

The original shell scripts have been replaced with thin wrappers that delegate to the Rust binary. This preserves backward compatibility with workflow files and documentation that reference the old script paths.

| Shell Wrapper | CLI Equivalent |
|--------------|----------------|
| `automation/ci-cd/run-ci.sh <stage>` | `automation-cli ci run <stage>` |
| `automation/ci-cd/run-lint-stage.sh <mode>` | `automation-cli lint <mode>` |
| `automation/ci-cd/agent-review-response.sh` | `automation-cli review respond` |
| `automation/ci-cd/agent-failure-handler.sh` | `automation-cli review failure` |
| `automation/scripts/wait-for-it.sh` | `automation-cli wait` |
| `automation/launchers/unix/start-ai-toolkit.sh` | `automation-cli launch ai-toolkit` |
| `automation/launchers/unix/start-comfyui.sh` | `automation-cli launch comfyui` |
| `automation/launchers/unix/start-gemini-mcp.sh` | `automation-cli launch gemini-mcp` |
| `automation/scripts/start-ai-services.sh` | `automation-cli service start` |
| `automation/scripts/remote-ai-services.sh` | `automation-cli service <action>` |

## Subcommands

### `ci` -- CI/CD Pipeline

```bash
automation-cli ci run <stage> [extra-args...]   # Run a CI stage
automation-cli ci list                          # List all available stages
```

Stages include all Python and Rust CI checks. Run `automation-cli ci list` for the full list.

### `lint` -- Lint Stages

```bash
automation-cli lint <mode> [extra-args...]
```

Modes: `format`, `basic`, `full`, `links`, `ruff`, `ruff-fix`, `shell`

### `review` -- AI Code Review Handling

```bash
automation-cli review respond <pr> <branch> <iteration>
automation-cli review failure <pr> <branch> <iteration> [failure-types]
```

### `wait` -- Health Check Utility

```bash
automation-cli wait --host <host> --port <port> [--timeout 15]
automation-cli wait --port 8080 --health-endpoint /health
```

Supports TCP and HTTP health checks with configurable timeout.

### `launch` -- Service Launchers

```bash
automation-cli launch ai-toolkit [--port 8675]
automation-cli launch comfyui [--port 8188]
automation-cli launch gemini-mcp [--mode stdio|http] [--port 8014]
```

### `service` -- Remote AI Service Management

```bash
automation-cli service start [--mode docker|host] [--profile ai-services]
automation-cli service stop
automation-cli service restart
automation-cli service logs
automation-cli service status
automation-cli service build
automation-cli service pull
automation-cli service update
```

### `setup` -- Environment Setup

```bash
automation-cli setup agents          # Check AI agent prerequisites
automation-cli setup runner          # Setup GitHub Actions runner
automation-cli setup runner-full     # Full runner setup with system deps
automation-cli setup permissions     # Fix runner permissions
automation-cli setup init-dirs       # Initialize Docker output directories
```

### `proxy` -- Corporate Proxy Tests

```bash
automation-cli proxy [--build]
```

## CI Integration

The automation-cli is automatically included in the `tools-full` and `rust-all` CI stages via the `tools/rust/*/` iterator pattern. It is also built as part of release binaries in `main-ci.yml`.
