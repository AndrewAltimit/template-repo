# pr-monitor

A Rust CLI tool for monitoring GitHub PR comments with intelligent classification.

## Overview

`pr-monitor` watches a GitHub Pull Request for comments from administrators or AI reviewers (like Gemini). When a relevant comment is detected, it outputs a structured JSON decision that can be used by automation tools or AI agents.

## Features

- **Polling-based monitoring** - Checks for new comments at configurable intervals
- **Intelligent classification** - Categorizes comments as admin commands, admin feedback, Gemini reviews, or CI results
- **Commit-based filtering** - Optionally only monitor comments after a specific commit
- **JSON output** - Structured output for automation integration
- **Graceful shutdown** - Handles Ctrl+C for clean interruption

## Installation

### Build from source

```bash
cd tools/rust/pr-monitor
cargo build --release
```

The binary will be at `target/release/pr-monitor`.

### Using Docker (CI)

```bash
docker-compose --profile ci run --rm rust-ci cargo build --release -p pr-monitor
```

## Usage

```bash
# Basic monitoring (10 minute timeout, 5 second poll interval)
pr-monitor 123

# Monitor for 30 minutes
pr-monitor 123 --timeout 1800

# JSON-only output (quiet mode, no stderr progress)
pr-monitor 123 --json

# Only monitor comments after a specific commit
pr-monitor 123 --since-commit abc1234

# Custom poll interval (check every 10 seconds)
pr-monitor 123 --poll-interval 10

# Combined options
pr-monitor 123 --timeout 3600 --poll-interval 10 --json --since-commit abc1234
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Found relevant comment (JSON output on stdout) |
| 1 | Timeout or error (no relevant comment found) |
| 130 | Interrupted by user (Ctrl+C) |

## Output Format

When a relevant comment is found, the tool outputs a JSON decision:

```json
{
  "needs_response": true,
  "priority": "high",
  "response_type": "admin_command",
  "action_required": "Execute admin command and respond",
  "comment": {
    "author": "AndrewAltimit",
    "timestamp": "2025-01-15T10:30:00Z",
    "body": "[ADMIN] Please add tests for this feature"
  }
}
```

### Response Types

| Type | Author | Trigger | Needs Response |
|------|--------|---------|----------------|
| `admin_command` | Admin user | Contains `[ADMIN]` | Yes (High priority) |
| `admin_comment` | Admin user | Any comment | Yes (Normal priority) |
| `gemini_review` | github-actions | Contains "Gemini" | Yes (Normal priority) |
| `ci_results` | github-actions | Contains "PR Validation Results" | No (Low priority) |

## Configuration

The tool uses the `gh` CLI for GitHub API access, which must be installed and authenticated:

```bash
# Check gh is installed and authenticated
gh auth status

# Authenticate if needed
gh auth login
```

### Admin User

Currently the admin user is hardcoded as `AndrewAltimit`. Future versions may support configuration via:
- Environment variable: `PR_MONITOR_ADMIN_USER`
- Config file: `~/.config/pr-monitor/config.toml`

## Dependencies

- **gh** (GitHub CLI) - Must be installed and authenticated
- No other runtime dependencies (statically linked Rust binary)

## Development

### Run tests

```bash
cargo test
```

### Run with verbose output

```bash
RUST_LOG=debug cargo run -- 123
```

### Build optimized release

```bash
cargo build --release --profile release
```

## Migration from Python/Bash

This tool is a Rust port of the original Python/Bash implementation:
- `automation/monitoring/pr/monitor.sh` - Polling logic
- `automation/monitoring/pr/pr_monitor_agent.py` - Classification logic
- `automation/monitoring/pr/monitor-pr.sh` - User wrapper

The Rust version provides:
- Single binary (no Python/Bash interpreter needed)
- Faster startup time
- Same JSON output format for drop-in replacement
- Improved error handling and user feedback

## License

MIT
